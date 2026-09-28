# Hardware bring-up for the T-Deck Max: I2C inventory -> XL9555 gates -> first frame.
#
#   mpremote connect /dev/ttyACM0 run bringup.py
#
# Everything that can be measured without eyes is measured and printed here
# (I2C addresses, XL9555 port bytes, BUSY-pin waveform, refresh timing), so the
# operator only has to confirm what is on the glass.

import time

import framebuf

from tdeckmax import WIDTH, HEIGHT
from tdeckmax.board import Board
from tdeckmax.epd import UC8253

EXPECTED = {0x18: "ES8311 codec", 0x1a: "CST3530 touch", 0x20: "XL9555 expander",
            0x28: "BHI260AP IMU", 0x34: "TCA8418 keyboard", 0x55: "BQ27220 fuel gauge",
            0x5a: "DRV2605 haptics", 0x6a: "SY6970 charger"}


def busy_pattern(pin, ms=400, step=20):
    """Sample a pin so BUSY polarity/idle level is visible as a string."""
    out = []
    for _ in range(ms // step):
        out.append("1" if pin.value() else "0")
        time.sleep_ms(step)
    return "".join(out)


print("=== T-Deck Max bring-up ===")
t_start = time.ticks_ms()

# --- stage A: board assembly + I2C inventory --------------------------------
t0 = time.ticks_ms()
board = Board()
print("A. board assembled in %d ms" % time.ticks_diff(time.ticks_ms(), t0))
found = board.i2c.scan()
print("A. I2C devices found: %s" % [hex(a) for a in found])
for addr in sorted(found):
    print("     %s  %s" % (hex(addr), EXPECTED.get(addr, "<-- unexpected address>")))
for addr, name in EXPECTED.items():
    if addr not in found:
        print("     MISSING %s (%s)" % (hex(addr), name))

# --- stage B: XL9555 gatekeeper --------------------------------------------
print("B. XL9555 port0/port1 before: 0x%02x 0x%02x"
      % (board.expander.read_port(0), board.expander.read_port(1)))
board.release_resets()
time.sleep_ms(20)
print("B. XL9555 port0/port1 after resets released: 0x%02x 0x%02x"
      % (board.expander.read_port(0), board.expander.read_port(1)))

# --- stage C: the e-paper --------------------------------------------------
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
print("C. BUSY idle samples (1=high, 0=low, 20ms apart): %s" % busy_pattern(board.epd_busy))

frame = bytearray(epd.FRAME)
fb = framebuf.FrameBuffer(frame, WIDTH, HEIGHT, framebuf.MONO_HLSB)
fb.fill(1)                                          # 1 = white
fb.rect(0, 0, WIDTH, HEIGHT, 0)                     # black border
fb.rect(1, 1, WIDTH - 2, HEIGHT - 2, 0)
fb.fill_rect(4, 4, 24, 24, 0)                       # TOP-LEFT black square
fb.fill_rect(WIDTH - 44, HEIGHT - 44, 40, 40, 0)    # BOTTOM-RIGHT black square
fb.line(WIDTH // 2, 0, WIDTH // 2, HEIGHT, 0)       # vertical crosshair
fb.line(0, HEIGHT // 2, WIDTH, HEIGHT // 2, 0)      # horizontal crosshair
fb.text("T-DECK MAX", 116, 44, 0)
fb.text("MicroPython", 116, 62, 0)
fb.text("BRINGUP OK", 116, 80, 0)
fb.text("TL", 32, 6, 0)
fb.text("mpx 1.29", 246, HEIGHT - 14, 0)

t0 = time.ticks_ms()
try:
    epd.full_refresh(frame)
    print("C. full_refresh returned in %d ms" % time.ticks_diff(time.ticks_ms(), t0))
except Exception as exc:
    print("C. full_refresh FAILED after %d ms: %s"
          % (time.ticks_diff(time.ticks_ms(), t0), exc))
print("C. BUSY samples right after refresh: %s" % busy_pattern(board.epd_busy))

print("=== done in %d ms total ===" % time.ticks_diff(time.ticks_ms(), t_start))
print("ASK: what is on the glass?")
