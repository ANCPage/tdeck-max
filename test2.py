# Test 2: frontlight ON, an unambiguous black/white split frame, refreshed TWICE
# (second pass sends a consistent "old" plane, which cleans up ghosting), with
# BUSY sampled by a timer DURING the refresh so panel activity is measurable.
#
#   mpremote connect /dev/ttyACM0 run test2.py
#
# Questions it settles:
#   * is the faint image a lighting artifact (dim room, frontlight off) or a weak drive?
#   * which bit value is black?  (left half black / right half white, text on both)
#   * does a second refresh kill the ghost of the factory UI?

import time

import framebuf
from machine import Timer

from tdeckmax import HEIGHT, WIDTH
from tdeckmax.board import Board
from tdeckmax.epd import UC8253

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)

print("frontlight -> duty 700/1023")
board.frontlight(700)
time.sleep_ms(50)

samples = []
timer = Timer(0)
timer.init(period=5, mode=Timer.PERIODIC,
           callback=lambda _: samples.append(board.epd_busy.value()))

frame = bytearray(epd.FRAME)
fb = framebuf.FrameBuffer(frame, WIDTH, HEIGHT, framebuf.MONO_HLSB)
fb.fill(1)                                        # 1 = white
fb.fill_rect(0, 0, WIDTH // 2, HEIGHT, 0)         # LEFT half black
fb.rect(0, 0, WIDTH, HEIGHT, 0)
fb.rect(1, 1, WIDTH - 2, HEIGHT - 2, 0)
fb.fill_rect(WIDTH // 2 - 12, 4, 24, 24, 0)       # marker: top centre
fb.text("L=BLACK", 24, 116, 1)                    # white text on the black half
fb.text("R=WHITE", 196, 116, 0)                   # black text on the white half
fb.text("mpx bringup", 196, 8, 0)

for attempt in (1, 2):
    samples.clear()
    t0 = time.ticks_ms()
    epd.full_refresh(frame)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    low = sum(1 for s in samples if s == 0)
    print("refresh %d: %d ms | BUSY samples %d, of which LOW %d (%.0f%%)"
          % (attempt, dt, len(samples), low, 100.0 * low / max(1, len(samples))))

timer.deinit()
print("frontlight duty_u16 =", getattr(getattr(board, "_bl", None), "duty_u16", lambda: "n/a")())
print("ASK: which half is black, is the text crisp, and is the old grid gone?")
