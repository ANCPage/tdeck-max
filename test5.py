# Test 5: orientation/mirroring probe that a human can answer in words.
#
#   mpremote connect /dev/ttyACM0 run test5.py
#
# Every element is asymmetric on purpose, so each answer maps to one transform:
#   * a big 'F'  -> mirrored if its bars point left instead of right
#   * the words LEFT / RIGHT on the same row -> swapped if the row is flipped
#   * the words TOP / BOTTOM -> swapped if the row order is reversed
#   * the text ABC 123 -> tells us whether glyphs themselves are mirrored

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

# 2px frame border
fb.rect(0, 0, PW, PH, 0)
fb.rect(1, 1, PW - 2, PH - 2, 0)

# big letter F (spine + two bars to the RIGHT when correct)
fb.fill_rect(40, 74, 14, 90, 0)      # spine
fb.fill_rect(40, 74, 60, 14, 0)      # top bar
fb.fill_rect(40, 116, 44, 14, 0)     # middle bar
fb.text("big F", 120, 116, 0)

# glyph readability
fb.text("ABC 123", 40, 200, 0)
fb.text("abcdefghij", 40, 216, 0)

# side words on one row
fb.text("LEFT", 8, 260, 0)
fb.text("RIGHT", 184, 260, 0)

# top / bottom words
fb.text("TOP", 8, 32, 0)
fb.text("BOTTOM", 8, 288, 0)

for attempt in (1, 2):
    t0 = time.ticks_ms()
    epd.full_refresh(frame)
    print("orientation probe pass %d: %d ms" % (attempt, time.ticks_diff(time.ticks_ms(), t0)))

print("ASK: read the screen and answer in words.")
