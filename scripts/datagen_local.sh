#!/usr/bin/env bash
# Generate a dataset locally in parallel shards, then merge (BACKBONE §8.6, module 02).
# Usage: bash scripts/datagen_local.sh [NUM_SHARDS=8] [DS=ds1]
set -euo pipefail
cd "$(dirname "$0")/.."
N="${1:-8}"; DS="${2:-ds1}"; PY="${PY:-.venv/bin/python}"
mkdir -p "data/raw/$DS" "data/processed/$DS" infra/logs
pids=()
for ((i = 0; i < N; i++)); do
  "$PY" -m sim.cli generate --config "config/generation/$DS.yaml" --shard "$i" --num-shards "$N" \
    --out "data/raw/$DS/shard=$i/" > "infra/logs/datagen_${DS}_shard$i.log" 2>&1 &
  pids+=($!)
done
fail=0
for p in "${pids[@]}"; do wait "$p" || fail=1; done
[[ $fail -eq 0 ]] || { echo "a shard failed — see infra/logs/datagen_${DS}_shard*.log" >&2; exit 1; }
"$PY" -m sim.cli merge --config "config/generation/$DS.yaml" --raw "data/raw/$DS/" --out "data/processed/$DS/"
echo "done: data/processed/$DS/manifest.json"
