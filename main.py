# main.py — runs automatically on every boot.
#
# Keyboard check with visible feedback and no timing pressure:
#   * press keys whenever you like; the panel shows what the keyboard controller
#     actually reported (raw FIFO code + our decode)
#   * every event is appended to /kb.log on the device, readable over USB later
#   * any boot-time exception is written to /boot_error.log, so a silent failure
#     at boot becomes a readable traceback

import sys
import time

import framebuf
from machine import Pin

from tdeckmax import HEIGHT, WIDTH, keys
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.tca8418 import TCA8418

ROW = WIDTH // 8


def start():
    board = Board()
    board.release_resets()
    epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
    board.frontlight(700)

    kb = TCA8418(board.i2c)
    kb_ok = kb.begin()
    kb_int = Pin(15, Pin.IN, Pin.PULL_UP)

    buf = bytearray(ROW * HEIGHT)
    count = [0]
    paints = [0]

    def paint(line1, line2="", line3=""):
        fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
        fb.fill(1)
        fb.rect(0, 0, WIDTH, HEIGHT, 0)
        fb.text("KEYBOARD TEST", 12, 12, 0)
        fb.text(line1, 12, 56, 0)
        fb.text(line2, 12, 80, 0)
        fb.text(line3, 12, 104, 0)
        fb.text("events seen: %d" % count[0], 12, HEIGHT - 88, 0)
        fb.text("kb init: %s  INT: %d" % (kb_ok, kb_int.value()), 12, HEIGHT - 68, 0)
        fb.text("press any keys", 12, HEIGHT - 40, 0)
        paints[0] += 1
        if paints[0] % 6 == 0:
            epd.full_refresh(buf)
        else:
            epd.fast_refresh(buf)

    log = open("/kb.log", "a")
    log.write("--- boot ---\n")
    log.flush()
    print("keyboard test up; kb init =", kb_ok)

    paint("waiting for a key", "no events yet")

    while True:
        if kb.available():
            raw = kb.get_event()
            count[0] += 1
            dec = keys.decode_raw(raw, letters=True)
            line = "raw=%3d (0x%02x) -> %s" % (raw, raw, dec)
            print(line)
            log.write(line + "\n")
            log.flush()
            paint(line, "decoded: %s" % (dec,), "event #%d" % count[0])
        time.sleep_ms(10)


try:
    start()
except Exception as exc:                    # noqa: BLE001 - report anything at all
    with open("/boot_error.log", "a") as fh:
        fh.write("\n--- boot failure ---\n")
        sys.print_exception(exc, fh)
    raise
