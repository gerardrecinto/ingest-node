"""Run fio, boil the JSON down to three numbers, and gate against a baseline."""
import json
import subprocess

JOBS = {
    "seq_write_1m": ["--rw=write", "--bs=1M", "--iodepth=16"],
    "rand_read_4k": ["--rw=randread", "--bs=4k", "--iodepth=32"],
}


def run_fio(directory, name, size="256M", runtime=5, direct=True, rate_iops=None):
    cmd = ["fio", f"--name={name}", f"--filename={directory}/{name}.dat", f"--size={size}",
           f"--runtime={runtime}", "--time_based", "--ioengine=libaio", f"--direct={int(direct)}",
           "--output-format=json", *JOBS[name]]
    if rate_iops:
        cmd.append(f"--rate_iops={rate_iops}")
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return json.loads(out[out.index("{"):])


def summarize(fio_json):
    job = fio_json["jobs"][0]
    side = job["write"] if job["write"]["io_bytes"] else job["read"]
    pct = side["clat_ns"]["percentile"] if "clat_ns" in side else None
    p99 = pct["99.000000"] / 1e6 if pct else side["clat"]["percentile"]["99.000000"] / 1e3
    return {"bw_mib_s": round(side["bw"] / 1024, 1), "iops": round(side["iops"]), "p99_ms": round(p99, 3)}


def gate(base, cand, bw_drop=0.20, p99_rise=0.50):
    """Return a list of failures. Empty means the candidate passes."""
    fails = []
    for name, b in base.items():
        c = cand.get(name)
        if c is None:
            fails.append(f"{name}: missing from the new run")
            continue
        if c["bw_mib_s"] < b["bw_mib_s"] * (1 - bw_drop):
            fails.append(f"{name}: bandwidth {b['bw_mib_s']} -> {c['bw_mib_s']} MiB/s (limit -{int(bw_drop * 100)}%)")
        if c["p99_ms"] > b["p99_ms"] * (1 + p99_rise):
            fails.append(f"{name}: p99 {b['p99_ms']} -> {c['p99_ms']} ms (limit +{int(p99_rise * 100)}%)")
    return fails


def bench_all(directory, **kw):
    return {name: summarize(run_fio(directory, name, **kw)) for name in JOBS}
