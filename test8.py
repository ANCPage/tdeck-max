# Test 8: same A/B, but the two frames are now impossible to confuse.
#
#   mpremote connect /dev/ttyACM0 run test8.py
#
#   Frame ONE: title "PAGE ONE", text "ABC 123", big black square TOP-LEFT,
#              drawn as MONO_HMSB (the bit order the library has used so far)
#   Frame TWO: title "PAGE TWO", text "ABC 123", big black square BOTTOM-RIGHT,
#              drawn as MONO_HLSB (opposite intra-byte bit order)
#
# Ask: (a) which page is on the glass, (b) does the lettering read normally?

import time

import framebuf

from tdeckmax.board import Board
from tdeckmax.epd import UC8253

PW, PH = 240, 320
ROW = PW // 8

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)


def make_frame(fmt, title, square_top_left):
    frame = bytearray(ROW * PH)
    fb = framebuf.FrameBuffer(frame, PW, PH, fmt)
    fb.fill(1)
    fb.rect(0, 0, PW, PH, 0)
    fb.text(title, 60, 24, 0)
    fb.text("ABC 123", 56, 120, 0)
    fb.text("LEFT", 12, 180, 0)
    fb.text("RIGHT", 172, 180, 0)
    if square_top_left:
        fb.fill_rect(12, 40, 60, 60, 0)
    else:
        fb.fill_rect(PW - 72, PH - 100, 60, 60, 0)
    return frame


FRAMES = (
    ("PAGE ONE / HMSB / square TOP-LEFT", make_frame(framebuf.MONO_HMSB, "PAGE ONE", True)),
    ("PAGE TWO / HLSB / square BOTTOM-RIGHT", make_frame(framebuf.MONO_HLSB, "PAGE TWO", False)),
)

for label, frame in FRAMES:
    print("drawing:", label)
    for attempt in (1, 2):
        t0 = time.ticks_ms()
        epd.full_refresh(frame)
        print("   pass %d: %d ms" % (attempt, time.ticks_diff(time.ticks_ms(), t0)))
    time.sleep_ms(3000)

print("ASK: which page is showing, and does the lettering read normally?")
