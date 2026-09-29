#!/usr/bin/env python3
"""Talk to the T-Deck's LAN file service — no USB involved.

    python3 tools/tdm_sync.py ls
    python3 tools/tdm_sync.py get /main.py [local]
    python3 tools/tdm_sync.py put <local> <remote>
    python3 tools/tdm_sync.py rm <remote>
    python3 tools/tdm_sync.py mkd /somedir
    python3 tools/tdm_sync.py repl "<python code>"

The device address comes from ~/tdeck-max/device.json (written by
tools/beacon_listener.py when the device boots).
"""
import json
import os
import socket
import sys

WIFI = os.path.expanduser("~/tdeck-max/wifi.json")
DEVICE = os.path.expanduser("~/tdeck-max/device.json")
PORT = 8098


def target():
    cfg = json.load(open(WIFI))
    ip = None
    if os.path.exists(DEVICE):
        ip = json.load(open(DEVICE)).get("ip")
    ip = ip or cfg.get("last_ip")
    if not ip:
        sys.exit("no device IP yet: start tools/beacon_listener.py, then reset the device")
    return ip, cfg["token"]


def open_conn(ip, timeout=20):
    s = socket.create_connection((ip, PORT), timeout)
    s.settimeout(timeout)
    return s


def read_line(s):
    buf = b""
    while not buf.endswith(b"\n"):
        ch = s.recv(1)
        if not ch:
            break
        buf += ch
    return buf.decode("utf-8", "replace").strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    ip, token = target()
    s = open_conn(ip)

    if cmd == "ls":
        s.sendall(("TDM %s LS\n" % token).encode())
        if read_line(s) != "OK":
            sys.exit("device refused")
        while True:
            line = read_line(s)
            if line == "END":
                break
            size, path = line.split(" ", 1)
            print("%9s  %s" % (size, path))

    elif cmd == "get":
        remote = sys.argv[2]
        local = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(remote)
        s.sendall(("TDM %s GET %s\n" % (token, remote)).encode())
        head = read_line(s).split()
        if head[0] != "OK":
            sys.exit("device said: %s" % " ".join(head))
        want = int(head[1])
        data = b""
        while len(data) < want:
            chunk = s.recv(min(4096, want - len(data)))
            if not chunk:
                break
            data += chunk
        with open(local, "wb") as fh:
            fh.write(data)
        print("got %d bytes -> %s" % (len(data), local))

    elif cmd == "put":
        local, remote = sys.argv[2], sys.argv[3]
        with open(local, "rb") as fh:
            data = fh.read()
        s.sendall(("TDM %s PUT %s %d\n" % (token, remote, len(data))).encode())
        if read_line(s) != "OK":
            sys.exit("device refused the write")
        s.sendall(data)
        print("sent %d bytes -> %s" % (len(data), remote))

    elif cmd == "rm":
        s.sendall(("TDM %s RM %s\n" % (token, sys.argv[2])).encode())
        print(read_line(s))

    elif cmd == "mkd":
        s.sendall(("TDM %s MKD %s\n" % (token, sys.argv[2])).encode())
        print(read_line(s))

    elif cmd == "repl":
        code = sys.argv[2]
        s.sendall(("TDM %s EXEC %d\n" % (token, len(code))).encode())
        if read_line(s) != "OK":
            sys.exit("device refused")
        s.sendall(code.encode())
        head = read_line(s).split()
        if head and head[0] == "OK":
            want = int(head[1])
            data = b""
            while len(data) < want:
                chunk = s.recv(min(4096, want - len(data)))
                if not chunk:
                    break
                data += chunk
            sys.stdout.write(data.decode("utf-8", "replace"))
        else:
            sys.exit("unexpected reply: %s" % " ".join(head))

    else:
        sys.exit(__doc__)

    s.close()


main()
