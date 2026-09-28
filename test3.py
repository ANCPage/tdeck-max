# Test 3: three unmistakable states, twice each, so a human can just SAY what
# they saw. No photo needed, no pixel-guessing.
#
#   mpremote connect /dev/ttyACM0 run test3.py
#
# Sequence:  ALL BLACK  ->  ALL WHITE  ->  LEFT BLACK / RIGHT WHITE
# Each state is refreshed twice (second pass sends a consistent old plane).
#
# What each answer tells us:
#   black looks black       -> polarity correct (1=white, 0=black)
#   black looks white       -> polarity inverted, one-line fix
#   split edge is clean     -> frame geometry 320x240 landscape is correct
#   split edge is jagged    -> panel is actually 240 wide, geometry fix needed

import time

from tdeckmax.board import Board
from tdeckmax.epd import UC8253

board = Board()
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)

board.frontlight(700)          # keep the glass lit for a dim room
time.sleep_ms(100)

BLACK = bytes([0x00]) * epd.FRAME
WHITE = bytes([0xFF]) * epd.FRAME

half = bytearray(WHITE)
for row in range(240):                       # left half black, right half white
    start = row * 40                         # 320 px / 8 = 40 bytes per row
    for i in range(20):
        half[start + i] = 0x00

states = [("ALL BLACK", BLACK), ("ALL WHITE", WHITE), ("LEFT BLACK / RIGHT WHITE", half)]

for label, frame in states:
    for pass_no in (1, 2):
        t0 = time.ticks_ms()
        epd.full_refresh(frame)
        print("%-28s pass %d: %d ms" % (label, pass_no, time.ticks_diff(time.ticks_ms(), t0)))
    time.sleep_ms(1500)

print("DONE - sequence was: all black, all white, left black/right white")
