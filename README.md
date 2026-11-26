# ingest-node-lab

A Linux data-ingest node lab. Ansible builds RAID 10, LVM, XFS, a ZFS mirror, an NFSv4.2 mount and a Slurm node. A push-only firewall is proven with real packets in network namespaces. An fio gate fails the build when I/O gets slower. Everything runs on a real Linux kernel in CI, on loop-backed devices.

[![CI](https://github.com/gerardrecinto/ingest-node-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/gerardrecinto/ingest-node-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/gerardrecinto/ingest-node-lab)](LICENSE)

**[Live page: real packets, a failed drive, and the I/O gate](https://gerardrecinto.github.io/ingest-node-lab/)**

## Run it

Tests need Linux, root, `nftables`, `iproute2` and `fio`. About a minute.

```bash
git clone https://github.com/gerardrecinto/ingest-node-lab
cd ingest-node-lab
sudo apt-get install -y nftables iproute2 fio python3-pytest
sudo python3 -m pytest -q
sudo PYTHONPATH=src python3 -m ingestlab fw
```

The firewall run prints one line per connection attempt:

```
ok     ot -> 10.10.1.2:9000     connected
ok     ot -> 10.10.1.2:8080     timeout
ok  ingest -> 10.10.1.1:22      timeout
...
payload checksum ok: True | counters: {'inbound_dropped': ..., 'egress_dropped': ...}
```

The full node build creates md, LVM, ZFS and NFS state, so use a VM you do not mind changing:

```bash
pip install ansible-core && ansible-galaxy collection install -r ansible/requirements.yml
ansible-playbook -i ansible/inventory.ini ansible/site.yml -e zfs_enabled=true
sudo bin/node-validate --mount /srv/ingest/nvme:xfs --nfs-mount /mnt/ingest-nfs
```

macOS note: the namespace and storage parts need a Linux kernel. Docker Desktop's VM runs the firewall and fio tests; it has no md or ZFS.

## What CI proves

The `provision` job runs on a GitHub-hosted Ubuntu 24.04 runner with root:

| Step | Result to look for |
| :--- | :--- |
| Ansible build, then a second run | second run reports `changed=0` |
| `node-validate` | sysctl profile, XFS mount, NFSv4.2 options, md RAID and ZFS pool all PASS |
| fio on the tier and the NFS mount | bandwidth, IOPS and p99 per job saved as an artifact |
| Capped run (`--rate-iops 50`) | the gate fails it |
| Slurm | the benchmark runs as a batch job that ends `COMPLETED` |
| Firewall in three namespaces | 10 cases as expected, drops are silent, counters above zero |
| Fail one RAID member | `node-validate` exits 1 and edgeprobe reports a degraded array |

The `rhel-family` job runs the hardware-free roles twice on Rocky Linux 9. Download the `evidence` artifact from any run to see the raw output.

## Parts

| Part | Where |
| :--- | :--- |
| Kernel parameters, applied and audited | `ansible/roles/tuning`, `bin/node-validate` |
| RAID 10, LVM, XFS, optional ZFS mirror | `ansible/roles/storage` |
| NFSv4.2 export and mount | `ansible/roles/nfs` |
| Slurm single node | `ansible/roles/slurm`, `slurm/bench.sbatch` |
| Push-only ruleset | `firewall/ot-push-only.nft` (checked with `nft -c`, applied only inside namespaces) |
| Firewall proof | `src/ingestlab/fw.py`, `tests/test_fw.py` |
| fio runner and gate | `src/ingestlab/bench.py`, `tests/test_bench.py` |
| Storage checks from the live host | [edgeprobe](https://github.com/gerardrecinto/edgeprobe) `scripts/collect_storage.sh` |

## Trade-offs

All design-only; nothing here ran in production.

| Chose | Over | Costs | Flip when |
| :--- | :--- | :--- | :--- |
| RAID 10 | RAID 5 or 6 | Half the capacity | Capacity per rack unit matters more than write latency |
| ZFS mirror | mdadm and XFS | RAM, CPU, out-of-tree module | Raw speed matters more than integrity checks |
| Hard NFS mounts | Soft | A hung server blocks clients | A failed write is better than a hang |
| Stateful firewall with drop | A hardware data diode | Not a physical one-way guarantee | A regulation needs physical one-way |
| Silent drop | Reject | Slower debugging | The segment is internal |
| p99 in the gate | Averages | Needs more samples | Throughput-only batch work |

Throughput numbers come from loop files on a shared CI runner.

MIT license.
