# Notes: a keyboard-first text page -- the first real app on the framework.
#
# Typing appends; ENT = newline; SPACE = space; DEL = backspace (when the page is
# already empty it hands control back to the launcher). j/k scroll older lines.
#
# It draws only through the shared Screen API, so the identical file runs in the
# host simulator (sim/preview.py) and on the device.

from tdeckmax import CELL, HEIGHT, WIDTH
from tdeckmax.screen import FOOTER_H, HEADER_H, Screen, draw_chrome

LEFT = 8
LINE_H = 12
COLS = (WIDTH - 2 * LEFT) // CELL                      # characters per line
ROWS = (HEIGHT - HEADER_H - FOOTER_H - 10) // LINE_H   # visible lines


class NotesScreen(Screen):
    title = "NOTES"
    hints = ("type to write   ENT: newline   SPACE: space",
             "DEL: backspace   j/k: scroll   DEL on empty: back")

    def __init__(self):
        self.text = ""
        self.scroll = 0        # extra lines scrolled up from the bottom

    # -- editing ---------------------------------------------------------------
    def _insert(self, s):
        self.text += s
        self.scroll = 0

    def handle(self, key, app):
        kind, val = key
        if kind in ("char", "digit"):
            self._insert(val)
            return True
        if kind == "ctl":
            if val == "space":
                self._insert(" ")
                return True
            if val == "enter":
                self._insert("\n")
                return True
            if val == "back":
                if self.text:
                    self.text = self.text[:-1]
                    return True
                return False          # empty page: let the launcher handle it
            return False
        if kind == "char" and val == "j":
            self.scroll += 1
            return True
        if kind == "char" and val == "k":
            self.scroll = max(0, self.scroll - 1)
            return True
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
        draw_chrome(fb, self, app, right="%d ch" % len(self.text))
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
