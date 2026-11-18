"""The Pages demo re-implements gate() in JavaScript on real CI results. Keep it honest."""
import json
import os
import shutil
import subprocess

import pytest

from ingestlab import bench

PAGE = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")
JS = os.path.join(os.path.dirname(__file__), "page_parity.js")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_gate_matches_python():
    res = json.loads(subprocess.run(["node", JS, PAGE], check=True, capture_output=True, text=True).stdout)
    data = res["data"]
    for key, count in res["out"].items():
        bw, p99 = map(float, key.split("|"))
        assert len(bench.gate(data["tier"], data["capped"], bw, p99)) == count, key


def test_embedded_run_is_a_real_regression():
    html = open(PAGE).read()
    assert "--rate_iops=50" in html
    data = json.loads(html.split("const DATA=")[1].split(";\nconst TEXT")[0])
    assert bench.gate(data["tier"], data["capped"]), "the capped run on the page must fail the default gate"
