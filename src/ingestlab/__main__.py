import argparse
import json
import sys

from . import bench, fw


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ingestlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fw", help="prove the push-only firewall in network namespaces (root)")
    f.add_argument("--json")
    b = sub.add_parser("bench", help="run fio on a directory and gate against a baseline")
    b.add_argument("directory")
    b.add_argument("--out")
    b.add_argument("--baseline")
    b.add_argument("--rate-iops", type=int, help="cap IOPS to simulate a slow disk")
    b.add_argument("--buffered", action="store_true", help="no O_DIRECT (for tmpfs or overlay)")
    b.add_argument("--bw-drop", type=float, default=0.20)
    b.add_argument("--p99-rise", type=float, default=0.50)
    a = ap.parse_args(argv)
    if a.cmd == "fw":
        res = fw.run()
        for r in res["rows"]:
            print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['from']:>6} -> {r['to']:<16} {r['result']}")
        print("payload checksum ok:", res["payload_checksum_ok"], "| counters:", res["counters"])
        if a.json:
            json.dump(res, open(a.json, "w"), indent=1)
        return 0 if all(r["ok"] for r in res["rows"]) and res["payload_checksum_ok"] else 1
    run = bench.bench_all(a.directory, direct=not a.buffered, rate_iops=a.rate_iops)
    print(json.dumps(run, indent=1))
    if a.out:
        json.dump(run, open(a.out, "w"), indent=1)
    if a.baseline:
        fails = bench.gate(json.load(open(a.baseline)), run, a.bw_drop, a.p99_rise)
        for x in fails:
            print("FAIL", x)
        return 1 if fails else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
