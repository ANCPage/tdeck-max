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
        # Read the full request: a single recv() often returns only the headers,
        # which is how my own localhost test wrote "127.0.0.1" into device.json
        # and sent every tool chasing the Pi itself.
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        want = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    want = int(line.split(b":", 1)[1])
                except Exception:                                # noqa: BLE001
                    want = 0
        while len(body) < want:
            chunk = conn.recv(1024)
            if not chunk:
                break
            body += chunk

        rec = {"ip": addr[0], "when": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            rec.update(json.loads(body.decode("utf-8", "replace")))
        except Exception:                                        # noqa: BLE001
            pass
        if str(rec.get("ip", "")).startswith("127."):
            print("ignoring loopback beacon (test traffic, not the device)", flush=True)
            continue
        with open(OUT, "w") as fh:
            json.dump(rec, fh)
        print("beacon: %s" % rec, flush=True)
    except Exception as exc:                                    # noqa: BLE001
        print("beacon error: %s" % exc, flush=True)
    finally:
        conn.close()
