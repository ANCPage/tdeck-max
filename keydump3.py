# Keyboard bring-up v3: watch the KB_INT line (GPIO15) and show events ON THE PANEL.
#
#   mpremote connect /dev/ttyACM0 run keydump3.py
#
# Why: the GPIO_DAT_STAT registers can report nothing for pins the chip has
# assigned to the keypad matrix, so "0 pin changes" may be a blind sensor rather
# than a dead keyboard. The INT line is driven by the controller itself whenever
# it latches a key event, so it is an independent witness.
#
# Also enables the interrupt bits in CFG (0x03) in case the scanner gates on them.
# On-screen feedback: the panel shows the last decoded key, so you can see
# whether your presses are landing at all.

import time

import framebuf
from machine import Pin, Timer

from tdeckmax import HEIGHT, WIDTH
from tdeckmax import keys
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.tca8418 import TCA8418

RUN_SECONDS = 45
ROW = WIDTH // 8

board = Board()
board.release_resets()
kb = TCA8418(board.i2c)
print("begin():", kb.begin())
cfg = kb._read(0x01)
kb._write(0x01, cfg | 0x03)          # GPI_IEN | KE_IEN
kb.flush()
print("CFG 0x01 was 0x%02x, now 0x%02x" % (cfg, kb._read(0x01)))

epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
board.frontlight(700)
buf = bytearray(ROW * HEIGHT)


def paint(line1, line2):
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
    fb.fill(1)
    fb.rect(0, 0, WIDTH, HEIGHT, 0)
    fb.text("KEY TEST", 12, 16, 0)
    fb.text(line1, 12, 60, 0)
    fb.text(line2, 12, 84, 0)
    fb.text("press any key", 12, HEIGHT - 40, 0)
    epd.fast_refresh(buf)


paint("waiting...", "no events yet")
time.sleep_ms(200)

int_pin = Pin(15, Pin.IN, Pin.PULL_UP)
pulses = [0]
state = [int_pin.value()]


def tick(_):
    v = int_pin.value()
    if v != state[0]:
        pulses[0] += 1
        state[0] = v


timer = Timer(0)
timer.init(period=2, mode=Timer.PERIODIC, callback=tick)

events = 0
t0 = time.ticks_ms()
next_beat = 15000
while time.ticks_diff(time.ticks_ms(), t0) < RUN_SECONDS * 1000:
    if kb.available():
        raw = kb.get_event()
        events += 1
        dec = keys.decode_raw(raw, letters=True)
        print("EVENT raw=%3d (0x%02x) -> %s  [int pulses=%d]"
              % (raw, raw, dec, pulses[0]))
        paint("raw %d (0x%02x)" % (raw, raw), "decoded %s" % (dec,))
    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    if elapsed > next_beat:
        print("... %ds: %d events, %d INT transitions, INT line now %s"
              % (elapsed // 1000, events, pulses[0], int_pin.value()))
        next_beat += 15000
    time.sleep_ms(8)

timer.deinit()
print("=== done: %d events, %d INT transitions ===" % (events, pulses[0]))
