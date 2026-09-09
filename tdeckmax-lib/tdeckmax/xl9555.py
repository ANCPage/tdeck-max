# XL9555 16-bit I2C IO expander — the T-Deck Max's power/routing master.
# Register map and pin semantics from LILYGO's own SensorLib
# (lib/SensorLib/src/ExtensionIOXL9555.hpp + REG/XL9555Constants.h):
#   IO0..IO7  -> port 0, IO8..IO15 -> port 1; a port bit = 1 means INPUT.

from machine import Pin, I2C


class XL9555:
    REG_IN0 = 0x00   # input  (r)
    REG_IN1 = 0x01
    REG_OUT0 = 0x02  # output (rw)
    REG_OUT1 = 0x03
    REG_POL0 = 0x04  # polarity inversion (rw)
    REG_POL1 = 0x05
    REG_CFG0 = 0x06  # configuration: 1 = input, 0 = output
    REG_CFG1 = 0x07

    def __init__(self, i2c: I2C, addr: int = 0x20):
        self.i2c = i2c
        self.addr = addr

    # -- register plumbing ------------------------------------------------
    def _read(self, reg: int) -> int:
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _write(self, reg: int, value: int) -> None:
        self.i2c.writeto_mem(self.addr, reg, bytes([value & 0xFF]))

    def _rmw(self, reg: int, bit: int, on: bool) -> None:
        value = self._read(reg)
        if on:
            value |= 1 << bit
        else:
            value &= ~(1 << bit)
        self._write(reg, value)

    # -- pin API (pin = IO0..IO15, 0..15) ----------------------------------
    def pin_mode_output(self, pin: int) -> None:
        cfg, bit = (self.REG_CFG1, pin - 8) if pin >= 8 else (self.REG_CFG0, pin)
        self._rmw(cfg, bit, False)              # 0 = output

    def pin_mode_input(self, pin: int) -> None:
        cfg, bit = (self.REG_CFG1, pin - 8) if pin >= 8 else (self.REG_CFG0, pin)
        self._rmw(cfg, bit, True)

    def write(self, pin: int, level: bool) -> None:
        out, bit = (self.REG_OUT1, pin - 8) if pin >= 8 else (self.REG_OUT0, pin)
        self._rmw(out, bit, bool(level))

    def read(self, pin: int) -> bool:
        inp, bit = (self.REG_IN1, pin - 8) if pin >= 8 else (self.REG_IN0, pin)
        return bool(self._read(inp) & (1 << bit))

    # -- bulk ---------------------------------------------------------------
    def read_port(self, port: int) -> int:
        return self._read(self.REG_IN0 if port == 0 else self.REG_IN1)

    def write_port(self, port: int, value: int) -> None:
        self._write(self.REG_OUT0 if port == 0 else self.REG_OUT1, value)
