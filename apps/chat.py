# Chat: talk to Hermes from the device, over the LAN.
#
# Design notes (each one is a lesson from earlier in this project):
#   * The request runs in a THREAD. An agent turn takes ~10-30 s (sometimes
#     minutes), and blocking the UI on it is exactly how the device got frozen
#     by the WiFi bring-up. While waiting, the screen says so and stays alive.
#   * The transcript is appended to /chat.log, so a reset doesn't lose the
#     conversation (and the agent keeps its own side of it in a named session).
#   * No urequests in plain MicroPython: the POST is built by hand on a socket.

import json
import socket
import time

from tdeckmax import CELL, HEIGHT, WIDTH
from tdeckmax.keys import apply_layer
from tdeckmax.screen import FOOTER_H, HEADER_H, Screen, draw_chrome

LEFT = 8
LINE_H = 12
COLS = (WIDTH - 2 * LEFT) // CELL
ROWS = (HEIGHT - HEADER_H - FOOTER_H - 26) // LINE_H     # leaves room for the input line
CHAT_LOG = "/chat.log"
BRIDGE_PORT = 8097
TIMEOUT_S = 90       # per attempt: long enough for an agent turn (~13 s here),
                     # short enough that a dead link surfaces instead of hanging

_cfg = None


def config(path="/wifi.json"):
    global _cfg
    if _cfg is None:
        try:
            _cfg = json.load(open(path))
        except Exception:
            _cfg = {}
    return _cfg


def _post_json(host, port, path, payload, timeout=TIMEOUT_S):
    """Minimal HTTP/1.1 POST with a JSON body. Returns the parsed reply."""
    body = json.dumps(payload).encode()
    s = socket.socket()
    try:
        s.settimeout(timeout)
        s.connect((host, port))
        s.send(("POST %s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\n"
                "Content-Length: %d\r\nConnection: close\r\n\r\n" % (path, host, len(body))).encode())
        s.send(body)
        raw = b""
        while True:
            chunk = s.recv(512)
            if not chunk:
                break
            raw += chunk
    finally:
        try:
            s.close()
        except Exception:
            pass
    head, _, data = raw.partition(b"\r\n\r\n")
    # chunked or plain: the bridge sends Content-Length, so a plain body is fine
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return {"reply": "(unreadable reply from the bridge: %r)" % raw[:80]}


class ChatScreen(Screen):
    title = "CHAT"
    hints = ("type   ENT: send   j/k scroll", "DEL: erase / back   needs the Pi up")

    @property
    def tick_repaint(self):
        """True while a request is in flight (so the elapsed counter moves) and
        once a result has landed (so the ANSWER gets drawn).

        That second half was missing: the worker cleared `pending`, which turned
        the repaint off, and the reply sat in memory invisible until the next
        keypress. The screen froze on "thinking 18s" with the answer already
        received.
        """
        return self.pending or self._needs_paint

    def __init__(self):
        self.text = ""              # what is being typed
        self.scroll = 0
        self.upper = False
        self.sym = False
        self.pending = False       # a request is in flight
        self.started = 0
        self.seconds = 0.0
        self.progress = ""         # e.g. "retry 2/3 (14s)"
        self._needs_paint = False  # a result arrived and must be drawn
        self.messages = []          # (who, text)
        self.load()

    def _set_progress(self, text):
        self.progress = text

    # -- transcript ------------------------------------------------------------
    def load(self):
        try:
            with open(CHAT_LOG) as fh:
                for line in fh.read().splitlines()[-40:]:
                    who, _, msg = line.partition(": ")
                    if msg:
                        self.messages.append((who, msg))
        except Exception:
            pass

    def _append(self, who, text):
        self.messages.append((who, text))
        try:
            with open(CHAT_LOG, "a") as fh:
                fh.write("%s: %s\n" % (who, text.replace("\n", " ")))
        except Exception:
            pass

    # -- sending (never blocks) ------------------------------------------------
    def send(self):
        text = self.text.strip()
        if not text or self.pending:
            return
        self.text = ""
        self._append("you", text)
        self.scroll = 0
        self.pending = True
        self.started = time.ticks_ms()
        cfg = config()
        host, token = cfg.get("pi"), cfg.get("token")
        screen = self

        def worker():
            """Ask the agent, retrying: this link drops packets intermittently
            (EHOSTUNREACH mid-session, both directions failing at random), so a
            single attempt made a healthy system look broken."""
            reply = None
            last = None
            for attempt in range(3):
                try:
                    if not host or not token:
                        reply = "(no pi/token in /wifi.json)"
                        break
                    res = _post_json(host, BRIDGE_PORT, "/chat",
                                     {"token": token, "text": text})
                    reply = res.get("reply") or "(empty reply)"
                    break
                except Exception as exc:                            # noqa: BLE001
                    last = exc
                    screen._set_progress("retry %d/3 (%.0fs)" % (
                        attempt + 1, time.ticks_diff(time.ticks_ms(), screen.started) / 1000.0))
                    if attempt < 2:
                        time.sleep(3)
            if reply is None:
                reply = ("(could not reach the Pi after 3 tries: %s)\n"
                         "The device's WiFi link is flaky - check the Device screen "
                         "for its address, or try again." % last)
            screen._append("hermes", reply)
            screen._needs_paint = True     # draw the answer (see tick_repaint)
            screen.pending = False
            screen.progress = ""
            screen.scroll = 0

        try:
            import _thread
            _thread.start_new_thread(worker, ())
        except Exception:
            # no threads: fall back to doing it inline (slow but correct)
            worker()

    # -- input -----------------------------------------------------------------
    def handle(self, key, app):
        kind, val = key
        if kind in ("char", "digit"):
            if self.pending:
                return False
            self.text += apply_layer(val, sym=self.sym, upper=self.upper)
            return True
        if kind == "ctl":
            if val == "alt":
                self.upper = not self.upper
                return True
            if val == "sym":
                self.sym = not self.sym
                return True
            if val == "space":
                if not self.pending:
                    self.text += " "
                return True
            if val == "enter":
                self.send()
                return True
            if val == "back":
                if self.pending:
                    return False
                if self.text:
                    self.text = self.text[:-1]
                    return True
                app.pop()               # nothing to erase: back to the launcher
                return True
            return False
        return False

    # -- drawing ---------------------------------------------------------------
    def _wrapped(self):
        out = []
        for who, msg in self.messages:
            prefix = "you: " if who == "you" else ""
            for i, para in enumerate(msg.split("\n")):
                line = (prefix + para) if i == 0 else para
                if not line:
                    out.append("")
                    continue
                while len(line) > COLS:
                    out.append(line[:COLS])
                    line = line[COLS:]
                out.append(line)
            out.append("")
        return out or [""]

    def render(self, fb, app):
        self._needs_paint = False          # whatever arrived is now on the glass
        if self.pending:
            self.seconds = time.ticks_diff(time.ticks_ms(), self.started) / 1000.0
            right = self.progress or ("thinking %.0fs" % self.seconds)
        else:
            right = "%d msgs" % len(self.messages)
        draw_chrome(fb, self, app, right=right)

        lines = self._wrapped()
        max_scroll = max(0, len(lines) - ROWS)
        self.scroll = min(self.scroll, max_scroll)
        end = len(lines) - self.scroll
        window = lines[max(0, end - ROWS):end]
        y = HEADER_H + 6
        for line in window:
            fb.text(line, LEFT, y, 0)
            y += LINE_H

        # input line, separated from the transcript
        iy = HEIGHT - FOOTER_H - 20
        fb.hline(LEFT, iy - 4, WIDTH - 2 * LEFT, 0)
        shown = self.text[-(COLS - 2):]
        fb.text(shown, LEFT, iy, 0)
        cx = LEFT + len(shown) * CELL
        if cx + CELL <= WIDTH - LEFT:
            fb.fill_rect(cx, iy, CELL, CELL, 0)
