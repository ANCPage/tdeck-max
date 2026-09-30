# BQ27220 fuel gauge (I2C 0x55) — the T-Deck Max's battery monitor.
#
# Register map taken from a driver written for this exact chip
# (kodediy/kode_BQ27220), cross-checked against the BQ27xxx command set:
#   0x06 Temperature (0.1 K)   0x08 Voltage (mV)      0x0A BatteryStatus
#   0x0C Current (mA, signed)  0x10 Remaining (mAh)   0x12 FullCapacity (mAh)
#   0x14 AvgCurrent (mA)       0x16 TimeToEmpty (min) 0x18 TimeToFull (min)
#   0x2A CycleCount            0x2C StateOfCharge (%) 0x2E StateOfHealth (%)
#
# Positive current = charging (BQ27xxx convention).
#
# NOTE: the gauge can only be read while the board is powered and code is
# running — a device that is off cannot report its own battery.

ADDR = 0x55


class BQ27220:
    def __init__(self, i2c, addr=ADDR):
        self.i2c = i2c
        self.addr = addr

    # -- raw ------------------------------------------------------------------
    def _word(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 2)
        return b[0] | (b[1] << 8)

    def _signed(self, reg):
        v = self._word(reg)
        return v - 65536 if v & 0x8000 else v

    # -- readings (None on any I2C hiccup, so callers never crash) ------------
    def soc(self):
        try:
            return self._word(0x2C)
        except OSError:
            return None

    def voltage_mv(self):
        try:
            return self._word(0x08)
        except OSError:
            return None

    def current_ma(self):
        try:
            return self._signed(0x0C)
        except OSError:
            return None

    def remaining_mah(self):
        try:
            return self._word(0x10)
        except OSError:
            return None

    def full_mah(self):
        try:
            return self._word(0x12)
        except OSError:
            return None

    def soh(self):
        try:
            return self._word(0x2E)
        except OSError:
            return None

    def cycles(self):
        try:
            return self._word(0x2A)
        except OSError:
            return None

    def temperature_c(self):
        try:
            return self._word(0x06) / 10.0 - 273.15
        except OSError:
            return None

    # -- display helpers ------------------------------------------------------
    def soc_text(self):
        """Short string for a header, e.g. '87%' or '--' when unreadable."""
        pct = self.soc()
        return "--" if pct is None else "%d%%" % pct

    def charging(self):
        ma = self.current_ma()
        return None if ma is None else ma > 5

    def summary(self):
        """One line for a status screen or log."""
        pct, mv, ma = self.soc(), self.voltage_mv(), self.current_ma()
        return "battery %s  %s mV  %s mA" % (
            "--" if pct is None else "%d%%" % pct,
            "--" if mv is None else mv,
            "--" if ma is None else ma,
        )
