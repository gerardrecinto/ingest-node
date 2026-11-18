"""Prove a push-only firewall with network namespaces.

Three namespaces stand in for three networks: `ot` (the control host the rules
protect), `ingest` (the data node it pushes to) and `corp`. Every namespace
listens on ports 22, 8080 and 9000, so a blocked connection is blocked by the
rules, not by a closed port. Needs root, `ip`, `nft` and python3.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

RULES = os.path.join(os.path.dirname(__file__), "..", "..", "firewall", "ot-push-only.nft")
PORTS = (22, 8080, 9000)
IP = {"ot_ingest": "10.10.1.1", "ingest": "10.10.1.2", "ot_corp": "10.10.2.1", "corp": "10.10.2.2"}

# (source, target address, port, expected). Expected "connected" or "blocked".
CASES = [
    ("ot", IP["ingest"], 9000, "connected"),
    ("ot", IP["ingest"], 8080, "blocked"),
    ("ot", IP["ingest"], 22, "blocked"),
    ("ot", IP["corp"], 9000, "blocked"),
    ("ingest", IP["ot_ingest"], 22, "blocked"),
    ("ingest", IP["ot_ingest"], 8080, "blocked"),
    ("ingest", IP["ot_ingest"], 9000, "blocked"),
    ("corp", IP["ot_corp"], 22, "blocked"),
    ("corp", IP["ot_corp"], 8080, "blocked"),
    ("corp", IP["ot_corp"], 9000, "blocked"),
]

_LISTEN = """
import socket, sys, threading
def serve(port):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port)); s.listen(16)
    while True:
        c, _ = s.accept()
        data = b""
        while True:
            b = c.recv(65536)
            if not b: break
            data += b
        c.sendall(__import__("hashlib").sha256(data).hexdigest().encode()); c.close()
for p in map(int, sys.argv[1:]):
    threading.Thread(target=serve, args=(p,), daemon=True).start()
print("ready", flush=True)
threading.Event().wait()
"""

_PROBE = """
import socket, sys
ip, port, t = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
s = socket.socket(); s.settimeout(t)
try:
    s.connect((ip, port)); print("connected")
except socket.timeout:
    print("timeout")
except ConnectionRefusedError:
    print("refused")
except OSError as e:
    print("error:" + e.strerror.replace(" ", "_"))
"""


def sh(*cmd, check=True, **kw):
    return subprocess.run(cmd, check=check, capture_output=True, text=True, **kw)


def ns(name, *cmd, **kw):
    return sh("ip", "netns", "exec", name, *cmd, **kw)


def setup():
    for n in ("ot", "ingest", "corp"):
        sh("ip", "netns", "add", n)
        ns(n, "ip", "link", "set", "lo", "up")
    for a, b, ia, ib in (("ot", "ingest", IP["ot_ingest"], IP["ingest"]), ("ot", "corp", IP["ot_corp"], IP["corp"])):
        va, vb = f"v-{a}-{b}"[:15], f"v-{b}-{a}"[:15]
        sh("ip", "link", "add", va, "type", "veth", "peer", "name", vb)
        sh("ip", "link", "set", va, "netns", a)
        sh("ip", "link", "set", vb, "netns", b)
        ns(a, "ip", "addr", "add", f"{ia}/24", "dev", va)
        ns(b, "ip", "addr", "add", f"{ib}/24", "dev", vb)
        ns(a, "ip", "link", "set", va, "up")
        ns(b, "ip", "link", "set", vb, "up")


def teardown():
    for n in ("ot", "ingest", "corp"):
        sh("ip", "netns", "del", n, check=False)


def listeners():
    procs = []
    for n in ("ot", "ingest", "corp"):
        p = subprocess.Popen(["ip", "netns", "exec", n, sys.executable, "-c", _LISTEN, *map(str, PORTS)],
                             stdout=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "ready"
        procs.append(p)
    return procs


def probe(src, ip, port, timeout=1.0):
    out = ns(src, sys.executable, "-c", _PROBE, ip, str(port), str(timeout)).stdout.strip()
    return out


def push_payload(size=1 << 20):
    """Send a payload from ot to ingest:9000 and check the checksum that comes back."""
    data = os.urandom(size)
    code = ("import socket,sys;s=socket.create_connection((sys.argv[1],9000),3);"
            "s.sendall(sys.stdin.buffer.read());s.shutdown(1);print(s.recv(64).decode())")
    p = subprocess.run(["ip", "netns", "exec", "ot", sys.executable, "-c", code, IP["ingest"]],
                       input=data, capture_output=True)
    return p.stdout.decode().strip() == hashlib.sha256(data).hexdigest()


def counters():
    out = json.loads(ns("ot", "nft", "-j", "list", "counters", "table", "inet", "ot_push_only").stdout)
    return {o["counter"]["name"]: o["counter"]["packets"] for o in out["nftables"] if "counter" in o}


def run():
    teardown()
    setup()
    procs = listeners()
    try:
        before = {"ot_to_ingest_8080": probe("ot", IP["ingest"], 8080),
                  "ingest_to_ot_22": probe("ingest", IP["ot_ingest"], 22)}
        ns("ot", "nft", "-f", RULES)
        t0 = time.time()
        with ThreadPoolExecutor(len(CASES)) as pool:
            got = list(pool.map(lambda c: probe(c[0], c[1], c[2]), CASES))
        rows = []
        for (src, ip, port, want), res in zip(CASES, got):
            ok = res == "connected" if want == "connected" else res == "timeout"
            rows.append({"from": src, "to": f"{ip}:{port}", "expected": want, "result": res, "ok": ok})
        return {
            "open_before_rules": before,
            "rows": rows,
            "payload_checksum_ok": push_payload(),
            "counters": counters(),
            "seconds": round(time.time() - t0, 1),
        }
    finally:
        for p in procs:
            p.kill()
        teardown()
