"""Client for the live Blender MCP add-on socket (127.0.0.1:9876).

Usage:
  python3 bb.py file.py [more.py ...]   # run each script with execute_code (shared prelude prepended)
  python3 bb.py -c "print(bpy.data.filepath)"
  python3 bb.py --cmd get_viewport_screenshot --params '{"max_size":1200,"filepath":"/tmp/x.png"}'
"""
import argparse
import json
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def send(cmd, params, timeout=1800):
    with socket.create_connection(("127.0.0.1", 9876), timeout=15) as c:
        c.settimeout(timeout)
        c.sendall(json.dumps({"type": cmd, "params": params}).encode())
        buf = bytearray()
        while True:
            chunk = c.recv(1 << 20)
            if not chunk:
                raise RuntimeError("Blender closed the socket before responding")
            buf.extend(chunk)
            try:
                return json.loads(buf)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="*")
    p.add_argument("-c", "--code")
    p.add_argument("--cmd", default="execute_code")
    p.add_argument("--params", default="{}")
    p.add_argument("--no-prelude", action="store_true")
    a = p.parse_args()

    prelude = ""
    pre = HERE / "prelude.py"
    if not a.no_prelude and pre.exists():
        prelude = pre.read_text() + "\n"

    jobs = []
    if a.cmd != "execute_code":
        jobs.append((a.cmd, json.loads(a.params), a.cmd))
    if a.code:
        jobs.append(("execute_code", {"code": prelude + a.code}, "<inline>"))
    for f in a.files:
        jobs.append(("execute_code", {"code": prelude + Path(f).read_text()}, f))

    rc = 0
    for cmd, params, label in jobs:
        t0 = time.time()
        r = send(cmd, params)
        dt = time.time() - t0
        if r.get("status") == "error":
            rc = 1
            msg = r.get("message", "")
            try:
                m = json.loads(msg)
                print(f"### ERROR in {label} ({dt:.1f}s): {m.get('exception_type')}: {m.get('message')}")
                print(m.get("traceback", ""))
            except Exception:
                print(f"### ERROR in {label} ({dt:.1f}s): {msg}")
            break
        res = r.get("result")
        if isinstance(res, dict) and "result" in res:
            sys.stdout.write(str(res["result"]))
        else:
            print(json.dumps(res, indent=1)[:20000])
        print(f"### ok {label} ({dt:.1f}s)")
    sys.exit(rc)


if __name__ == "__main__":
    main()
