#!/bin/bash
# Deterministic deploy — minimum USB churn, in this order:
#   1. reflash MicroPython (this also WIPES the filesystem, so no half-running
#      app can fight us for the CPU/panel while we upload)
#   2. upload library + app + main into an idle REPL
#   3. boot it
#
# One esptool pass + one mpremote session. Both host-reset types
# (DTR/RTS resets, port closes) are known ESP32-S3 USB triggers, so we keep
# the count as low as possible.
#
# Usage:  ./push.sh
set -u

PORT=/dev/ttyACM0
LIB="$(cd "$(dirname "$0")" && pwd)"
MP=/home/austin/tdeck-max/firmware/ESP32_GENERIC_S3-20260824-v1.29.0.bin
MAIN="${1:-main.py}"          # first arg lets you deploy a diagnostic as main.py
cd "$LIB" || exit 1

if [ ! -f "$MP" ]; then
    echo "MicroPython image missing: $MP"; exit 1
fi

echo "== 1/3 flash MicroPython (wipes the FS) =="
python3 -m esptool --chip esp32s3 -p "$PORT" erase-flash || {
    echo "!! chip not reachable — unplug/replug the USB-C cable and retry"; exit 1; }
python3 -m esptool --chip esp32s3 -p "$PORT" --after hard-reset write-flash 0 "$MP" || exit 1

echo "== 2/3 let the REPL come up (no app present: FS was wiped) =="
sleep 4

echo "== 3/3 upload everything in ONE mpremote session, then hard reset =="
python3 -m mpremote connect "$PORT" \
    fs cp -r tdeckmax : + fs cp -r apps : + fs cp ../wifi.json :wifi.json + fs cp "$MAIN" :main.py || exit 1

# mpremote's own reset does NOT reliably run main.py — use a real hard reset.
python3 -m esptool --chip esp32s3 -p "$PORT" --after hard-reset --before default-reset chip-id >/dev/null 2>&1

echo "== done: app booted. Read /boot.log for reset_cause =="
