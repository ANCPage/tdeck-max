#!/usr/bin/env python3
"""Record the T-Deck's LAN address when it beacons at boot.

The device POSTs to this port on every boot, so the Pi learns its DHCP address
without touching USB. Writes ~/tdeck-max/device.json.

Run in the background before resetting the device:
    python3 tools/beacon_listener.py
"""
import json
import os
import socket
import time

OUT = os.path.expanduser("~/tdeck-max/device.json")

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 8099))
sock.listen(4)
print("beacon listener on :8099 -> %s" % OUT, flush=True)

while True:
    conn, addr = sock.accept()
    try:
        data = conn.recv(2048).decode("utf-8", "replace")
        body = data.split("\r\n\r\n", 1)[-1]
        rec = {"ip": addr[0], "when": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            rec.update(json.loads(body))
        except Exception:
            pass
        with open(OUT, "w") as fh:
            json.dump(rec, fh)
        print("beacon: %s" % rec, flush=True)
    except Exception as exc:                                    # noqa: BLE001
        print("beacon error: %s" % exc, flush=True)
    finally:
        conn.close()
