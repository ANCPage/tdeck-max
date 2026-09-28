# kbtest.py — "is the panel alive?" and "does the keyboard report anything?"
# in one run, with no timing pressure on the operator.
#
#   mpremote connect /dev/ttyACM0 run kbtest.py
#
# The panel redraws every 5 s with a rising tick counter and the event count.
#   * tick rises, events stay 0   -> loop + panel fine, keyboard silent
#   * tick frozen                 -> the program is not running at all
# Any key event replaces the display with its raw code and is appended to
# /kb2.log. Also pulses the keyboard reset line (XL9555 P0.9, LOW = reset) and
# re-inits the controller afterwards, in case the chip latched up.

import time

import framebuf

from tdeckmax import HEIGHT, WIDTH, keys
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.tca8418 import TCA8418

RUN_SECONDS = 150
ROW = WIDTH // 8

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)
buf = bytearray(ROW * HEIGHT)

print("pulsing keyboard reset (XL9555 P0.9 LOW -> HIGH)")
board.gate(9, False)
time.sleep_ms(60)
board.gate(9, True)
time.sleep_ms(250)

kb = TCA8418(board.i2c)
print("kb.begin() ->", kb.begin())
print("CFG=0x%02x KP_GPIO=0x%02x 0x%02x 0x%02x LCK_EC=0x%02x"
      % (kb._read(0x01), kb._read(0x1D), kb._read(0x1E), kb._read(0x1F), kb._read(0x03)))

paints = [0]


def paint(l1, l2="", l3=""):
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
    fb.fill(1)
    fb.rect(0, 0, WIDTH, HEIGHT, 0)
    fb.text("KB TEST", 12, 12, 0)
    fb.text(l1, 12, 60, 0)
    fb.text(l2, 12, 84, 0)
    fb.text(l3, 12, 108, 0)
    paints[0] += 1
    if paints[0] % 6 == 0:
        epd.full_refresh(buf)          # clear ghosting every 6th paint
    else:
        epd.fast_refresh(buf)


log = open("/kb2.log", "a")
log.write("--- run ---\n")
log.flush()

events = 0
ticks = 0
t0 = time.ticks_ms()
paint("alive, tick 0", "events: 0", "press keys now")

while time.ticks_diff(time.ticks_ms(), t0) < RUN_SECONDS * 1000:
    if kb.available():
        raw = kb.get_event()
        events += 1
        line = "raw=%d (0x%02x) -> %s" % (raw, raw, keys.decode_raw(raw, letters=True))
        print(line)
        log.write(line + "\n")
        log.flush()
        paint("EVENT", line[:26], "count %d" % events)
    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    if elapsed // 5000 > ticks:
        ticks = elapsed // 5000
        paint("alive, tick %d" % ticks, "events: %d" % events, "press keys now")
    time.sleep_ms(10)

print("=== done: %d events after %ds ===" % (events, RUN_SECONDS))
