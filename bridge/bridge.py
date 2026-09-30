#!/usr/bin/env python3
"""Hermes bridge: lets the T-Deck Max talk to the agent over the LAN.

    POST /chat   {"token": "...", "text": "hello"}
      ->        {"reply": "...", "seconds": 12.3, "session": "2026..."}

The agent call is deliberately a *named continuing session* (`--continue
tdeck`), so the device has one ongoing conversation with memory, and the message
text is passed via stdin (`--query-file -`) so nothing is ever shell-interpreted.

Run:  python3 ~/tdeck-max/bridge/bridge.py          (listens on 0.0.0.0:8097)
Log:  ~/tdeck-max/bridge/bridge.log
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8097
WIFI = os.path.expanduser("~/tdeck-max/wifi.json")
LOG = os.path.expanduser("~/tdeck-max/bridge/bridge.log")
BRIDGE_HOME = os.path.expanduser("~/tdeck-max/bridge")

SESSION = "tdeck"            # one ongoing conversation for the device
RUN_BUDGET = "180"           # seconds the agent may work per message
MAX_TURNS = "20"
LOCK = threading.Lock()      # one agent run at a time


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def token():
    try:
        return json.load(open(WIFI))["token"]
    except Exception:
        return None


def clean(text):
    """Make the agent's answer fit an e-ink screen: drop the session banner and
    the light markdown that would otherwise show up as literal asterisks."""
    lines = []
    for ln in text.splitlines():
        low = ln.strip().lower()
        if low.startswith("session_id:") or "resumed session" in low:
            continue                      # CLI banner, not part of the answer
        lines.append(ln)
    out = "\n".join(lines).strip()
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)     # bold
    out = re.sub(r"`([^`]+)`", r"\1", out)         # inline code
    out = re.sub(r"^\s*#{1,6}\s*", "", out, flags=re.M)   # headings
    return out.strip()


def ask_hermes(text, timeout=240):
    """One turn of the continuing session. Returns (reply, seconds)."""
    cmd = [
        "hermes", "chat", "-Q",
        "--continue", SESSION, "--create-if-missing",
        "--query-file", "-",
        "--run-budget", RUN_BUDGET,
        "--max-turns", MAX_TURNS,
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, input=text.encode(), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout,
                          cwd=BRIDGE_HOME)
    return clean(proc.stdout.decode("utf-8", "replace")), time.time() - t0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):        # quieter default logging
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw.decode("utf-8", "replace") or "{}")
        except Exception:
            self._send({"error": "bad json"}, 400)
            return
        if req.get("token") != token():
            log("rejected: bad token from %s" % self.client_address[0])
            self._send({"error": "bad token"}, 403)
            return
        text = (req.get("text") or "").strip()
        if not text:
            self._send({"error": "empty message"}, 400)
            return
        log("ask from %s: %r" % (self.client_address[0], text[:80]))
        try:
            with LOCK:                      # one run at a time: keep it simple
                reply, secs = ask_hermes(text)
            log("reply in %.1fs: %r" % (secs, reply[:80]))
            self._send({"reply": reply, "seconds": round(secs, 1)})
        except subprocess.TimeoutExpired:
            log("TIMEOUT after %ss" % 240)
            self._send({"reply": "(timed out - the agent is still working; try again)",
                        "seconds": 240})
        except Exception as exc:                                   # noqa: BLE001
            log("ERROR: %r" % (exc,))
            self._send({"reply": "(bridge error: %s)" % exc}, 500)

    def do_GET(self):
        self._send({"ok": True, "service": "hermes bridge", "port": PORT})


if __name__ == "__main__":
    os.makedirs(BRIDGE_HOME, exist_ok=True)
    if not token():
        sys.exit("no token in %s" % WIFI)
    log("hermes bridge on 0.0.0.0:%d  (session %r)" % (PORT, SESSION))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
