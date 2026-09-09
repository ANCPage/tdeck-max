# tabs-calc — two-tab calculator for the LILYGO T-Deck Max

A small, keyboard-first demo app that shows the whole dev pattern for this board:
**PlatformIO + Arduino framework, direct GxEPD2 e-paper drawing (no LVGL), polled
TCA8418 keyboard.** Two tabs, one job each:

- **Tab 1 — ADD**: enter A and B, the black banner shows `A + B` live.
- **Tab 2 — SUB**: same form, banner shows `A − B` live.

Numbers update on every keypress. No buttons, no touch, no menus-within-menus —
deliberately small so it is easy to read, flash, and hack on.

## Key layout (verified against LILYGO factory firmware)

This keyboard has a QWERTY grid but no printed number row, so digits follow the
same convention LILYGO's own phone dialer uses (`phone_keypad_to_digit` in their
`examples/factory/ui_deckpro.cpp`):

| Key(s)              | Meaning                    |
|---------------------|----------------------------|
| `a b c` … `w x y z` | digits 2 … 9 (T9 groups)   |
| `UP` (bottom row, ×2)| digit 1                    |
| bottom `0` key      | digit 0                    |
| `ENT`               | move editing A ⇄ B         |
| `DEL`               | backspace                  |
| `SPACE`             | clear focused field        |
| `SYM` / `ALT`       | next / previous tab        |

The whole mapping lives in one table in `src/keyboard.cpp` — if a keycap
disagrees with the table on your unit, the serial log prints every decoded key
(`key: digit 7`, `key: ctl 2`, …) so you can remap it in seconds.

## Build & flash

Requires PlatformIO (any machine — desktop, or this Pi once ~3 GB of disk is
free; the ESP32 toolchain is large). The LILYGO repo is **not** required: this
project is self-contained and pins the same `espressif32@6.5.0` platform LILYGO
CI-tests against.

```sh
cd tabs-calc
pio run                 # first run downloads the toolchain (~minutes)
pio run -t upload       # device in BOOT+RST download mode if upload fails
pio device monitor      # 115200 baud
```

Arduino IDE is possible but needs the 14 board settings from the LILYGO wiki —
PlatformIO is the supported path.

## Screen-refresh policy

E-paper ghosts if you only ever do fast partial refreshes, and full refreshes
are slow and flashy. This app does:

- **Full refresh** on boot, tab change, and every 10th update.
- **Whole-canvas fast partial refresh** for key feedback in between.

Tune `kPartialMax` and the banner/field geometry at the top of `src/ui.cpp`.

## Project layout

```
platformio.ini       board/PSRAM/partition flags mirroring the LILYGO repo
src/pins.h           verified T-Deck Max pin map (only what this app uses)
src/keyboard.hpp/cpp TCA8418 driver: matrix decode + T9 digit mapping
src/app.hpp/cpp      tab state, text fields, add/subtract logic (no UI here)
src/ui.hpp/cpp       all drawing; every layout constant in one place
src/main.cpp         init order + key poll loop
```

## Verify-on-device checklist (first flash)

1. Serial prints `tabs-calc ready` — I2C + keyboard OK.
2. Every key prints a sensible `key:` line (fix the table if not).
3. `1 ADD` chip is filled black; SYM/ALT flips tabs; each tab keeps its numbers.
4. ENT swaps the filled field; digits land only in the filled field.
5. Banner shows the live result; screen doesn't ghost after ~10 edits.

## Status / honesty note

Written 2026-09-08 from the official repo's CI-tested patterns (display init,
matrix decode, digit mapping all copied verbatim from LILYGO examples). It has
**not been compiled or run yet** — no toolchain on this Pi while its disk is
~98% full. First `pio run` may surface a driver-version nit; the two candidates
are `GxEPD2@1.5.5` (pinned to LILYGO's version) and the partition scheme.

## Ideas to grow it

- Decimals + negative input (`.`, `-` via SYM layer)
- A third tab or a home menu screen
- Frontlight (GPIO 41 PWM) toggle key
- Touch (CST driver is in the LILYGO repo) so taps also move the field focus
- WiFi + HTTP to the Pi's llama-server (`:8092`) — this form is the natural
  seed of the Hermes-client app
