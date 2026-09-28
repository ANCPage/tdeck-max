# Keyboard bring-up: dump every raw FIFO event alongside our decode, so the
# real keymap can be checked against the vendor-derived table in keys.py.
#
#   mpremote connect /dev/ttyACM0 run keydump.py
#
# Type on the device while this runs. Nothing needs to be sent back.
# Prints both press and release events, so this also settles the
# PRESS_IS_HIGH knob in keys.py (presses 129..163 vs 1..35).

import time

from tdeckmax import keys
from tdeckmax.board import Board
from tdeckmax.tca8418 import TCA8418

RUN_SECONDS = 150

board = Board()
board.release_resets()
kb = TCA8418(board.i2c)
print("keyboard begin():", kb.begin())
print("presses expected as 129..163 (PRESS_IS_HIGH=%s)" % keys.PRESS_IS_HIGH)
print("=== TYPE NOW ===")

raws = []
presses = []
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < RUN_SECONDS * 1000:
    if kb.available():
        raw = kb.get_event()
        raws.append(raw)
        dec = keys.decode_raw(raw, letters=True)
        rc = key = None
        if keys.PRESS_MIN <= raw <= keys.PRESS_MAX:
            rc = keys.rowcol_from_code(raw - keys.PRESS_MIN)
            if 0 <= rc[0] < keys.ROWS and 0 <= rc[1] < keys.COLS:
                key = keys.KEYMAP[rc[0]][rc[1]]
            presses.append(raw)
        print("raw=%3d 0x%02x rc=%-8s key=%-5s -> %s" % (raw, raw, rc, key, dec))
    time.sleep_ms(8)

print("=== done: %d events (%d in press range) ===" % (len(raws), len(presses)))
if raws:
    print("raw range: %d..%d" % (min(raws), max(raws)))
