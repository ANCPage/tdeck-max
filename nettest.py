# WiFi reachability test for the T-Deck Max.
#
# Writes progress to /net_test.log as it goes, so the result survives even if
# the chip reboots mid-connect (a failing connect can trip the task watchdog).
#
# Run:  mpremote connect /dev/ttyACM0 run nettest.py
# Read: mpremote connect /dev/ttyACM0 fs cat :net_test.log

import json
import time

import network

log = open("/net_test.log", "w")


def w(msg):
    log.write(str(msg) + "\n")
    log.flush()


try:
    cfg = json.load(open("/wifi.json"))
    w("cfg ssid=%r pi=%s" % (cfg["ssid"], cfg["pi"]))

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        w("active=%s mac=%s" % (sta.active(), ":".join("%02x" % b for b in sta.config("mac"))))
    except Exception as exc:                                       # noqa: BLE001
        w("mac unreadable: %s" % exc)

    try:
        aps = sta.scan()
        w("scan: %d access points" % len(aps))
        for ap in aps:
            ssid = ap[0].decode("utf-8", "replace") if isinstance(ap[0], bytes) else ap[0]
            if ssid:
                w("  ssid=%r rssi=%d chan=%d" % (ssid, ap[3], ap[2]))
    except Exception as exc:                                       # noqa: BLE001
        w("scan failed: %s" % exc)

    w("connecting to %r ..." % cfg["ssid"])
    sta.connect(cfg["ssid"], cfg["pwd"])
    start = time.time()
    while not sta.isconnected() and time.time() - start < 20:
        time.sleep(0.5)

    w("connected=%s status=%s" % (sta.isconnected(), sta.status()))
    if sta.isconnected():
        w("ifconfig=%s" % (sta.ifconfig(),))
        w("RESULT: OK")
    else:
        # status: 1 idle, 2 connecting, 3 wrong password, 4 no AP found, ...
        w("RESULT: FAILED (status=%s) -> 3 = wrong password, 201 = no AP found"
          % sta.status())
except Exception as exc:                                           # noqa: BLE001
    import sys
    w("EXCEPTION: %s" % exc)
    sys.print_exception(exc, log)
finally:
    log.close()
