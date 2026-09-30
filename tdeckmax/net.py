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
LAST_IP = None          # set once we are on the network; the UI shows it
STA = None              # the WLAN object, owned by begin()/poll()
_SERVED = False         # service + beacon started once
_TRIES = 0              # association retries (capped backoff)
_NEXT_TRY = 0           # ticks deadline for the next retry
_LAST_BEACON = 0        # ticks of the last beacon
BEACON_EVERY_MS = 120_000   # re-beacon every 2 min so the Pi tracks address changes
_CONNECT_AT = 0         # ticks when connect() was last issued (stuck-connecting watchdog)
STUCK_MS = 45_000       # a connect still "connecting" after this is treated as failed
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
        _log("beacon sent (%s -> %s:8099)" % (ip, cfg["pi"]))
        return True
    except Exception as exc:
        # Logged, not printed: a silent beacon failure is how the Pi ended up
        # with a stale address while everything looked healthy.
        _log("beacon FAILED to %s:8099: %s" % (cfg.get("pi"), exc))
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


def _read_line(conn, limit=256):
    """Read one \\n-terminated line byte by byte.

    Deliberately NOT conn.readline(): a buffered readline can swallow part of
    the payload that follows, and this protocol is header-then-raw-bytes.
    """
    buf = b""
    while len(buf) < limit:
        ch = conn.read(1)
        if not ch or ch == b"\n":
            break
        buf += ch
    return buf.decode("utf-8", "replace").strip()


def _handle(conn):
    line = _read_line(conn)
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
        # Write to a temp file and only replace the target once the WHOLE
        # payload has arrived. A client that gives up mid-transfer used to leave
        # the target truncated -- that is how /tdeckmax/__init__.py got gutted
        # to 0 bytes on 2026-09-30 and would have broken the next boot.
        tmp = path + ".part"
        conn.send(b"OK\n")
        remaining = size
        written = 0
        try:
            with open(tmp, "wb") as fh:
                while remaining > 0:
                    chunk = conn.read(min(512, remaining))
                    if not chunk:
                        break
                    fh.write(chunk)
                    remaining -= len(chunk)
                    written += len(chunk)
        except Exception as exc:                                   # noqa: BLE001
            _log("put %s interrupted after %d bytes: %s" % (path, written, exc))

        if written == size and size > 0:
            try:
                os.remove(path)
            except OSError:
                pass
            os.rename(tmp, path)
            _log("put %s ok (%d bytes)" % (path, written))
        else:
            _log("put %s INCOMPLETE (%d/%d) - old file kept" % (path, written, size))
            try:
                os.remove(tmp)
            except OSError:
                pass
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
            # A timeout is essential: without one, one client that vanishes
            # mid-request blocks the whole (single-threaded) service, and every
            # later connection just queues and times out -- the failure mode
            # that made PUT mysteriously "not answer" on 2026-09-30.
            try:
                conn.settimeout(15)
            except Exception:                                      # noqa: BLE001
                pass
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


def begin():
    """START an association without blocking.

    w.connect() hands the work to the ESP-IDF WiFi stack; the waiting is what
    used to block. The app calls poll() from its own loop instead, so a slow or
    failing network can never freeze the UI (which is exactly what happened when
    bring-up ran at boot as a blocking thread).
    """
    global STA
    if network is None or not load_cfg():
        _log("begin: no network module, or /wifi.json missing")
        return False
    STA = network.WLAN(network.STA_IF)
    try:
        STA.active(True)
    except Exception as exc:                                       # noqa: BLE001
        _log("begin: active() failed: %s" % exc)
        return False
    # Turn radio power-save OFF. By default the ESP32 naps its radio between
    # beacons; on this extender that showed up as the device silently vanishing
    # from the LAN for minutes at a time, which looked like a code bug.
    for pm_value in (getattr(network.WLAN, "PM_NONE", None), 0):
        if pm_value is None:
            continue
        try:
            STA.config(pm=pm_value)
            _log("power-save disabled (pm=%r)" % (pm_value,))
            break
        except Exception as exc:                                   # noqa: BLE001
            _log("pm config %r failed: %s" % (pm_value, exc))
    if STA.isconnected():
        return True
    try:
        _log("begin: connecting to %r" % cfg["ssid"])
        STA.connect(cfg["ssid"], cfg["pwd"])
        globals()["_CONNECT_AT"] = time.ticks_ms()
        return True
    except Exception as exc:                                       # noqa: BLE001
        _log("begin: connect() raised: %s" % exc)
        return False


def poll():
    """Called from the app loop. Returns the IP once up; starts the beacon and
    the file service exactly once. Never blocks, never raises."""
    global LAST_IP, _SERVED, _TRIES, _NEXT_TRY, _LAST_BEACON
    if STA is None:
        return None
    try:
        if STA.isconnected():
            ip = STA.ifconfig()[0]
            _TRIES = 0
            now = time.ticks_ms()
            if not _SERVED:
                _SERVED = True
                LAST_IP = ip
                _log("connected ip=%s" % ip)
                beacon(ip)
                _LAST_BEACON = now
                try:
                    import _thread
                    _thread.start_new_thread(serve, ())
                    _log("file service on port %d" % PORT)
                except Exception as exc:                           # noqa: BLE001
                    _log("service not started: %s" % exc)
            elif time.ticks_diff(now, _LAST_BEACON) > BEACON_EVERY_MS:
                # Keep the Pi's record fresh: DHCP gave the device a different
                # address more than once today, and a one-shot boot beacon left
                # us connecting to a stale IP ("No route to host").
                if ip != LAST_IP:
                    _log("address changed: %s -> %s" % (LAST_IP, ip))
                    LAST_IP = ip
                beacon(ip)
                _LAST_BEACON = now
            return ip

        # Not connected. Two failure shapes need different handling:
        #  * the stack goes IDLE (1000) or gives up (201/202/203), or
        #  * it sits in 1001 "connecting" FOREVER -- observed on this extender,
        #    where the device then never retried and simply stayed off the LAN.
        # Both re-arm the association, with a capped backoff.
        st = STA.status()
        now = time.ticks_ms()
        stuck = (st == 1001 and _CONNECT_AT
                 and time.ticks_diff(now, _CONNECT_AT) > STUCK_MS)
        if (st in (1000, 201, 202, 203) or stuck) and time.ticks_diff(now, _NEXT_TRY) >= 0:
            # Gentle on purpose: hammering the AP every 5 s produced a run of
            # status=202 (wrong password) rejections on this extender, i.e. the
            # retry storm itself was making things worse. 30 s, doubling to 5 min.
            wait = min(300, 30 * (2 ** min(_TRIES, 3)))
            _TRIES += 1
            _NEXT_TRY = time.ticks_add(now, wait * 1000)
            _log("retry %d (status=%s%s): re-arming, next in %ds"
                 % (_TRIES, st, " stuck" if stuck else "", wait))
            try:
                if stuck:
                    STA.disconnect()        # clear the half-open attempt first
                STA.connect(cfg["ssid"], cfg["pwd"])
                _CONNECT_AT = now
            except Exception as exc:                               # noqa: BLE001
                _log("retry connect raised: %s" % exc)
        return None
    except Exception:                                              # noqa: BLE001
        return None


def start():
    """Blocking bring-up for scripts: connect + beacon + service. Never fatal."""
    if not begin():
        return None
    import time as _t
    t0 = _t.time()
    while _t.time() - t0 < 35:
        ip = poll()
        if ip:
            return ip
        _t.sleep(0.5)
    _log("gave up after 35s: status=%s" % STA.status())
    return None
