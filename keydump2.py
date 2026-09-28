# Keyboard bring-up v2: watch TWO channels at once, so "nothing reached the
# chip" can be told apart from "the chip saw it but our decode failed".
#
#   mpremote connect /dev/ttyACM0 run keydump2.py
#
#   channel 1: the key-event FIFO (what the scanner decoded)
#   channel 2: the raw key-matrix pin levels (GPIO_DAT_STAT 0x14/0x15/0x16),
#              printed whenever they change from their resting value
#
# Prints a heartbeat every 20 s, so silence is distinguishable from a dead loop.

import time

from tdeckmax.board import Board
from tdeckmax.tca8418 import TCA8418

RUN_SECONDS = 240

board = Board()
board.release_resets()
kb = TCA8418(board.i2c)
print("keyboard begin():", kb.begin())

resting = (kb._read(0x14), kb._read(0x15), kb._read(0x16))
print("resting pin levels (0x14,0x15,0x16) = 0x%02x 0x%02x 0x%02x" % resting)
print("=== TYPE NOW (firm single presses, ~1 per second) ===")

events = 0
pin_changes = 0
t0 = time.ticks_ms()
next_beat = 20000
while time.ticks_diff(time.ticks_ms(), t0) < RUN_SECONDS * 1000:
    # channel 1: decoded events
    while kb.available():
        raw = kb.get_event()
        events += 1
        from tdeckmax import keys
        print("EVENT raw=%3d (0x%02x) -> %s" % (raw, raw, keys.decode_raw(raw, letters=True)))

    # channel 2: raw matrix pin levels
    levels = (kb._read(0x14), kb._read(0x15), kb._read(0x16))
    if levels != resting:
        pin_changes += 1
        print("PINS  0x%02x 0x%02x 0x%02x  (resting was 0x%02x 0x%02x 0x%02x)"
              % (levels + resting))
        time.sleep_ms(120)

    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    if elapsed > next_beat:
        print("... %ds: %d events, %d pin changes" % (elapsed // 1000, events, pin_changes))
        next_beat += 20000

    time.sleep_ms(8)

print("=== done: %d events, %d pin-level changes ===" % (events, pin_changes))
