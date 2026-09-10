# Host stand-in for MicroPython's framebuf.FrameBuffer — the subset our screens
# use (fill, rect, fill_rect, hline, line, text). Same convention as the panel:
# 1 = white paper, 0 = black ink.  Renders to PNG so we can SEE the UI on the Pi
# weeks before hardware exists; on the device this class is replaced by framebuf.

import os
from PIL import Image, ImageDraw, ImageFont

WHITE, BLACK = 255, 0
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 12          # ≈7.2px advance, close to the device's 8px glyph cell


class PilFrameBuffer:
    def __init__(self, width, height, font_path=FONT_PATH, font_size=FONT_SIZE):
        self.width, self.height = width, height
        self.img = Image.new("L", (width, height), WHITE)
        self.d = ImageDraw.Draw(self.img)
        self.font = ImageFont.truetype(font_path, font_size)

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _c(v):
        return WHITE if v else BLACK

    # -- framebuf API subset ----------------------------------------------
    def fill(self, v):
        self.d.rectangle([0, 0, self.width - 1, self.height - 1], fill=self._c(v))

    def fill_rect(self, x, y, w, h, v):
        self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=self._c(v))

    def rect(self, x, y, w, h, v):
        self.d.rectangle([x, y, x + w - 1, y + h - 1], outline=self._c(v))

    def hline(self, x, y, w, v):
        self.d.line([x, y, x + w - 1, y], fill=self._c(v))

    def line(self, x1, y1, x2, y2, v):
        self.d.line([x1, y1, x2, y2], fill=self._c(v))

    def text(self, s, x, y, v):
        # -3 aligns PIL's taller glyphs (12px) with the device's 8px cell top,
        # so labels sit above meter boxes and the footer fits on screen.
        self.d.text((x, y - 3), s, font=self.font, fill=self._c(v))

    # -- output -------------------------------------------------------------
    def save(self, path):
        self.img.convert("1").save(path)

    def tobytes_msb(self):
        """Pack to 1 bpp, row-major, MSB first — same layout as the panel frame."""
        img = self.img.point(lambda p: 255 if p > 127 else 0).convert("1")
        row_bytes = self.width // 8
        out = bytearray(row_bytes * self.height)
        px = img.load()
        for y in range(self.height):
            base = y * row_bytes
            for x in range(self.width):
                if px[x, y]:
                    out[base + (x >> 3)] |= 0x80 >> (x & 7)
        return out
