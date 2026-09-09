#pragma once
// Pin map for the LILYGO T-Deck Max.
// Values verified against the official repo (Xinyuan-LilyGO/T-Deck-MAX):
//   lib/TDeckMaxBoard/src/TDeckMaxBoard.h  +  docs/pinmap.md
// Only peripherals this app touches are listed. LoRa/GPS/IMU/motor/audio/4G are
// power-gated behind the XL9555 IO expander (I2C 0x20) — if you add one of those,
// read ~/tdeck-max/RESEARCH.md first.

// Shared I2C bus (everything rides on it: touch, keyboard, XL9555, PMIC, ...)
#define PIN_I2C_SDA 13
#define PIN_I2C_SCL 14

// TCA8418 keyboard controller
#define PIN_KB_ADDR  0x34
#define PIN_KB_INT   15   // interrupt line (this app polls instead)
#define PIN_KB_LED   42   // keyboard backlight PWM

// E-paper (GDEQ031T10, 3.1", UC8253, 240x320 native, used in 320x240 landscape)
#define PIN_EPD_SCK   36
#define PIN_EPD_MOSI  33
#define PIN_EPD_CS    34
#define PIN_EPD_DC    35
#define PIN_EPD_RST   9
#define PIN_EPD_BUSY  37
#define PIN_EPD_BL    41   // frontlight PWM

// Other users of the shared SPI bus — must sit deselected (CS high) at all times
// while the e-paper is talking (rule from LILYGO's display example).
#define PIN_LORA_CS   3
#define PIN_LORA_RST  4
#define PIN_SD_CS     48
