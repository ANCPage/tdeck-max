# tdeckmax — MicroPython driver library for the LILYGO T-Deck Max.
#
# Status: 2026-09-08 scaffold, written from verified primary sources:
#   * register maps  -> LILYGO repo (SensorLib/ExtensionIOXL9555), Adafruit
#                       TCA8418 driver (register-level), Good Display demo code
#   * init sequences -> LILYGO example GDEQ031T10_Arduino/Display_EPD_W21.cpp
#                       (UC8253, transcribed verbatim)
#   * key decoding   -> LILYGO examples/factory (peri_keypad.cpp + dialer T9 map)
#
# NOT yet tested on hardware — everything touching the panel geometry, BUSY
# polarity or physical key positions carries a VERIFY marker. Run apps/
# tabs_calc.py first: it prints every decoded key and draws a test frame.
__version__ = "0.1.0-dev"

# Board geometry (hardware-free, so the host simulator can import it).
# Landscape drawing surface; the panel is natively 240x320 portrait.
WIDTH, HEIGHT, CELL = 320, 240, 8     # CELL = framebuf glyph cell (px)
