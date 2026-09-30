# Try BOTH visible 2.4 GHz names, with a longer window and status transitions.
#
# status codes (MicroPython): 1000 idle, 1001 connecting, 1010 got IP,
# 201 no AP found, 202 wrong password, 203 connect failed.
#
# Progress goes to /net_test.log so a chip reboot can't lose it.

import json
import socket
import time

import network

log = open("/net_test.log", "w")


def w(msg):
    log.write(str(msg) + "\n")
    log.flush()


cfg = json.load(open("/wifi.json"))
PI = cfg["pi"]
BEACON_PORT = 8099

sta = network.WLAN(network.STA_IF)
sta.active(True)

for ssid in ("TelstraB9E485_EXT", "TelstraB9E485"):
    w("=== trying %r ===" % ssid)
    try:
        sta.disconnect()
    except Exception:                                              # noqa: BLE001
        pass
    time.sleep(1)
    sta.connect(ssid, cfg["pwd"])
    last = None
    start = time.time()
    while time.time() - start < 40:
        st = sta.status()
        if st != last:
            w("  t=%2ds status=%s" % (time.time() - start, st))
            last = st
        if sta.isconnected():
            break
        time.sleep(1)
    if sta.isconnected():
        ip = sta.ifconfig()[0]
        w("  CONNECTED to %r ip=%s rssi=%s" % (ssid, ip, sta.status("rssi") if False else ""))
        w("  RESULT: OK with %r" % ssid)
        try:
            body = ('{"ip":"%s","port":8099}' % ip).encode()
            s = socket.socket()
            s.settimeout(8)
            s.connect((PI, BEACON_PORT))
            s.send(b"POST /boot HTTP/1.1\r\nHost: %s\r\nContent-Length: %d\r\n\r\n"
                   % (PI.encode(), len(body)) + body)
            time.sleep(1)
            reply = s.recv(200)
            s.close()
            w("  beacon sent to %s:%d -> %r" % (PI, BEACON_PORT, reply[:80]))
        except Exception as exc:                                   # noqa: BLE001
            w("  beacon FAILED: %s" % exc)
        break
    else:
        w("  gave up after 40s, final status=%s" % sta.status())

log.close()
