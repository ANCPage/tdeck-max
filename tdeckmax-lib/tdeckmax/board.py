# T-Deck Max board assembly: pins, buses and XL9555 power gates.
# Pin values verified against Xinyuan-LilyGO/T-Deck-MAX
# (lib/TDeckMaxBoard/src/TDeckMaxBoard.h + docs/pinmap.md).

from machine import Pin, I2C, SPI, PWM
from tdeckmax.xl9555 import XL9555

# --- pins -----------------------------------------------------------------
I2C_SDA, I2C_SCL = 13, 14

KB_INT, KB_LED = 15, 42          # TCA8418 interrupt / keyboard backlight
TOUCH_INT = 12

EPD_SCK, EPD_MOSI, EPD_MISO = 36, 33, 47
EPD_CS, EPD_DC, EPD_RST, EPD_BUSY = 34, 35, 9, 37
EPD_BL = 41                      # e-paper frontlight PWM

LORA_CS, LORA_RST = 3, 4         # shared-SPI neighbours that must stay
SD_CS = 48                       # deselected (CS high) around the e-paper

GPS_TX, GPS_RX = 2, 16           # MCU side; module power-gated
MODEM_TX, MODEM_RX = 10, 11      # A7682E AT uart

# --- XL9555 ports (IO0..IO15, active-high unless noted) --------------------
# Names + polarity from TDeckMaxBoard.h. Only set what your app needs.
GATE_4G_EN = 0        # HIGH enables A7682E power
GATE_LORA_EN = 1      # HIGH enables SX1262
GATE_GPS_EN = 2       # HIGH enables MIA-M10Q
GATE_IMU_EN = 3       # HIGH enables BHI260AP 1V8 rail
GATE_LORA_ANT = 4     # HIGH = internal antenna, LOW = external
GATE_MOTOR_EN = 5     # HIGH enables DRV2605
GATE_AMP_EN = 6       # HIGH enables audio power amp
GATE_TOUCH_RST = 7    # LOW = touch reset (drive HIGH to release)
GATE_MODEM_PWRKEY = 8 # HIGH pulses A7682E PWRKEY
GATE_KB_RST = 9       # LOW = keyboard reset (drive HIGH to release)
GATE_AUDIO_SEL = 10   # HIGH = A7682E audio, LOW = ES8311

_RESET_GATES = (GATE_TOUCH_RST, GATE_KB_RST)  # release both resets


class Board:
    """One object per boot: shared buses + the XL9555 gatekeeper."""

    def __init__(self):
        self.i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400_000)
        self.expander = XL9555(self.i2c, 0x20)
        self.spi = SPI(1, baudrate=4_000_000, polarity=0, phase=0,
                       sck=Pin(EPD_SCK), mosi=Pin(EPD_MOSI), miso=Pin(EPD_MISO))
        self.epd_cs = Pin(EPD_CS, Pin.OUT, value=1)
        self.epd_dc = Pin(EPD_DC, Pin.OUT, value=0)
        self.epd_rst = Pin(EPD_RST, Pin.OUT, value=1)
        self.epd_busy = Pin(EPD_BUSY, Pin.IN)
        # park shared-SPI neighbours before the e-paper ever runs
        self.spi_neighbours_high()

    def spi_neighbours_high(self):
        for pin in (LORA_CS, LORA_RST, SD_CS, EPD_CS):
            p = Pin(pin, Pin.OUT, value=1)

    # -- power gates ---------------------------------------------------------
    def gate(self, port: int, on: bool = True) -> None:
        """Configure + drive one XL9555 output."""
        self.expander.pin_mode_output(port)
        self.expander.write(port, on)

    def release_resets(self):
        for port in _RESET_GATES:
            self.gate(port, True)       # touch + keyboard out of reset

    # -- convenience ----------------------------------------------------------
    def frontlight(self, duty: int = 0):
        """E-paper frontlight, 0..1023."""
        if not hasattr(self, "_bl"):
            self._bl = PWM(Pin(EPD_BL), freq=1000, duty_u16=0)
        self._bl.duty_u16(duty * 64)    # scale 0..1023 -> 0..65535
