# Put OUR launcher on the REAL panel — the same screen code the simulator renders.
#
#   mpremote connect /dev/ttyACM0 run device_run.py
#
# Panel geometry is now native portrait 240x320 (verified on hardware), so the
# framebuffer goes to the UC8253 unchanged: no rotation, no conversion.

import time

import framebuf

from tdeckmax import HEIGHT, WIDTH
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.planner import Planner
from tdeckmax.screen import App
from apps.demo_menu import MenuScreen

board = Board()
board.frontlight(700)
epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)

buf = bytearray(WIDTH * HEIGHT // 8)
fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
app = App(Planner(epd), fb, buf)
app.push(MenuScreen())

t0 = time.ticks_ms()
app.paint()
print("launcher painted in %d ms (full refresh)" % time.ticks_diff(time.ticks_ms(), t0))

# and prove a fast/partial refresh works too: move the selection down one item
t0 = time.ticks_ms()
if app.handle(("char", "j")):
    app.paint()
    print("fast refresh after 'j' in %d ms" % time.ticks_diff(time.ticks_ms(), t0))
else:
    print("no repaint requested by 'j'")
