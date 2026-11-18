import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "bin", "node-validate")
PROFILE = os.path.join(ROOT, "ansible", "roles", "tuning", "files", "90-ingest.conf")


def make_proc(tmp_path, mdstat=None, mounts=""):
    for line in open(PROFILE):
        if line.strip() and not line.startswith("#"):
            key, val = [x.strip() for x in line.split("=", 1)]
            p = tmp_path / "sys" / key.replace(".", "/")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(val + "\n")
    (tmp_path / "mounts").write_text(mounts)
    if mdstat:
        (tmp_path / "mdstat").write_text(mdstat)
    return tmp_path


def run(proc, *args):
    return subprocess.run([SCRIPT, *args], capture_output=True, text=True, env={**os.environ, "PROC_ROOT": str(proc)})


def test_clean_node_passes(tmp_path):
    proc = make_proc(tmp_path, mdstat="md0 : active raid10 sdb[0] sdc[1]\n  1024 blocks [2/2] [UU]\n",
                     mounts="/dev/md0 /srv/ingest xfs rw 0 0\nlo:/ /mnt/nfs nfs4 rw,vers=4.2,hard,rsize=1048576 0 0\n")
    r = run(proc, "--mount", "/srv/ingest:xfs", "--nfs-mount", "/mnt/nfs")
    assert r.returncode == 0, r.stdout
    assert "PASS  sysctl-profile" in r.stdout


def test_sysctl_drift_is_reported(tmp_path):
    proc = make_proc(tmp_path)
    (tmp_path / "sys/vm/swappiness").write_text("60\n")
    r = run(proc)
    assert r.returncode == 1 and "vm.swappiness(have 60, want 10)" in r.stdout


def test_degraded_raid_fails(tmp_path):
    proc = make_proc(tmp_path, mdstat="md0 : active raid10 sdb[0]\n  1024 blocks [2/1] [U_]\n")
    r = run(proc)
    assert r.returncode == 1 and "FAIL  md-raid" in r.stdout


def test_bad_nfs_options_fail(tmp_path):
    proc = make_proc(tmp_path, mounts="lo:/ /mnt/nfs nfs rw,vers=3,soft,rsize=32768 0 0\n")
    r = run(proc, "--nfs-mount", "/mnt/nfs")
    assert r.returncode == 1 and "not-v4 not-hard rsize<1MiB" in r.stdout


def test_json_output(tmp_path):
    import json
    proc = make_proc(tmp_path)
    out = json.loads(run(proc, "--json").stdout)
    assert out[0]["check"] == "sysctl-profile" and out[0]["status"] == "PASS"
