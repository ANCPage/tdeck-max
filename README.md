# T-Deck Max apps (LILYGO ESP32-S3 e-paper PDA)

Two flavours of the same demo app, built/checked automatically by GitHub Actions:

- `tabs-calc/` — **C++ / PlatformIO / Arduino** app (two-tab ADD/SUB calculator).
  Official LILYGO toolchain (`espressif32@6.5.0`), self-contained, no LILYGO repo needed.
  Build: `cd tabs-calc && pio run` · Upload: `pio run -t upload` · See its README.
- `tdeckmax-lib/` — **MicroPython driver library** (`tdeckmax/`) + Python port of the
  same calculator (`apps/tabs_calc.py`). Drivers transcribed from verified primary
  sources; hardware-untested — VERIFY markers in the code. See its README.

CI: `.github/workflows/build.yml` — real compile proof for the C++ app and
syntax + key-decode checks for the Python library, on every push.
