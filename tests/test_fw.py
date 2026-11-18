import os
import shutil

import pytest

from ingestlab import fw

need = pytest.mark.skipif(
    os.geteuid() != 0 or not shutil.which("nft") or not shutil.which("ip"),
    reason="needs root, nft and ip")


def test_rules_file_has_deny_by_default():
    text = open(fw.RULES).read()
    assert "hook input priority 0; policy drop" in text
    assert "hook forward priority 0; policy drop" in text
    assert "hook output priority 0; policy drop" in text


@need
def test_push_only_policy_in_namespaces():
    res = fw.run()
    bad = [r for r in res["rows"] if not r["ok"]]
    assert not bad, bad
    assert res["open_before_rules"] == {"ot_to_ingest_8080": "connected", "ingest_to_ot_22": "connected"}
    assert res["payload_checksum_ok"]
    assert res["counters"]["inbound_dropped"] > 0 and res["counters"]["egress_dropped"] > 0
    assert all(r["result"] == "timeout" for r in res["rows"] if r["expected"] == "blocked"), "drops must be silent"
