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


class UC8253:
    WIDTH, HEIGHT = 320, 240
    FRAME = WIDTH * HEIGHT // 8

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
        self._cmd(0x10)
        self._data(self._prev)                # old plane: what's on screen
        self._cmd(0x13)
        self._data(frame)
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
