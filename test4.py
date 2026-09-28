# Test 4: native-portrait geometry probe.
#
# Vendor truth (examples/Elink_paper/GDEQ031T10_Arduino/Display_EPD_W21.h):
#     #define EPD_WIDTH  240
#     #define EPD_HEIGHT 320
# i.e. the panel's frame is 240 px wide x 320 px tall = 30 bytes per row.
# A uniform fill looks identical under any row width; a split frame does not
# (that is how we caught it: the split showed up as bars).
#
# This frame is drawn NATIVELY in 240x320 with two unmistakable markers, to find
# out which way the panel's axes land on the device as Austin holds it.
#
#   mpremote connect /dev/ttyACM0 run test4.py

import time

import framebuf

from tdeckmax.board import Board
from tdeckmax.epd import UC8253

PW, PH = 240, 320          # panel native portrait
ROW = PW // 8              # 30 bytes per row

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)

frame = bytearray(ROW * PH)
fb = framebuf.FrameBuffer(frame, PW, PH, framebuf.MONO_HLSB)
fb.fill(1)                                   # white
fb.rect(0, 0, PW, PH, 0)
fb.rect(1, 1, PW - 2, PH - 2, 0)
fb.fill_rect(4, 4, 24, 24, 0)                # marker A: native top-left
fb.text("A", 36, 10, 0)
fb.fill_rect(PW - 44, PH - 44, 40, 40, 0)    # marker B: native bottom-right
fb.text("B", PW - 44, PH - 60, 0)
fb.line(PW // 2, 0, PW // 2, PH, 0)          # centre crosshair
fb.line(0, PH // 2, PW, PH // 2, 0)
fb.text("native 240x320", 76, 8, 0)

for attempt in (1, 2):
    t0 = time.ticks_ms()
    epd.full_refresh(frame)
    print("native-portrait frame pass %d: %d ms" % (attempt, time.ticks_diff(time.ticks_ms(), t0)))
    time.sleep_ms(400)

print("ASK: where are the two black squares?")
print("  is 'A' readable and upright, and where does it sit?")
