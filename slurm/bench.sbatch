#!/bin/bash
#SBATCH --job-name=ingest-bench
#SBATCH --partition=ingest
#SBATCH --output=/tmp/ingest-bench-%j.out
# Run the I/O benchmark as a scheduled job. Usage: sbatch slurm/bench.sbatch /srv/ingest/nvme
cd "$SLURM_SUBMIT_DIR" || exit 1  # run sbatch from the repository root
PYTHONPATH=src python3 -m ingestlab bench "${1:-/srv/ingest/nvme}" --out "/tmp/ingest-bench-$SLURM_JOB_ID.json"
