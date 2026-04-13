#!/bin/bash
# sweep.sh [NUM_GPUS] [BASE_PORT]
# Launches all sweeps across NUM_GPUS GPUs. When a GPU frees up, the next
# queued run grabs it. After all sweeps finish, runs sweep_aggregate.py.
#
# Examples:
#   bash training/sweep.sh 5          # 5 GPUs, ports from 8100
#   bash training/sweep.sh 8 9000     # 8 GPUs, ports from 9000
set -eu

NUM_GPUS=${1:-5}
BASE_PORT=${2:-8100}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Matrix: NAME R LR EPOCHS
CONFIGS=(
  "s01_r16_lr2e-5_e10  16  2e-5  10"
  "s02_r32_lr2e-5_e10  32  2e-5  10"
  "s03_r64_lr2e-5_e10  64  2e-5  10"
  "s04_r32_lr1e-5_e10  32  1e-5  10"
  "s05_r32_lr5e-5_e10  32  5e-5  10"
  "s06_r32_lr2e-5_e5   32  2e-5  5"
  "s07_r32_lr2e-5_e20  32  2e-5  20"
  "s08_r64_lr1e-5_e20  64  1e-5  20"
)

echo "=== sweep launch: $(date -Iseconds) ==="
echo "NUM_GPUS=$NUM_GPUS BASE_PORT=$BASE_PORT TOTAL_RUNS=${#CONFIGS[@]}"

# A GPU queue: simple file with one line per free GPU id.
QDIR=$(mktemp -d)
trap "rm -rf $QDIR" EXIT
for ((g=0; g<NUM_GPUS; g++)); do
  echo "$g" > "$QDIR/gpu_$g"
done

claim_gpu() {
  # Blocks until a GPU slot file exists, then removes one and prints the id.
  while true; do
    for f in "$QDIR"/gpu_*; do
      [ -e "$f" ] || continue
      if mv "$f" "$f.lock" 2>/dev/null; then
        cat "$f.lock"
        rm "$f.lock"
        return
      fi
    done
    sleep 2
  done
}

release_gpu() {
  echo "$1" > "$QDIR/gpu_$1"
}

PIDS=()
NAMES=()
RESULTS=()

for i in "${!CONFIGS[@]}"; do
  # shellcheck disable=SC2086
  set -- ${CONFIGS[$i]}
  NAME=$1; R=$2; LR=$3; EPOCHS=$4
  GPU=$(claim_gpu)
  PORT=$((BASE_PORT + GPU))
  echo "[$(date +%H:%M:%S)] launch [$NAME] on gpu=$GPU port=$PORT"
  (
    bash "$SCRIPT_DIR/sweep_one.sh" "$NAME" "$R" "$LR" "$EPOCHS" "$GPU" "$PORT"
    RC=$?
    release_gpu "$GPU"
    echo "[$(date +%H:%M:%S)] done [$NAME] rc=$RC gpu=$GPU freed"
    exit $RC
  ) &
  PIDS+=($!)
  NAMES+=("$NAME")
done

echo "${#PIDS[@]} sweeps queued across $NUM_GPUS GPUs. Waiting..."
for idx in "${!PIDS[@]}"; do
  if wait "${PIDS[$idx]}"; then
    RESULTS+=("0")
  else
    RESULTS+=("$?")
  fi
done

echo "=== all sweeps done: $(date -Iseconds) ==="
for idx in "${!NAMES[@]}"; do
  echo "  ${NAMES[$idx]}: exit=${RESULTS[$idx]}"
done

echo "=== aggregating ==="
python3 "$SCRIPT_DIR/sweep_aggregate.py"
