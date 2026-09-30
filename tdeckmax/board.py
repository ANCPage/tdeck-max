# T-Deck Max board assembly: pins, buses and XL9555 power gates.
# Pin values verified against Xinyuan-LilyGO/T-Deck-MAX
# (lib/TDeckMaxBoard/src/TDeckMaxBoard.h + docs/pinmap.md).

import time

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

# Lights live at MODULE level on purpose: if the PWM objects were instance
# attributes of Board, they'd be garbage-collected the moment the app is
# interrupted by a host session (mpremote sends Ctrl-C), and the frontlight +
# key backlight would go dark every time we read a log. Module globals survive
# that, so the device never blackens itself just because we looked at it.
_LIGHTS = {}


def _pwm(pin: int, level: int) -> None:
    """Drive one backlight (level 0..1023) with a persistent PWM object."""
    p = _LIGHTS.get(pin)
    if p is None:
        p = PWM(Pin(pin), freq=1000, duty_u16=0)
        _LIGHTS[pin] = p
    p.duty_u16(max(0, min(1023, level)) * 64)


class Board:
    """One object per boot: shared buses + the XL9555 gatekeeper."""

    def __init__(self):
        self.i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
        self.expander = XL9555(self.i2c, 0x20)
        # Cold-boot race (seen 2026-09-30): right after a reset the XL9555 can
        # NACK its first access -- ENODEV inside release_resets -- which killed
        # the app before it could draw a single pixel. Poll until it answers.
        self.expander_ready_ms = self._wait_for_expander()
        self.spi = SPI(1, baudrate=4_000_000, polarity=0, phase=0,
                       sck=Pin(EPD_SCK), mosi=Pin(EPD_MOSI), miso=Pin(EPD_MISO))
        self.epd_cs = Pin(EPD_CS, Pin.OUT, value=1)
        self.epd_dc = Pin(EPD_DC, Pin.OUT, value=0)
        self.epd_rst = Pin(EPD_RST, Pin.OUT, value=1)
        self.epd_busy = Pin(EPD_BUSY, Pin.IN)
        # park shared-SPI neighbours before the e-paper ever runs
        self.spi_neighbours_high()

    def _wait_for_expander(self, attempts: int = 40, delay_ms: int = 100) -> int:
        """Wait for the XL9555 to answer I2C; return how long that took (ms).

        The expander gates everything else on this board, so it must be up
        before any reset line is touched. Raises only if it never answers.
        """
        start = time.ticks_ms()
        for _ in range(attempts):
            try:
                self.expander.read_port(0)
                return time.ticks_diff(time.ticks_ms(), start)
            except OSError:
                time.sleep_ms(delay_ms)
        raise OSError("XL9555 did not answer after %d attempts" % attempts)

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

    def pulse_keyboard_reset(self, hold_ms: int = 60):
        """Assert + release the keyboard's reset line.

        Needed in practice: after the factory firmware has been through its
        sleep/shutdown path, the TCA8418 can come up latched -- it answers I2C
        and reports healthy registers, but never queues a single key event.
        A LOW pulse on XL9555 P0.9 fixes it (hardware-verified 2026-09-29).
        """
        self.gate(GATE_KB_RST, False)
        time.sleep_ms(hold_ms)
        self.gate(GATE_KB_RST, True)
        time.sleep_ms(250)

    def pulse_touch_reset(self, hold_ms: int = 20):
        """The factory firmware pulses the touch controller's reset at boot
        (IO07 LOW, delay, HIGH). Mirror it."""
        self.gate(GATE_TOUCH_RST, False)
        time.sleep_ms(hold_ms)
        self.gate(GATE_TOUCH_RST, True)

    def lights(self, frontlight: int = 200, keyboard: int = 1023):
        """Turn both backlights on the way the factory firmware does:
        analogWrite(EPD_BL, 50/255) and analogWrite(KEYBOARD_LED, 255/255).
        Our ranges are 0..1023, so 50/255 -> ~200 and 255/255 -> 1023."""
        self.frontlight(frontlight)
        self.keyboard_backlight(keyboard)

    # -- convenience ----------------------------------------------------------
    def keyboard_backlight(self, duty: int = 0):
        """Keyboard backlight on KB_LED (GPIO42), 0..1023. Useful as a visible
        liveness signal: if it glows, the app is running."""
        _pwm(KB_LED, duty)

    def frontlight(self, duty: int = 0):
        """E-paper frontlight, 0..1023."""
        _pwm(EPD_BL, duty)
