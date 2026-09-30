# Network bring-up + a tiny LAN file service.
#
# Why: the ESP32-S3's USB-CDC wedges under repeated host open/close sessions
# (documented for this chip), and our own app blocks the USB upload path while
# it runs. So development I/O goes over WiFi instead: push files, read logs,
# never touch the cable.
#
# Protocol (line based, LAN only, token checked). All lines end with \n:
#   TDM <token> LS                  -> "OK\n" then "size /path\n"... then "END\n"
#   TDM <token> GET <path>          -> "OK <len>\n" then exactly <len> raw bytes
#   TDM <token> PUT <path> <len>    -> "OK\n" then <len> raw bytes
#   TDM <token> RM <path>           -> "OK\n"
# Config comes from /wifi.json: ssid, pwd, pi, token.

import json
import os
import socket
import time

try:
    import network
except ImportError:                       # host-side import for tests
    network = None

PORT = 8098
cfg = None
LOG_PATH = "/net.log"


def _log(msg):
    """Log to a file AND stdout.

    The net thread has no console we can read over USB afterwards, so every
    step goes to /net.log too -- otherwise a failed bring-up is invisible and
    we end up guessing at why the device never appeared on the LAN.
    """
    try:
        with open(LOG_PATH, "a") as fh:
            fh.write(str(msg) + "\n")
    except Exception:
        pass
    try:
        print("net:", msg)
    except Exception:
        pass


def load_cfg(path="/wifi.json"):
    global cfg
    try:
        cfg = json.load(open(path))
    except Exception:
        cfg = None
    return cfg


def connect(timeout_s=35):
    """Join the WLAN; returns the IP or None. Never raises.

    Measured on this network: association takes ~13 s, so a 25 s window was
    cutting it fine and a 20 s one failed outright.
    """
    if network is None or not load_cfg():
        _log("connect: no network module, or /wifi.json missing/unreadable")
        return None
    try:
        w = network.WLAN(network.STA_IF)
        w.active(True)
        if not w.isconnected():
            _log("connecting to %r ..." % cfg["ssid"])
            w.connect(cfg["ssid"], cfg["pwd"])
            t0 = time.time()
            last = None
            while not w.isconnected() and time.time() - t0 < timeout_s:
                st = w.status()
                if st != last:
                    _log("  t=%ds status=%s" % (int(time.time() - t0), st))
                    last = st
                time.sleep(0.5)
        if w.isconnected():
            ip = w.ifconfig()[0]
            _log("connected ip=%s" % ip)
            return ip
        _log("gave up after %ss: status=%s" % (timeout_s, w.status()))
        return None
    except Exception as exc:
        _log("connect failed: %s" % exc)
        return None


def beacon(ip):
    """Tell the Pi we're up so it learns our address without USB."""
    try:
        s = socket.socket()
        s.settimeout(4)
        s.connect((cfg["pi"], 8099))
        body = ('{"ip":"%s","port":%d}' % (ip, PORT)).encode()
        s.send(b"POST /boot HTTP/1.1\r\nHost: %s\r\nContent-Length: %d\r\n"
               b"Connection: close\r\n\r\n" % (cfg["pi"].encode(), len(body)))
        s.send(body)
        s.close()
        return True
    except Exception as exc:
        print("net: beacon failed:", exc)
        return False


def _walk(root="/"):
    out = []
    try:
        names = os.listdir(root)
    except OSError:
        return out
    for name in names:
        path = (root.rstrip("/") + "/" + name) if root != "/" else "/" + name
        try:
            is_dir = bool(os.stat(path)[0] & 0x4000)
        except OSError:
            continue
        if is_dir:
            if name == "__pycache__":
                continue
            out.extend(_walk(path))
        else:
            out.append(path)
    return out


def _handle(conn):
    line = conn.readline().decode().strip()
    parts = line.split()
    if len(parts) < 3 or parts[0] != "TDM" or parts[1] != cfg["token"]:
        conn.send(b"ERR auth\n")
        return
    op = parts[2]
    if op == "LS":
        conn.send(b"OK\n")
        for path in _walk("/"):
            try:
                size = os.stat(path)[6]
            except OSError:
                size = 0
            conn.send(("%d %s\n" % (size, path)).encode())
        conn.send(b"END\n")
    elif op == "GET":
        with open(parts[3], "rb") as fh:
            data = fh.read()
        conn.send(("OK %d\n" % len(data)).encode())
        conn.send(data)
    elif op == "PUT":
        path, size = parts[3], int(parts[4])
        parent = path.rsplit("/", 1)[0]
        if parent:
            try:
                os.mkdir(parent)
            except OSError:
                pass
        conn.send(b"OK\n")
        remaining = size
        written = 0
        with open(path, "wb") as fh:
            while remaining > 0:
                chunk = conn.read(min(512, remaining))
                if not chunk:
                    break
                fh.write(chunk)
                remaining -= len(chunk)
                written += len(chunk)
        # Confirm the write: without this the client's "sent N bytes" means only
        # that the bytes left the Pi, which is how a write that never landed
        # still looked successful.
        _log("put %s %d/%d bytes" % (path, written, size))
        conn.send(("DONE %d\n" % written).encode())
    elif op == "MKD":
        try:
            os.mkdir(parts[3])
        except OSError:
            pass
        conn.send(b"OK\n")
    elif op == "EXEC":
        size = int(parts[3])
        code = b""
        while len(code) < size:
            chunk = conn.read(size - len(code))
            if not chunk:
                break
            code += chunk
        import io
        import sys
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            exec(code.decode(), {"__name__": "__main__"})
        except Exception as exc:                             # noqa: BLE001
            sys.print_exception(exc, buf)
        finally:
            sys.stdout = old
        out = buf.getvalue().encode()
        conn.send(("OK %d\n" % len(out)).encode())
        conn.send(out)
    elif op == "RM":
        try:
            os.remove(parts[3])
        except OSError:
            pass
        conn.send(b"OK\n")
    else:
        conn.send(b"ERR op\n")


def serve(port=PORT):
    """Blocking accept loop — run in a thread."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(2)
    while True:
        try:
            conn, _ = s.accept()
        except Exception:
            continue
        try:
            _handle(conn)
        except Exception as exc:
            print("net: request failed:", exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass


def start():
    """Connect + beacon + spawn the file service in a thread. Never fatal."""
    _log("--- net.start() ---")
    ip = connect()
    if not ip:
        _log("no WiFi: staying offline")
        return None
    _log("up as %s" % ip)
    beacon(ip)
    try:
        import _thread
        _thread.start_new_thread(serve, ())
        _log("file service on port %d" % PORT)
    except Exception as exc:
        _log("service not started: %s" % exc)
    return ip
