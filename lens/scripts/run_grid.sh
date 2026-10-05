#!/bin/bash
# Launch one `lens evaluate` per GPU job, thread-capped to avoid CPU oversubscription.
# usage: scripts/run_grid.sh <grid> <features> <budget> <policy> "<gpu>:<spec>[:<version>]" ...
# TABPFN_TOKEN must already be in the environment; it is never written by this script.
set -euo pipefail
grid=$1; feats=$2; budget=$3; policy=$4; shift 4
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-16} MKL_NUM_THREADS=${MKL_NUM_THREADS:-16}
# Only these GPUs may be used on the shared instance (override deliberately via LENS_GPUS).
allowed=" ${LENS_GPUS:-4 5 6 7} "
for job in "$@"; do
  gpu=${job%%:*}
  if [[ "$allowed" != *" $gpu "* ]]; then
    echo "refusing job '$job': GPU $gpu not in allowed set [${allowed}]" >&2; exit 1
  fi
done
mkdir -p "artifacts/$grid" "logs/$grid"
for job in "$@"; do
  IFS=: read -r gpu spec ver <<< "$job"; ver=${ver:-3.5}
  name="${spec//+/_}_v$ver"
  CUDA_VISIBLE_DEVICES=$gpu nohup .venv/bin/lens evaluate --features "$feats" --budget "$budget" \
    --policy "$policy" --device cuda --tabpfn-version "$ver" --learners "$spec" \
    --output "artifacts/$grid/$name" ${EXTRA_ARGS:-} > "logs/$grid/$name.log" 2>&1 &
done
