# main.py — boots straight into the notes app: type, and see it on the glass.
#
# This is the end-to-end test that matters: if the keymap is right, what appears
# on the panel is what your fingers pressed. Keystrokes are coalesced (~120 ms)
# so fast typing costs one panel refresh per burst, not one per key.
#
# Logs every raw code + decode to /keys.log, and any boot exception to
# /boot_error.log.

import sys
import time

import framebuf

from apps.notes import NotesScreen
from tdeckmax import HEIGHT, WIDTH, keys
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.planner import Planner
from tdeckmax.screen import App
from tdeckmax.tca8418 import TCA8418

COALESCE_MS = 120


def start():
    board = Board()
    board.release_resets()
    board.pulse_keyboard_reset()
    epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
    board.frontlight(700)

    kb = TCA8418(board.i2c)
    print("kb.begin():", kb.begin())

    buf = bytearray(WIDTH * HEIGHT // 8)
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
    app = App(Planner(epd), fb, buf)
    app.push(NotesScreen())
    app.paint()

    log = open("/keys.log", "a")
    log.write("--- notes app up ---\n")
    log.flush()
    print("notes app up")

    while True:
        if kb.available():
            changed = False
            raw = kb.get_event()
            key = keys.decode_raw(raw, letters=True)
            log.write("%3d %s\n" % (raw, key))
            log.flush()
            if key and app.handle(key):
                changed = True
            # coalesce the burst, then repaint once
            deadline = time.ticks_add(time.ticks_ms(), COALESCE_MS)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if kb.available():
                    raw = kb.get_event()
                    key = keys.decode_raw(raw, letters=True)
                    log.write("%3d %s\n" % (raw, key))
                    log.flush()
                    if key and app.handle(key):
                        changed = True
                time.sleep_ms(4)
            if changed:
                app.paint()
        time.sleep_ms(4)


try:
    start()
except Exception as exc:                    # noqa: BLE001
    with open("/boot_error.log", "a") as fh:
        fh.write("\n--- boot failure ---\n")
        sys.print_exception(exc, fh)
    raise
