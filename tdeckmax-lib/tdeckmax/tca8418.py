# TCA8418 keyboard-matrix controller driver (MicroPython).
# Register map + init writes transcribed from Adafruit's TCA8418 driver
# (begin()/matrix()/available()/getEvent()/flush()) and LILYGO's peri_keypad.cpp.
#
# This driver is dumb: it configures the 4x10 matrix and returns raw FIFO
# events. Semantic decoding (keys -> digits/controls) lives in keys.py.

from machine import I2C
from tdeckmax import keys

# Register map (Adafruit/CP driver + datasheet)
REG_CFG = 0x01            # config: key-event int enable etc.
REG_INT_STAT = 0x02
REG_KEY_LCK_EC = 0x03     # low nibble = event count
REG_KEY_EVENT_A = 0x04    # reading pops one event from the FIFO
REG_GPIO_INT_STAT1 = 0x11
REG_GPIO_DAT_STAT1 = 0x14
REG_GPIO_DAT_OUT1 = 0x17
REG_GPIO_INT_EN1 = 0x1A
REG_KP_GPIO1 = 0x1D       # keypad/gpio select per pin (1 = GPIO)
REG_EVT_MODE1 = 0x20      # GPIO event mode (1 = events go to FIFO)
REG_GPIO_DIR1 = 0x23      # 1 = output
REG_GPIO_INT_LVL1 = 0x26
REG_DEBOUNCE_DIS1 = 0x29  # 1 = debounce disabled
REG_GPIO_PULL1 = 0x2C     # 1 = pull-up disabled

I2C_ADDR = 0x34


class TCA8418:
    def __init__(self, i2c: I2C, addr: int = I2C_ADDR):
        self.i2c = i2c
        self.addr = addr

    # -- register plumbing -------------------------------------------------
    def _read(self, reg: int) -> int:
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _write(self, reg: int, value: int) -> None:
        self.i2c.writeto_mem(self.addr, reg, bytes([value & 0xFF]))

    def _write3(self, base: int, v1: int, v2: int, v3: int) -> None:
        # registers 1..3 sit in a row (Adafruit writes all three)
        self._write(base, v1)
        self._write(base + 1, v2)
        self._write(base + 2, v3)

    # -- init ----------------------------------------------------------------
    def begin(self) -> bool:
        """Probe + default setup. Mirrors Adafruit begin(): every pin as an
        input, GPIO events off so the FIFO stays key-only, debounce on."""
        try:
            self._read(REG_CFG)
        except OSError:
            return False
        self._write3(REG_GPIO_DIR1, 0x00, 0x00, 0x00)      # all inputs
        self._write3(REG_EVT_MODE1, 0x00, 0x00, 0x00)       # no GPIO->FIFO
        self._write3(REG_GPIO_INT_LVL1, 0x00, 0x00, 0x00)   # falling ints
        self._write3(REG_GPIO_INT_EN1, 0x00, 0x00, 0x00)    # polling: no irq
        self._write3(REG_DEBOUNCE_DIS1, 0x00, 0x00, 0x00)   # debounce on
        self.matrix(keys.ROWS, keys.COLS)
        self.flush()
        return True

    def matrix(self, rows: int, cols: int) -> None:
        """Assign the lowest pins as keypad rows/cols (Adafruit matrix())."""
        self._write(REG_KP_GPIO1, (1 << rows) - 1)
        self._write(REG_KP_GPIO1 + 1, 0xFF if cols >= 8 else (1 << cols) - 1)
        self._write(REG_KP_GPIO1 + 2, 0x03 if cols > 8 else 0x00)

    # -- events ---------------------------------------------------------------
    def available(self) -> int:
        return self._read(REG_KEY_LCK_EC) & 0x0F

    def get_event(self) -> int:
        return self._read(REG_KEY_EVENT_A)

    def flush(self) -> None:
        while self.available():
            self.get_event()
        self._write(REG_INT_STAT, 0x03)     # clear key + overflow int flags

    def read_key(self):
        """One decoded press, or None. Releases are consumed and dropped.
        Returns keys.decode_raw() tuples: ("digit", "7") or ("ctl", "tab_next")."""
        if self.available() <= 0:
            return None
        raw = self.get_event()
        return keys.decode_raw(raw)
