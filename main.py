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
    app = App(Planner(epd, fast_budget=0), fb, buf)
    notes = NotesScreen()
    notes.status = gauge.soc_text() + " "      # battery in the header, as the factory UI has it
    app.push(notes)
    app.paint()

    # Bring the network up in a THREAD: WiFi is slow to associate and must never
    # delay or break the UI. Once up, the device beacons its IP to the Pi and
    # serves the LAN file service, so development stops depending on the fragile
    # USB-CDC.
    def bring_up_net():
        try:
            import net
            net.start()
        except Exception as exc:                                 # noqa: BLE001
            print("net bring-up failed:", exc)

    try:
        import _thread
        _thread.start_new_thread(bring_up_net, ())
    except Exception:
        pass

    # Diagnostics WITHOUT touching flash in the hot path: per-keystroke log
    # flushes meant a flash write per key with live USB, which is a known
    # ESP32-S3 trigger (micropython #17560: USB interrupts during flash ops).
    # Keep a small in-RAM ring instead, and write one line per boot only.
    cause = machine.reset_cause()
    reasons = {0: "PWRON", 1: "HARD", 2: "WDT", 3: "DEEPSLEEP", 4: "SOFT",
               5: "BROWNOUT", 6: "SDIO"}
    with open("/boot.log", "a") as fh:
        fh.write("boot reset_cause=%s(%s) note=%s\n"
                 % (cause, reasons.get(cause, "?"), machine.wake_reason()))
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
