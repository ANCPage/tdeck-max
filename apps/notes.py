# Notes: a keyboard-first text page -- the first real app on the framework.
#
# Typing appends; ENT = newline; SPACE = space; DEL = backspace (when the page is
# already empty it hands control back to the launcher). j/k scroll older lines.
#
# It draws only through the shared Screen API, so the identical file runs in the
# host simulator (sim/preview.py) and on the device.

from tdeckmax import CELL, HEIGHT, WIDTH
from tdeckmax.keys import apply_layer
from tdeckmax.screen import FOOTER_H, HEADER_H, Screen, draw_chrome

LEFT = 8
LINE_H = 12
COLS = (WIDTH - 2 * LEFT) // CELL                      # characters per line
ROWS = (HEIGHT - HEADER_H - FOOTER_H - 10) // LINE_H   # visible lines
NOTES_PATH = "/notes.txt"


class NotesScreen(Screen):
    title = "NOTES"
    hints = ("type   ENT: newline   SPACE: space",
             "ALT: caps   SYM: 123/+   DEL: backspace")

    def __init__(self, path=NOTES_PATH):
        self.path = path
        self.text = ""
        self.load()
        self.scroll = 0        # extra lines scrolled up from the bottom
        self.upper = False     # ALT toggles caps (as the factory UI does)
        self.sym = False       # SYM layer: digits + punctuation
        self.tick = 0          # repaint counter, shown in the header (liveness)
        self.status = ""       # battery + wifi readout, set by main.py
        self.dirty = False     # unsaved edits; main.py flushes after a pause

    # -- persistence -----------------------------------------------------------
    def load(self):
        """Read the page back after a reset. Never fatal: a missing or damaged
        file just means an empty page."""
        try:
            with open(self.path) as fh:
                self.text = fh.read()
        except Exception:
            self.text = ""

    def save(self):
        """Write the page to flash. Called only when the typing has stopped:
        one write per pause, not one per keystroke (flash wear)."""
        try:
            with open(self.path, "w") as fh:
                fh.write(self.text)
            self.dirty = False
            return True
        except Exception:
            return False

    # -- editing ---------------------------------------------------------------
    def _insert(self, s):
        self.text += s
        self.scroll = 0
        self.dirty = True

    def _delete(self):
        self.text = self.text[:-1]
        self.dirty = True

    def handle(self, key, app):
        kind, val = key
        if kind in ("char", "digit"):
            self._insert(apply_layer(val, sym=self.sym, upper=self.upper))
            return True
        if kind == "ctl":
            if val == "alt":
                self.upper = not self.upper
                return True
            if val == "sym":
                self.sym = not self.sym
                return True
            if val == "space":
                self._insert(" ")
                return True
            if val == "enter":
                self._insert("\n")
                return True
            if val == "back":
                if self.text:
                    self._delete()
                    return True
                app.pop()             # empty page: DEL steps back to the launcher
                return True
            return False
        return False

    # -- drawing ---------------------------------------------------------------
    def _lines(self):
        """Wrap the buffer into screen lines (simple fixed-width wrap)."""
        out = []
        for para in self.text.split("\n"):
            if not para:
                out.append("")
                continue
            while len(para) > COLS:
                out.append(para[:COLS])
                para = para[COLS:]
            out.append(para)
        return out or [""]

    def render(self, fb, app):
        self.tick += 1
        flags = ("SYM " if self.sym else "") + ("CAPS " if self.upper else "")
        marker = "* " if self.dirty else ""      # * = not yet written to flash
        draw_chrome(fb, self, app,
                    right="%s%s%s%d ch  t%d" % (self.status, marker, flags,
                                                len(self.text), self.tick))
        lines = self._lines()
        max_scroll = max(0, len(lines) - ROWS)
        self.scroll = min(self.scroll, max_scroll)
        start = max(0, len(lines) - ROWS - self.scroll)
        window = lines[start:start + ROWS]

        y = HEADER_H + 8
        for line in window:
            fb.text(line, LEFT, y, 0)
            y += LINE_H

        # cursor: solid block after the last character of the last line
        last = window[-1] if window else ""
        cx = LEFT + len(last) * CELL
        cy = HEADER_H + 8 + (len(window) - 1) * LINE_H
        if cx + CELL <= WIDTH - LEFT:
            fb.fill_rect(cx, cy, CELL, CELL, 0)
        else:
            fb.fill_rect(LEFT, cy + LINE_H, CELL, CELL, 0)
