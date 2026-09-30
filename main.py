# main.py — boots into the notes app: type, and see it on the glass.
#
# Robustness rules learned the hard way:
#   * everything is inside try/except, and the SERVICE LOOP is wrapped per
#     iteration, so one panel timeout can't kill the app
#   * faults go to /panel_error.log (loop) or /boot_error.log (startup)
#   * the keyboard backlight is deliberately left OFF (15 white LEDs on that
#     line; driving it coincided with the device wedging)
#   * keystrokes are coalesced (~120 ms) so a typing burst costs one refresh
#
# Restart it by pressing RST or power-cycling. `mpremote soft-reset` does NOT
# reliably run this file — use a hard reset.

import sys
import time

import framebuf
import machine

from tdeckmax import HEIGHT, WIDTH, keys
from tdeckmax.battery import BQ27220
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.planner import Planner
from tdeckmax.screen import App
from tdeckmax.tca8418 import TCA8418
from apps.notes import NotesScreen

COALESCE_MS = 120
HEARTBEAT_MS = 0        # disabled: the idle repaint was what seized the panel


def start():
    board = Board()
    board.release_resets()
    board.pulse_touch_reset()          # factory pulses touch reset at boot
    board.pulse_keyboard_reset()
    epd = UC8253(board.spi, board.epd_cs, board.epd_dc, board.epd_rst, board.epd_busy)
    board.lights()                     # frontlight ~20% + keyboard backlight ON,
                                       # exactly as the factory firmware does

    kb = TCA8418(board.i2c)
    print("kb.begin():", kb.begin())

    gauge = BQ27220(board.i2c)         # BQ27220 fuel gauge @ 0x55 (battery)

    buf = bytearray(WIDTH * HEIGHT // 8)
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_HLSB)
    # fast_budget=5: five fast edits (~0.76 s) per full refresh (~3.2 s). This is
    # LILYGO's own refresh budget number. It was set to 0 during the USB-wedge
    # hunt on the theory that fast refreshes were destabilising the panel; that
    # theory is gone (the "wedge" was USB modes and a misread reset code), and
    # budget 0 costs ~3 s of full refresh on every single keystroke.
    app = App(Planner(epd, fast_budget=5), fb, buf)
    notes = NotesScreen()
    notes.status = gauge.soc_text() + " "      # battery in the header, as the factory UI has it
    app.push(notes)
    app.paint()

    # Bring the network up in a THREAD: WiFi is slow to associate and must never
    # delay or break the UI. OFF BY DEFAULT: a WiFi connect that cannot succeed
    # blocks the network stack for up to 25 s, which trips the ESP32 task
    # watchdog and reboots the chip (observed as reset_cause=2 in /boot.log, and
    # as "the device switches itself off after ~15 s" from the outside). Create
    # /net_on on the device when there is a verified network to join.
    def bring_up_net():
        try:
            # NOTE: net.py lives INSIDE the package. `import net` raises
            # ModuleNotFoundError here, and because this helper used to just
            # print, that failure was invisible over USB -- the device simply
            # never appeared on the LAN and we had nothing to go on.
            from tdeckmax import net
            net.start()
        except Exception as exc:                                 # noqa: BLE001
            try:
                with open("/net.log", "a") as fh:
                    fh.write("bring-up failed: %r\n" % (exc,))
            except Exception:
                pass

    try:
        import os
        if "net_on" in os.listdir("/"):
            import _thread
            _thread.start_new_thread(bring_up_net, ())
    except Exception:
        pass

    # Diagnostics WITHOUT touching flash in the hot path: per-keystroke log
    # flushes meant a flash write per key with live USB, which is a known
    # ESP32-S3 trigger (micropython #17560: USB interrupts during flash ops).
    # Keep a small in-RAM ring instead, and write one line per boot only.
    cause = machine.reset_cause()
    # esp_reset_reason() values (esp-idf), which is what the esp32 port returns
    # RAW -- NOT the classic ESP8266 numbering our first dict assumed. Verified
    # 2026-09-30: an ordinary reset (host DTR/RTS or the RST button) reports
    # 2 = ESP_RST_EXT, which the old dict mislabelled "WDT" and sent us chasing a
    # watchdog that was never tripping.
    reasons = {0: "UNKNOWN", 1: "PWRON", 2: "EXT/pin", 3: "SW", 4: "PANIC",
               5: "INT_WDT", 6: "TASK_WDT", 7: "WDT", 8: "DEEPSLEEP",
               9: "BROWNOUT", 10: "SDIO"}
    with open("/boot.log", "a") as fh:
        fh.write("boot reset_cause=%s(%s) note=%s\n"
                 % (cause, reasons.get(cause, "?"), machine.wake_reason()))
        fh.write("expander ready after %d ms\n" % board.expander_ready_ms)
        fh.write(gauge.summary() + "\n")
    recent = []                     # last keys seen, RAM only

    state = {"changed": False, "beat": time.ticks_ms(), "keys": 0,
             "armed": time.ticks_ms(), "batt": time.ticks_ms()}

    def revive_if_deaf():
        """The TCA8418 can come up latched: I2C answers, registers look sane,
        and it never queues a single key event. Seen three times on this board.
        If no key has EVER arrived a while after boot, pulse its reset and
        re-init. One flash write per attempt, not per keystroke."""
        if state["keys"] == 0 and time.ticks_diff(time.ticks_ms(), state["armed"]) > 20000:
            board.pulse_keyboard_reset()
            kb.begin()
            with open("/boot.log", "a") as fh:
                fh.write("keyboard re-pulse (still no events)\n")
            state["armed"] = time.ticks_ms()
            app.paint()                 # redraw so the operator sees it did something

    def pump():
        # battery: cheap I2C read every few seconds (2 bytes at 100 kHz)
        if time.ticks_diff(time.ticks_ms(), state["batt"]) > 5000:
            notes.status = gauge.soc_text() + " "
            state["batt"] = time.ticks_ms()
        if kb.available():
            raw = kb.get_event()
            key = keys.decode_raw(raw, letters=True)
            state["keys"] += 1
            recent.append((raw, key))
            if len(recent) > 40:
                del recent[0]
            if key and app.handle(key):
                state["changed"] = True
            deadline = time.ticks_add(time.ticks_ms(), COALESCE_MS)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if kb.available():
                    raw = kb.get_event()
                    key = keys.decode_raw(raw, letters=True)
                    state["keys"] += 1
                    recent.append((raw, key))
                    if len(recent) > 40:
                        del recent[0]
                    if key and app.handle(key):
                        state["changed"] = True
                time.sleep_ms(4)
            if state["changed"]:
                app.paint()
                state["changed"] = False
                state["beat"] = time.ticks_ms()
        if HEARTBEAT_MS and time.ticks_diff(time.ticks_ms(), state["beat"]) > HEARTBEAT_MS:
            app.paint()                     # heartbeat: header tick rises
            state["beat"] = time.ticks_ms()

    while True:
        try:
            pump()
            revive_if_deaf()
        except Exception as exc:            # noqa: BLE001 - never die silently
            with open("/panel_error.log", "a") as fh:
                fh.write("\n--- loop fault ---\n")
                sys.print_exception(exc, fh)
            time.sleep_ms(500)
        time.sleep_ms(4)


try:
    start()
except Exception as exc:                    # noqa: BLE001
    with open("/boot_error.log", "a") as fh:
        fh.write("\n--- boot failure ---\n")
        sys.print_exception(exc, fh)
    raise
