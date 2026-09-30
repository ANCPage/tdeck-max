# Device + log screens: what the machine knows about itself.
#
# These exist because of how much of this project is debugged remotely: when
# the network is unreliable, the panel is the one channel that always works.
# Read the Device screen to me and I know battery, address, uptime and whether
# the last boot was clean.

import os
import time

from tdeckmax import CELL, HEIGHT, WIDTH
from tdeckmax.screen import FOOTER_H, HEADER_H, Screen, draw_chrome

LIST_TOP = 44
LINE_H = 14

# Set by main.py at boot (the screen never constructs hardware itself, which is
# also what keeps it runnable in the host simulator).
gauge = None
net = None


def _lines():
    """Everything worth knowing, cheapest first. Never raises."""
    out = []
    try:
        if gauge is not None:
            out.append("battery   %s   %s mV   %s mA" % (
                gauge.soc_text(), gauge.voltage_mv(), gauge.current_ma()))
    except Exception as exc:                                       # noqa: BLE001
        out.append("battery   error: %s" % exc)
    try:
        from tdeckmax import net as _net
        ip = getattr(_net, "LAST_IP", None)
        if ip:
            w = _net.STA
            out.append("network   %s  connected=%s" % (ip, w.isconnected() if w else "?"))
        else:
            out.append("network   offline (no IP)")
    except Exception as exc:                                       # noqa: BLE001
        out.append("network   error: %s" % exc)
    try:
        import machine
        causes = {0: "UNKNOWN", 1: "PWRON", 2: "EXT/pin", 3: "SW", 4: "PANIC",
                  5: "INT_WDT", 6: "TASK_WDT", 7: "WDT", 8: "DEEPSLEEP",
                  9: "BROWNOUT", 10: "SDIO"}
        out.append("last boot %s" % causes.get(machine.reset_cause(), "?"))
        mins = time.ticks_ms() // 60000
        out.append("uptime    %d min" % mins)
        out.append("free RAM  %d kB" % (__import__("gc").mem_free() // 1024))
    except Exception as exc:                                       # noqa: BLE001
        out.append("machine   error: %s" % exc)
    try:
        st = os.statvfs("/")
        out.append("free flash %d kB" % (st[0] * st[3] // 1024))
    except Exception:                                              # noqa: BLE001
        pass
    return out


class DeviceScreen(Screen):
    title = "DEVICE"
    hints = ("r: refresh   DEL: back", "read this screen out when asking for help")

    def __init__(self):
        self.tick = 0

    def handle(self, key, app):
        kind, val = key
        if kind == "ctl" and val in ("back", "space"):
            app.pop()
            return True
        if kind == "char" and val == "r":
            return True
        return False

    def render(self, fb, app):
        self.tick += 1
        draw_chrome(fb, self, app, right="t%d" % self.tick)
        for i, line in enumerate(_lines()):
            fb.text(line[:29], 8, LIST_TOP + i * LINE_H, 0)


class LogScreen(Screen):
    """/net.log (or any file) as a scrolled page -- readable with no cable."""

    title = "NET LOG"
    hints = ("j/k scroll   r: reload   DEL: back", "the device's own network log")
    PATH = "/net.log"
    ROWS = 13

    def __init__(self):
        self.offset = 0            # 0 = newest lines at the bottom
        self.lines = []

    def enter(self, app):
        self.reload()

    def reload(self):
        try:
            with open(self.PATH) as fh:
                self.lines = fh.read().splitlines()[-200:]
        except Exception as exc:                                   # noqa: BLE001
            self.lines = ["(cannot read %s: %s)" % (self.PATH, exc)]
        self.offset = 0

    def handle(self, key, app):
        kind, val = key
        if kind == "ctl" and val in ("back", "space"):
            app.pop()
            return True
        if kind == "char" and val == "j":
            self.offset = max(0, self.offset - 1)
            return True
        if kind == "char" and val == "k":
            self.offset = min(max(0, len(self.lines) - self.ROWS), self.offset + 1)
            return True
        if kind == "char" and val == "r":
            self.reload()
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app,
                    right="%d lines" % len(self.lines))
        end = len(self.lines) - self.offset
        window = self.lines[max(0, end - self.ROWS):end]
        y = LIST_TOP - 10
        for line in window:
            fb.text(line[:29], 8, y, 0)
            y += LINE_H
