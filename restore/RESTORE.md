# T-Deck Max restore runbook

Device as dumped: **2026-09-28**, factory firmware, bootloader + app + NVS + SPIFFS all captured below.

## Files in this directory

| File | Size (bytes) | sha256 |
|---|---|---|
| `factory-full-dump.bin` | 16,777,216 | `d3d1bbff808d9a853ad516c0b00305ed6148703f262e7c9294e7b5abbd72a8a4` |
| `T-Deck-MAX_V3.1_20260313.bin` (LILYGO app-only, NOT our firmware) | 3,298,944 | `8278ba63da0eeac64b58d4b46e3043c1e0f3356993d7c347587db14fb6ae8a52` |

**The full dump is the real insurance.** The published LILYGO `.bin` is an *application image only*
(3 segments, app-only) — it does **not** contain a bootloader or partition table, so flashing it at
offset 0 would erase the bootloader. It also is **not** the same build this device shipped with
(device app entry point `0x40377a8c` vs published `0x403c98d0`), so it is not an exact restore.

## Partition layout (parsed out of our own dump)

Partition table at `0x8000`; bootloader at `0x0`; app image at `0x10000`.

| Label | Type | Subtype | Offset | Size |
|---|---|---|---|---|
| nvs | data | nvs | `0x9000` | `0x5000` (20 KB) |
| otadata | data | ota | `0xe000` | `0x2000` (8 KB) |
| app0 | app | ota_0 | `0x10000` | `0x640000` (6.25 MB) |
| app1 | app | ota_1 | `0x650000` | `0x640000` (6.25 MB) |
| spiffs | data | spiffs | `0xc90000` | `0x360000` (3.38 MB) |
| coredump | data | coredump | `0xff0000` | `0x10000` (64 KB) |

Note the SPIFFS partition — 3.38 MB of on-device files live there, and it is only preserved by the
full dump.

## 1. Enter download mode (hardware, no software needed)

1. Hold **BOOT**.
2. Tap **RST**, then release **RST**.
3. Release **BOOT**.

Check it worked: `python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 chip-id`
→ should print `ESP32-S3 (QFN56) (revision v0.2)`, MAC `10:51:db:40:62:e4`.

## 2. Full restore (bootloader + app + NVS + SPIFFS — everything)

```bash
cd ~/tdeck-max/restore
sha256sum -c full-dump.sha256          # verify the backup before trusting it
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write-flash 0 factory-full-dump.bin
# then tap RST
```
16 MB write ≈ 3 minutes at ~854 kbit/s.

## 3. App-only restore (factory demo UI back, keeps NVS/SPIFFS intact)

```bash
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 write-flash 0x10000 T-Deck-MAX_V3.1_20260313.bin
```

## Rules that make bricking impossible

- The ESP32-S3 **ROM bootloader lives in mask ROM** — it cannot be erased, and the BOOT+RST combo
  always reaches it (proven: esptool connected and read all 16 MB over it).
- A failed/blank app makes the chip fall into that ROM download mode instead of running anything, so
  there is always a way back in.
- **Never burn eFuses** (`--chip esp32s3 burn-efuse`, secure boot, flash encryption, disabling
  USB-JTAG). That is the only irreversible class of operation on this chip. Everything else here is
  a write that this dump undoes.

## Restore drill — executed 2026-09-28 18:34–18:37 AEST: **PASSED**

Walked the worst case on purpose: verified the backup, **erased all 16 MB** (blank, unbootable device),
wrote the dump back, read it back and compared.

| Step | Result | Time |
|---|---|---|
| 0. verify backup sha256 | `factory-full-dump.bin: OK` | — |
| 1. chip reachable over USB-JTAG | ESP32-S3 rev v0.2, MAC `10:51:db:40:62:e4` | — |
| 2. `erase-flash` (16 MB) | erased (device blank) | 37 s |
| 3. `write-flash 0 factory-full-dump.bin` | `Hash of data verified.` | 1 m 51 s |
| 4. `verify-flash 0 factory-full-dump.bin` | `Verification successful (digest matched).` | 28 s |
| 5. boot after restore | normal factory init: PSRAM, XL9555, ES8311 codec, SX1262 OK, GPS task, BHI260AP IMU | — |

Conclusion: **a completely blanked device is restored from this dump and boots normally.** The undo
is proven, not theoretical. Script: `drill.sh`; log: `drill_*.log`.

## Related facts


- Sleep screen → deep sleep; **wake = press BOOT** (`EXT1`, GPIO0 active low). Shutdown screen cuts
  the PMIC rails (`PPM.shutdown()`), needs a press-and-hold power-on afterwards.
- GPS antenna is **external** — IPEX connector `J2`; none ships in the box.
- LoRa antenna = the stock T-shaped one, IPEX at the case cut-out; internal PCB antenna is the
  firmware default (`XL9555` P0.4 HIGH = internal, LOW = external).
- SD card mount fails at boot when no card is inserted (expected).
