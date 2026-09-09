# E-paper screen + refresh policy. Rendering uses MicroPython framebuf
# (MONO_HMSB: bit 1 = white paper, 0 = black ink) — the same bit convention the
# UC8253 driver expects, so the frame buffer feeds straight into the panel.
#
# Font note: framebuf's built-in font is 8x8. Fine for scaffold UIs; a real
# app should swap in a bigger bitmap font (tdeckmax/fonts.py later).

import framebuf
from tdeckmax.epd import UC8253

WIDTH, HEIGHT = 320, 240
CELL = 8                     # builtin font: 8px cell
MAX_FAST_BETWEEN_FULL = 10   # full refresh after this many fast ones (anti-ghost)


class EPaperUI:
    def __init__(self, epd: UC8253):
        self.epd = epd
        self.buf = bytearray(WIDTH * HEIGHT // 8)
        self.fb = framebuf.FrameBuffer(self.buf, WIDTH, HEIGHT, framebuf.MONO_HMSB)
        self._fast_since_full = 0

    # -- primitives -----------------------------------------------------------
    def clear(self) -> None:          # blank white page
        self.fb.fill(1)

    def ink_text(self, s, x, y) -> None:
        self.fb.text(s, x, y, 0)

    def ink_box(self, x, y, w, h, filled=True) -> None:
        if filled:
            self.fb.fill_rect(x, y, w, h, 0)
        else:
            self.fb.rect(x, y, w, h, 0)

    def paper_text_in_ink_box(self, s, x, y, w, h) -> None:
        """White (paper) text centred inside a black box."""
        self.ink_box(x, y, w, h, filled=True)
        self.fb.text(s, x + (w - len(s) * CELL) // 2, y + (h - CELL) // 2, 1)

    def ink_text_in_box(self, s, x, y, w, h) -> None:
        """Black text horizontally centred inside an empty box."""
        self.fb.text(s, x + (w - len(s) * CELL) // 2, y + (h - CELL) // 2, 0)

    # -- refresh policy --------------------------------------------------------
    def render(self, full: bool) -> None:
        if full or self._fast_since_full >= MAX_FAST_BETWEEN_FULL:
            self.epd.full_refresh(self.buf)
            self._fast_since_full = 0
        else:
            self.epd.fast_refresh(self.buf)
            self._fast_since_full += 1
