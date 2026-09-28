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
WIDTH, HEIGHT, CELL = 240, 320, 8     # CELL = framebuf glyph cell (px)
# PORTRAIT, and that is hardware-verified: the panel's native frame is 240 wide
# x 320 tall (vendor Display_EPD_W21.h: EPD_WIDTH 240, EPD_HEIGHT 320), and a
# frame drawn 240x320 lands on the glass exactly as drawn. A 320x240 landscape
# frame shears into bars -- uniform fills hide it, a split frame exposes it.
