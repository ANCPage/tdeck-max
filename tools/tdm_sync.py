#!/usr/bin/env python3
"""Talk to the T-Deck's LAN file service — no USB involved.

    python3 tools/tdm_sync.py ls
    python3 tools/tdm_sync.py get /main.py [local]
    python3 tools/tdm_sync.py put <local> <remote>
    python3 tools/tdm_sync.py rm <remote>
    python3 tools/tdm_sync.py mkd /somedir
    python3 tools/tdm_sync.py repl "<python code>"
    python3 tools/tdm_sync.py reboot
    python3 tools/tdm_sync.py deploy [main.py]

`deploy` is the wireless equivalent of push.sh: it uploads the library, the
apps, main.py and wifi.json over the LAN, reboots the device, then waits for it
to come back by reading /boot.log — so USB is not needed at all.

The device address comes from ~/tdeck-max/device.json (written by
tools/beacon_listener.py when the device boots).
"""
import json
import os
import socket
import sys
import time

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


def rpath(p):
    """Device path from a friendly one: 'boot.log', ':boot.log', '/boot.log'."""
    p = p.lstrip(":")
    return p if p.startswith("/") else "/" + p


def put_file(ip, token, local, remote, attempts=3):
    """Upload one file; raises unless the device confirms what it wrote.

    Retries: the device's service is a small single-threaded accept loop, and
    a connect that lands while it is mid-reply just times out. Observed once,
    so it gets a couple of retries rather than failing a whole deploy.
    """
    data = open(local, "rb").read()
    last = None
    for attempt in range(attempts):
        s = None
        try:
            s = open_conn(ip)
            s.sendall(("TDM %s PUT %s %d\n" % (token, remote, len(data))).encode())
            if read_line(s) != "OK":
                raise RuntimeError("device refused %s" % remote)
            s.sendall(data)
            ack = read_line(s)
            if not ack.startswith("DONE"):
                raise RuntimeError("%s not confirmed: %r" % (remote, ack))
            return ack
        except Exception as exc:                                   # noqa: BLE001
            last = exc
            if attempt + 1 < attempts:
                time.sleep(2)
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:                                  # noqa: BLE001
                    pass
    raise RuntimeError("PUT %s failed after %d attempts: %s" % (remote, attempts, last))


def get_text(ip, token, path):
    """Fetch a file as text, or None (used as the is-it-alive probe)."""
    s = open_conn(ip)
    try:
        s.sendall(("TDM %s GET %s\n" % (token, path)).encode())
        head = read_line(s).split()
        if not head or head[0] != "OK":
            return None
        want = int(head[1])
        data = b""
        while len(data) < want:
            chunk = s.recv(min(4096, want - len(data)))
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return None
    finally:
        s.close()


def exec_code(ip, token, code):
    """Run code on the device. A reboot tears the connection down: expected."""
    if isinstance(code, str):
        code = code.encode()
    try:
        s = open_conn(ip)
    except Exception:                                              # noqa: BLE001
        return None
    try:
        s.sendall(("TDM %s EXEC %d\n" % (token, len(code))).encode())
        s.sendall(code)
        return read_line(s)
    except Exception:                                              # noqa: BLE001
        return None
    finally:
        try:
            s.close()
        except Exception:                                          # noqa: BLE001
            pass


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
        remote = rpath(sys.argv[2])
        local = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(remote)
        s.sendall(("TDM %s GET %s\n" % (token, remote)).encode())
        head = read_line(s).split()
        if not head or head[0] != "OK":
            sys.exit("device said: %s" % (" ".join(head) or "nothing (does that file exist?)"))
        want = int(head[1])
        data = b""
        while len(data) < want:
            chunk = s.recv(min(4096, want - len(data)))
            if not chunk:
                break
            data += chunk
        with open(local, "wb") as fh:
            fh.write(data)
        print("got %d of %d bytes -> %s" % (len(data), want, local))

    elif cmd == "put":
        local, remote = sys.argv[2], rpath(sys.argv[3])
        with open(local, "rb") as fh:
            data = fh.read()
        s.sendall(("TDM %s PUT %s %d\n" % (token, remote, len(data))).encode())
        if read_line(s) != "OK":
            sys.exit("device refused the write")
        s.sendall(data)
        ack = read_line(s)                      # the device confirms what it wrote
        print("put %s: %s" % (remote, ack or "no confirmation (write may have failed)"))
        if not ack.startswith("DONE"):
            sys.exit(1)

    elif cmd == "deploy":
        main_py = sys.argv[2] if len(sys.argv) > 2 else "main.py"
        files = []
        for base in ("tdeckmax", "apps"):
            if os.path.isdir(base):
                for name in sorted(os.listdir(base)):
                    if name.endswith(".py"):
                        files.append((os.path.join(base, name),
                                      "/%s/%s" % (base, name)))
        files.append((main_py, "/main.py"))
        cfg_path = os.path.join("..", "wifi.json")
        if os.path.exists(cfg_path):
            files.append((cfg_path, "/wifi.json"))

        for local, remote in files:
            print("  %-30s %s" % (remote, put_file(ip, token, local, remote)))
        print("uploaded %d files over WiFi" % len(files))

        print("rebooting the device ...")
        exec_code(ip, token, "import machine; machine.reset()")
        for _ in range(30):
            time.sleep(3)
            txt = get_text(ip, token, "/boot.log")
            if txt:
                print("device is back. /boot.log tail:")
                for line in txt.splitlines()[-4:]:
                    print("   ", line)
                break
        else:
            print("no reply after 90 s - check /net.log on the device")

    elif cmd == "rm":
        s.sendall(("TDM %s RM %s\n" % (token, sys.argv[2])).encode())
        print(read_line(s))

    elif cmd == "mkd":
        s.sendall(("TDM %s MKD %s\n" % (token, sys.argv[2])).encode())
        print(read_line(s))

    elif cmd == "repl":
        code = sys.argv[2]
        # Send the header AND the payload together: the device reads the code
        # before it answers, so waiting for "OK" first deadlocks (that was the
        # "device refused" bug).
        s.sendall(("TDM %s EXEC %d\n" % (token, len(code))).encode())
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
            sys.exit("unexpected reply: %s" % (" ".join(head) or "nothing"))

    elif cmd == "reboot":
        print("rebooting the device over WiFi ...")
        exec_code(ip, token, "import machine; machine.reset()")
        for _ in range(30):
            time.sleep(3)
            txt = get_text(ip, token, "/boot.log")
            if txt:
                print("device is back:")
                for line in txt.splitlines()[-4:]:
                    print("   ", line)
                break
        else:
            print("no reply after 90 s - check /net.log on the device")

    else:
        sys.exit(__doc__)

    s.close()


if __name__ == "__main__":
    main()
