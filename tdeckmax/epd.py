# UC8253 e-paper driver for the GDEQ031T10 (3.1", b/w, fast partial refresh).
# Command sequences transcribed verbatim from Good Display's demo driver as
# shipped in the LILYGO repo:
#   examples/Elink_paper/GDEQ031T10_Arduino/Display_EPD_W21.cpp
#
# Conventions:
#   * 1 frame = 320*240/8 = 9600 bytes, 1 bit per pixel, bit=1 -> WHITE
#     (same as the demo: new-data 0xFF = all white). framebuf MONO_HMSB output
#     feeds straight in.  VERIFY: geometry/orientation on first boot
#     (apps/tabs_calc.py draws a labelled test frame).
#   * full_refresh()  = clean update, use on boot/tab change/every N edits
#   * fast_refresh()  = whole-canvas fast-partial update (EPD_Init_Part path)
#   * the driver keeps a copy of the last frame: these UC8253 panels want the
#     previous image in the "old data" plane (cmd 0x10) to refresh cleanly.
#   * BUSY polarity: demo waits while BUSY == 0 (pin LOW = busy).
#     VERIFY: if a refresh hangs or skips, flip wait_busy_high_idle.

import time
from machine import Pin, SPI

# The panel's data path mirrors each row horizontally: a frame drawn containing
# "LEFT ... RIGHT" comes up reading "TFEL ... THGIR" (hardware-verified
# 2026-09-28 by reading test5.py off the glass). Mirroring at the driver keeps
# every higher layer -- screens, apps, the host simulator -- in normal
# left-to-right coordinates.
MIRROR_X = False      # OFF while we establish the panel's true behaviour (test6)


def _rev8(byte):
    """Reverse the 8 bits of one byte (MicroPython has no negative-step slice)."""
    out = 0
    for i in range(8):
        if byte & (1 << i):
            out |= 1 << (7 - i)
    return out


_REV_BITS = bytes(_rev8(i) for i in range(256))


def _mirror_row_order(frame, row_bytes):
    """Reverse pixel order within every row: byte order reversed, bits reversed."""
    out = bytearray(len(frame))
    for row in range(0, len(frame), row_bytes):
        for i in range(row_bytes):
            out[row + row_bytes - 1 - i] = _REV_BITS[frame[row + i]]
    return out


class UC8253:
    WIDTH, HEIGHT = 240, 320      # panel NATIVE portrait: vendor header says
    FRAME = WIDTH * HEIGHT // 8   # EPD_WIDTH 240 / EPD_HEIGHT 320 -> 30 bytes/row

    def __init__(self, spi: SPI, cs: Pin, dc: Pin, rst: Pin, busy: Pin):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.busy = busy
        self._prev = bytearray(self.FRAME)   # last thing sent to the panel

    # -- low level ------------------------------------------------------------
    def _cmd(self, b: int) -> None:
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytes([b]))
        self.cs.value(1)

    def _data(self, buf) -> None:
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(buf if isinstance(buf, (bytes, bytearray)) else bytes([buf]))
        self.cs.value(1)

    def _busy_wait(self, timeout_ms: int = 5000) -> None:
        t0 = time.ticks_ms()
        while self.busy.value() == 0:        # LOW = controller busy
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                raise TimeoutError("e-paper busy timeout")

    def _reset(self) -> None:
        self.rst.value(0)
        time.sleep_ms(10)                    # >= 10 ms per Good Display demo
        self.rst.value(1)
        time.sleep_ms(10)

    # -- init sequences (verbatim from Display_EPD_W21.cpp) --------------------
    def _init_full(self) -> None:
        self._reset()
        self._cmd(0x00); self._data(0x1F)     # panel setting PSR
        self._cmd(0x04)                       # power on
        self._busy_wait()

    def _init_part(self) -> None:
        self._reset()
        self._cmd(0x00); self._data(0x1F)
        self._cmd(0x04)
        self._busy_wait()
        self._cmd(0xE0); self._data(0x02)     # 1.0s fast-mode enable
        self._cmd(0xE5); self._data(0x79)     # fast-mode LUT select (partial)
        self._cmd(0x50); self._data(0xD7)     # VCOM and data interval

    # -- refresh ---------------------------------------------------------------
    def _send_planes(self, frame, full: bool) -> None:
        """cmd 0x10 = old plane (previous frame), 0x13 = new plane, refresh."""
        row_bytes = self.WIDTH // 8
        if MIRROR_X:
            old = _mirror_row_order(self._prev, row_bytes)
            new = _mirror_row_order(frame, row_bytes)
        else:
            old, new = self._prev, frame
        self._cmd(0x10)
        self._data(old)                       # old plane: what's on screen
        self._cmd(0x13)
        self._data(new)
        self._cmd(0x12)                       # display refresh
        time.sleep_ms(1)                      # >= 200us, demo keeps 1ms
        self._busy_wait()
        self._cmd(0x02)                       # power off
        self._prev[:] = frame

    def full_refresh(self, frame) -> None:
        self._init_full()
        self._send_planes(frame, full=True)

    def fast_refresh(self, frame) -> None:
        self._init_part()
        self._send_planes(frame, full=False)

    def clear(self, white: bool = True) -> None:
        fill = 0xFF if white else 0x00       # 1 = white per demo convention
        frame = bytearray(self.FRAME)
        for i in range(self.FRAME):
            frame[i] = fill
        self.full_refresh(frame)
