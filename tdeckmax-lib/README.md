# tdeckmax — MicroPython library + apps for the LILYGO T-Deck Max

Drivers (in `tdeckmax/`), one demo app (`apps/tabs_calc.py`), and a port of the
C++ two-tab calculator so you can compare the two flavours side by side.

## What's real vs what still needs hardware

Everything is transcribed from verified primary sources (register maps, LILYGO
factory key decoding, Good Display's UC8253 init sequences), **but nothing has
run on the device yet** — every item below is marked with what to check first.

| Module | Source of truth | First thing to verify on hardware |
|---|---|---|
| `xl9555.py` | LILYGO SensorLib register map | nothing — standard 16-bit expander |
| `tca8418.py` | Adafruit TCA8418 driver (registers + init writes) | probe at 0x34 |
| `keys.py` | LILYGO peri_keypad.cpp + dialer T9 map | **press vs release ranges** (`PRESS_IS_HIGH`) and mirrored column split — serial log settles it in one keypress |
| `epd.py` | Good Display demo (`Display_EPD_W21.cpp`) | **BUSY polarity**, frame orientation (320x240 row-major assumed), fast-partial look |
| `ui.py` | framebuf (built-in 8x8 font) | text legibility; spacing |

## Running it

1. Flash a generic **ESP32-S3 MicroPython** build (SPIRAM variant — the board
   has 8 MB PSRAM) via esptool over the USB-C port (BOOT+RST to enter download
   mode). MicroPython has no T-Deck-Max board port; we use the generic S3 port
   and drive everything over the verified pins in `board.py`.
2. Copy the `tdeckmax/` folder and `apps/tabs_calc.py` onto the device filesystem
   (REPL `mpremote cp`, or ampy, or the WebREPL).
3. `import apps.tabs_calc` (or set it as `main.py`).

Expect the boot frame, then every keypress prints to the REPL:
`key: ('digit', '7')` / `key: ('ctl', 'tab_next')`.

## Host-side checks (no hardware needed)

`keys.py` imports nothing from MicroPython, so decode logic can be unit-tested
on any Python 3:

```python
import sys; sys.path.insert(0, "tdeckmax")
from keys import decode_raw
assert decode_raw(129 + 0) == ("digit", "7")   # FIFO key 1 -> 'p' group (T9 7)
```

## Layout

```
tdeckmax/
  __init__.py   version + status
  board.py      pins, I2C/SPI buses, XL9555 gate table (from TDeckMaxBoard.h)
  xl9555.py     IO-expander driver (LILYGO register map)
  tca8418.py    keyboard controller (Adafruit register map, 4x10 matrix)
  keys.py       pure-python key decode: T9 digits + controls (host-testable)
  epd.py        UC8253 / GDEQ031T10 driver (Good Display init sequences)
  ui.py         framebuf screen + full/fast refresh policy (anti-ghost)
apps/
  tabs_calc.py  two-tab ADD/SUB calculator (state machine ported from the C++ app)
```

## Why MicroPython (not CircuitPython)

CircuitPython's ready-made driver ecosystem (incl. an official TCA8418 driver)
is tempting, but the only hard part of this board — the UC8253 e-paper with
fast partial refresh — is DIY in **both** environments, and MicroPython sits
closer to the C reference code we are transcribing (machine.SPI/I2C, direct
register writes, PSRAM). Nothing in this library depends on a CircuitPython-only
module; porting `tca8418.py`/`xl9555.py` to busio if you ever switch is
mechanical. `keys.py` is flavour-agnostic.

## Known gaps (honest)

- e-paper **windowed** partial refresh (small dirty rects) is not implemented —
  only whole-canvas fast refresh. Fine for form UIs; needed for a clock/status
  line later.
- No touch (CST328) driver yet, no LoRa/GPS/4G wrappers. All are downstream of
  the same pattern: XL9555 gate on, then drive the peripheral.
- framebuf's 8x8 font only, for now.
