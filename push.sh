#!/bin/bash
# Deploy to the T-Deck Max — no buttons, no replugging, ever.
#
#   ./push.sh                 files only: upload lib/app + reboot   (the daily loop)
#   ./push.sh --reflash       + wipe and reflash MicroPython first  (rare)
#   ./push.sh diag_net.py     deploy that file as main.py instead
#   ./push.sh --reflash notes.py
#
# WHY THIS SHAPE — every rule below is measured on this board, not assumed:
#
#   * esptool ONLY talks to the chip when it is in ROM flash mode
#     (lsusb shows 303a:1001). Pointed at a running app (303a:4001) it dies
#     with "Write timeout" and leaves the port unusable for everything
#     afterwards — that failure is what forced every physical replug.
#
#   * Flash mode is reachable IN SOFTWARE: `machine.bootloader()` over
#     mpremote. mpremote works even while an app is running (it sends Ctrl-C
#     first), so no button presses and no RST-pinhole hunt are needed.
#
#   * After esptool finishes we always reset back OUT of flash mode: mpremote
#     cannot talk to a chip sitting in the ROM bootloader.
#
#   * Never call esptool "just to have a look" while the app is running.
#     Check the USB identity first; the guard below does it for you.
set -u

PORT=${PORT:-/dev/ttyACM0}
LIB="$(cd "$(dirname "$0")" && pwd)"
MP=/home/austin/tdeck-max/firmware/ESP32_GENERIC_S3-20260824-v1.29.0.bin
REFLASH=0
MAIN=main.py
for arg in "$@"; do
    case "$arg" in
        --reflash) REFLASH=1 ;;
        *) MAIN="$arg" ;;
    esac
done
cd "$LIB" || exit 1
[ -f "$MP" ] || { echo "MicroPython image missing: $MP"; exit 1; }

seen()     { lsusb | grep -q "$1"; }                       # 303a:1001 | 303a:4001
wait_for() { for _ in $(seq 1 "${2:-20}"); do seen "$1" && return 0; sleep 1; done; return 1; }
mpremote_run() { timeout 90 python3 -m mpremote connect "$PORT" "$@" >/dev/null 2>&1; }

ensure_flash_mode() {
    seen 303a:1001 && { echo "   already in flash mode"; return 0; }
    echo "   asking the device to enter flash mode (software — no buttons)"
    mpremote_run exec "import machine; machine.bootloader()"
    wait_for 303a:1001 25 && { echo "   flash mode OK"; return 0; }
    echo "!! could not enter flash mode."
    echo "!! Check: cable plugged in, device powered on. Then re-run."
    return 1
}

leave_flash_mode() {
    echo "   resetting out of flash mode"
    timeout 90 python3 -m esptool --chip esp32s3 -p "$PORT" --before no-reset --after hard-reset chip-id >/dev/null 2>&1
    wait_for 303a:4001 25 || { echo "!! device did not come back"; return 1; }
}

if [ "$REFLASH" = "1" ]; then
    echo "== 1/4 enter flash mode =="
    ensure_flash_mode || exit 1
    echo "== 2/4 reflash MicroPython (this WIPES the filesystem) =="
    timeout 180 python3 -m esptool --chip esp32s3 -p "$PORT" --before no-reset erase-flash >/dev/null 2>&1 \
        || { echo "!! erase failed"; exit 1; }
    timeout 300 python3 -m esptool --chip esp32s3 -p "$PORT" --before no-reset --after no-reset write-flash 0 "$MP" 2>&1 \
        | grep -E "Hash of data verified|Wrote" || true
    leave_flash_mode || exit 1
    sleep 3
else
    echo "== 1/4 no reflash: keeping MicroPython and the filesystem =="
fi

echo "== 3/4 upload (one mpremote session) =="
timeout 300 python3 -m mpremote connect "$PORT" \
    fs cp -r tdeckmax : + fs cp -r apps : + fs cp "$MAIN" :main.py + fs cp ../wifi.json :wifi.json \
    || { echo "!! upload failed"; exit 1; }

echo "== 4/4 reboot into the app =="
mpremote_run exec "import machine; machine.reset()" || true   # resetting kills our own link: that error is expected

echo "== done: waiting for the app to boot, then reading /boot.log =="
sleep 8
timeout 60 python3 -m mpremote connect "$PORT" exec "
try:
    print(open('/boot.log').read()[-500:])
except Exception as e:
    print('no /boot.log:', e)
" 2>/dev/null | tail -10
