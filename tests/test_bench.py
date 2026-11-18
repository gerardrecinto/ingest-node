import json
import os
import shutil

import pytest

from ingestlab import bench

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
BASE = {"seq_write_1m": {"bw_mib_s": 1000.0, "iops": 1000, "p99_ms": 10.0}}


def test_summarize_fio_json():
    fio = json.load(open(os.path.join(FIX, "fio_seq_write.json")))
    assert bench.summarize(fio) == {"bw_mib_s": 500.0, "iops": 500, "p99_ms": 12.0}


def test_gate_passes_small_noise():
    cand = {"seq_write_1m": {"bw_mib_s": 900.0, "iops": 900, "p99_ms": 12.0}}
    assert bench.gate(BASE, cand) == []


def test_gate_fails_bandwidth_and_latency():
    cand = {"seq_write_1m": {"bw_mib_s": 700.0, "iops": 700, "p99_ms": 20.0}}
    fails = bench.gate(BASE, cand)
    assert len(fails) == 2 and "bandwidth" in fails[0] and "p99" in fails[1]


def test_gate_ignores_improvements_and_flags_missing():
    better = {"seq_write_1m": {"bw_mib_s": 2000.0, "iops": 2000, "p99_ms": 1.0}}
    assert bench.gate(BASE, better) == []
    assert "missing" in bench.gate(BASE, {})[0]


@pytest.mark.skipif(shutil.which("fio") is None, reason="fio not installed")
def test_real_fio_and_throttled_run_fails_the_gate(tmp_path):
    base = bench.bench_all(str(tmp_path), size="32M", runtime=2, direct=False)
    assert all(v["bw_mib_s"] > 0 for v in base.values())
    slow = bench.bench_all(str(tmp_path), size="32M", runtime=2, direct=False, rate_iops=50)
    assert bench.gate(base, slow), "a run capped at 50 IOPS must fail against an uncapped baseline"
