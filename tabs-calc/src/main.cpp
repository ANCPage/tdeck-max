// tabs-calc — two-tab calculator demo for the LILYGO T-Deck Max.
//
// Boot order matters on this board (see ~/tdeck-max/RESEARCH.md):
//   1. Wire on the shared I2C bus   (keyboard + everything else live here)
//   2. Park every shared-SPI chip-select high before the e-paper touches SPI
//   3. Keyboard first (cheap), then the e-paper (slow first full refresh)
//
// The display and keyboard need NO XL9555 power-gating init (matches LILYGO's
// own display/keypad examples). LoRa/GPS/audio would, but this app has none.

#include <Arduino.h>
#include <Wire.h>
#include "pins.h"
#include "keyboard.hpp"
#include "app.hpp"
#include "ui.hpp"

namespace {
Keyboard s_kb;
App      s_app;
Ui       s_ui(s_app);
}  // namespace

void setup()
{
    Serial.begin(115200);
    delay(100);

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

    if (!s_kb.init()) {
        Serial.println("tabs-calc: TCA8418 keyboard not found on I2C 0x34 — check wiring");
        while (true) {
            delay(1000);   // hold here; screen never draws, serial explains why
        }
    }

    s_ui.init();   // e-paper setup + first full frame
    Serial.println("tabs-calc ready");
}

void loop()
{
    Key key;
    if (s_kb.poll(key)) {
        bool wantFull = false;
        if (s_app.handle(key, wantFull)) {
            if (key.digit) {
                Serial.printf("key: digit %c\n", key.digitVal);
            } else {
                Serial.printf("key: ctl %d\n", (int)key.ctl);
            }
            s_ui.render(wantFull ? Ui::RefreshFull : Ui::RefreshPartial);
        }
    }
    delay(20);   // poll loop
}
