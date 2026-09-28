#!/bin/bash
# Restore drill: prove the 16MB backup can bring a BLANK device back to life.
# Order matters: verify the backup, blank the chip, write it back, verify byte-for-byte,
# then boot it. Any failure aborts before touching the device.
set -u
cd /home/austin/tdeck-max/restore || exit 1
PORT=/dev/ttyACM0
LOG="drill_$(date +%Y%m%d_%H%M%S).log"
ET="python3 -m esptool --chip esp32s3 -p $PORT"

{
  echo "=== RESTORE DRILL start $(date) ==="
  echo "--- step 0: verify the local backup file against its recorded sha256 ---"
  sha256sum -c full-dump.sha256 || { echo "DRILL-ABORT: backup file does not match its hash"; exit 1; }
  echo "--- step 1: is the chip reachable? ---"
  $ET chip-id 2>&1 | grep -E "Connected|Chip type|MAC" 
  echo "--- step 2: erase the whole 16MB flash (simulates a blank, unbootable device) ---"
  time $ET erase-flash 2>&1 | tail -2
  echo "--- step 3: write the 16MB dump back ---"
  time $ET --after no-reset write-flash 0 factory-full-dump.bin 2>&1 | tail -3
  echo "--- step 4: read it back and compare to the file (byte-for-byte proof) ---"
  time $ET --after hard-reset verify-flash 0 factory-full-dump.bin 2>&1 | tail -3
  echo "=== DRILL-RESULT-OK $(date) ==="
} 2>&1 | tee -a "$LOG"
