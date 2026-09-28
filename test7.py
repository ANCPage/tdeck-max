# Test 7: A/B the framebuf byte order on the real panel.
#
#   mpremote connect /dev/ttyACM0 run test7.py
#
# Frame 1 = MONO_HMSB (what the library has used so far)
# Frame 2 = MONO_HLSB (opposite intra-byte bit order)
# Same text in both. Whichever one reads correctly is the format the panel wants.
#
# Coarse shapes cannot tell these apart (a filled bar spans whole bytes, so a
# bit-order flip is invisible); 8x8 font glyphs live inside ONE byte, so they
# reveal it immediately.

import time

import framebuf

from tdeckmax.board import Board
from tdeckmax.epd import UC8253

PW, PH = 240, 320
ROW = PW // 8

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)


def make_frame(fmt):
    frame = bytearray(ROW * PH)
    fb = framebuf.FrameBuffer(frame, PW, PH, fmt)
    fb.fill(1)
    fb.rect(0, 0, PW, PH, 0)
    fb.text("FRAME ONE", 48, 40, 0)
    fb.text("ABC 123", 48, 80, 0)
    fb.text("LEFT", 20, 130, 0)
    fb.text("RIGHT", 168, 130, 0)
    return frame


for label, fmt in (("HMSB (old)", framebuf.MONO_HMSB), ("HLSB (new)", framebuf.MONO_HLSB)):
    frame = make_frame(fmt)
    for attempt in (1, 2):
        t0 = time.ticks_ms()
        epd.full_refresh(frame)
        print("%-12s pass %d: %d ms" % (label, attempt, time.ticks_diff(time.ticks_ms(), t0)))
    time.sleep_ms(2500)          # long enough to look at it

print("ASK: which frame -- the FIRST or the SECOND -- had readable text?")
