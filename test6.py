# Test 6: one big asymmetric glyph, no text, so the answer is unambiguous.
#
#   mpremote connect /dev/ttyACM0 run test6.py
#
# Drawn: a large thick 'L' -- upright spine on the LEFT, foot extending RIGHT.
# Exactly one of four things will be on the glass, and they are visually
# unmistakable:
#   A) normal L      (spine left, foot pointing right)        -> no transform
#   B) mirror of L   (spine right, foot pointing left)        -> x-flip
#   C) upside-down L (spine right at top, foot pointing left) -> 180 rotation
#   D) sideways L    (spine along the top/bottom)             -> 90 rotation
#
# Three refreshes so any ghost of the previous frame is driven away first.

import time

import framebuf

from tdeckmax.board import Board
from tdeckmax.epd import UC8253

PW, PH = 240, 320
ROW = PW // 8

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)

frame = bytearray(ROW * PH)
fb = framebuf.FrameBuffer(frame, PW, PH, framebuf.MONO_HLSB)
fb.fill(1)

THICK = 34
fb.fill_rect(60, 60, THICK, 200, 0)          # spine (vertical, on the left)
fb.fill_rect(60, 226, 120, THICK, 0)         # foot extends to the RIGHT

for attempt in (1, 2, 3):
    t0 = time.ticks_ms()
    epd.full_refresh(frame)
    print("big-L pass %d: %d ms" % (attempt, time.ticks_diff(time.ticks_ms(), t0)))

print("ASK: A normal / B mirrored / C upside-down / D sideways?")
