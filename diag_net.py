# Temporary diagnostic: try WiFi, write the result to /net.log, then EXIT so the
# REPL is idle and the log can be read over USB in a single session.

import sys
import time

import framebuf
import network

from tdeckmax import HEIGHT, WIDTH
from tdeckmax.board import Board
from tdeckmax.epd import UC8253

log = open("/net.log", "w")


def note(msg):
    log.write(msg + "\n")
    log.flush()
    print(msg)


try:
    board = Board()
    board.lights()
    epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)

    import json
    cfg = json.load(open("/wifi.json"))
    note("cfg ssid=%s pi=%s" % (cfg["ssid"], cfg["pi"]))

    w = network.WLAN(network.STA_IF)
    w.active(True)
    time.sleep_ms(500)
    note("active=%s connected=%s" % (w.active(), w.isconnected()))

    note("scanning...")
    try:
        found = w.scan()
        note("found %d APs" % len(found))
        for ap in found[:12]:
            ssid = ap[0].decode("utf-8", "replace") if isinstance(ap[0], bytes) else ap[0]
            note("  ssid=%r rssi=%d chan=%d" % (ssid, ap[3], ap[2]))
    except Exception as exc:
        note("scan failed: %s" % exc)

    note("connecting to %s ..." % cfg["ssid"])
    try:
        w.connect(cfg["ssid"], cfg["pwd"])
        t0 = time.time()
        while not w.isconnected() and time.time() - t0 < 25:
            time.sleep(0.5)
        note("connected=%s ifconfig=%s" % (w.isconnected(), w.ifconfig()))
        st = w.status()
        note("status=%s" % st)
    except Exception as exc:
        note("connect raised: %s" % exc)

    # paint the outcome so Austin can see it without a cable
    buf = bytearray(WIDTH * HEIGHT // 8)
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
    fb.fill(1)
    fb.rect(0, 0, WIDTH, HEIGHT, 0)
    fb.text("NET DIAG", 12, 12, 0)
    fb.text("connected: %s" % w.isconnected(), 12, 60, 0)
    fb.text(str(w.ifconfig()[0]), 12, 84, 0)
    fb.text("see /net.log", 12, 120, 0)
    epd.full_refresh(buf)

    note("done")
except Exception as exc:                       # noqa: BLE001
    sys.print_exception(exc, log)
    log.flush()
finally:
    log.close()
