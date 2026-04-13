#!/bin/bash
# sweep_rerun.sh — sequential scoring of pre-trained sweep adapters.
#
# Phase 1: each adapter gets L1-L4 only (~15 min). Fast.
# Phase 2: top 2 by L1-L4 composite get full L5 (~50 min each).
#
# Why sequential: prior parallel scoring crashed all 4 processes ~18:51 (suspected
# shared-module-state race in tsunami imports). One agent loop at a time = safe.
#
# Usage:
#   bash training/sweep_rerun.sh           # all sweeps in models/sweep/
#   bash training/sweep_rerun.sh s02 s03   # specific subset
set -eu

SWEEPS=("$@")
if [ ${#SWEEPS[@]} -eq 0 ]; then
  for d in models/sweep/*-merged; do
    n=$(basename "$d" -merged)
    SWEEPS+=("$n")
  done
fi

PORT=8200
GPU=0
RES_DIR=workspace/training_data/sweep_rerun
LOG_DIR=training/logs/sweep_rerun
mkdir -p "$RES_DIR" "$LOG_DIR"

echo "=== sweep_rerun start: $(date -Iseconds) ==="
echo "Sweeps: ${SWEEPS[*]}"
echo "Output: $RES_DIR/  Logs: $LOG_DIR/"

run_score() {
  local NAME=$1
  local LAYERS=$2
  local SUFFIX=$3
  local MERGED=models/sweep/${NAME}-merged
  local LOG=${LOG_DIR}/${NAME}${SUFFIX}.log
  local OUT=${RES_DIR}/${NAME}${SUFFIX}.json

  if [ ! -d "$MERGED" ]; then
    echo "[$(date +%H:%M:%S)] SKIP $NAME — no merged adapter at $MERGED"
    return 1
  fi

  echo "[$(date +%H:%M:%S)] $NAME [$LAYERS] serve on :$PORT gpu=$GPU"
  CUDA_VISIBLE_DEVICES=$GPU UNSLOTH_SKIP_TORCHVISION_CHECK=1 \
    PYTHONPATH=. python3 -u tsunami/serve_transformers.py \
    --model "$MERGED" --port "$PORT" --image-model none \
    > "$LOG" 2>&1 &
  local SPID=$!
  trap "kill $SPID 2>/dev/null; exit 130" INT TERM

  local READY=0
  for _ in $(seq 1 30); do
    if curl -s -m 2 "http://localhost:$PORT/health" >/dev/null 2>&1; then
      READY=1; break
    fi
    sleep 10
  done
  if [ $READY -eq 0 ]; then
    echo "[$(date +%H:%M:%S)] $NAME server FAILED to start"
    kill $SPID 2>/dev/null || true
    wait $SPID 2>/dev/null || true
    return 2
  fi

  echo "[$(date +%H:%M:%S)] $NAME score $LAYERS"
  PYTHONPATH=. python3 -u training/eval.py \
    --endpoint "http://localhost:$PORT" --layers "$LAYERS" --output "$OUT" \
    >> "$LOG" 2>&1 || echo "[$(date +%H:%M:%S)] $NAME score exited non-zero"

  echo "[$(date +%H:%M:%S)] $NAME kill server"
  kill $SPID 2>/dev/null || true
  wait $SPID 2>/dev/null || true

  if [ -f "$OUT" ]; then
    python3 -c "
import json
d = json.load(open('$OUT'))
parts=[]
for k in ('format','scaffold','recovery','hackfree','integration'):
    r=d.get(k,{})
    if r:parts.append(f'{k[:3]}={r.get(\"passed\",0)}/{r.get(\"total\",0)}')
print('  result:', '|'.join(parts))"
  fi
}

echo
echo "=== PHASE 1: L1-L4 (fast) ==="
for NAME in "${SWEEPS[@]}"; do
  run_score "$NAME" "format,scaffold,recovery,hackfree" "_L14" || true
done

echo
echo "=== PHASE 1 ranking by L1-L4 ==="
RANK_FILE=$(mktemp)
for NAME in "${SWEEPS[@]}"; do
  J=${RES_DIR}/${NAME}_L14.json
  [ -f "$J" ] || continue
  python3 -c "
import json
d = json.load(open('$J'))
total = 0
for k in ('format','scaffold','recovery','hackfree'):
    r = d.get(k, {})
    if r and r.get('total',0):
        total += 100 * r['passed'] / r['total']
print(f'$NAME {total:.1f}')"
done | sort -k2 -rn > "$RANK_FILE"
cat "$RANK_FILE"

TOP_NAMES=()
while IFS=' ' read -r n _ && [ ${#TOP_NAMES[@]} -lt 2 ]; do
  TOP_NAMES+=("$n")
done < "$RANK_FILE"
rm "$RANK_FILE"

echo
echo "=== PHASE 2: L5 on top-2 (${TOP_NAMES[*]}) ==="
for NAME in "${TOP_NAMES[@]}"; do
  run_score "$NAME" "integration" "_L5" || true
done

echo
echo "=== sweep_rerun done: $(date -Iseconds) ==="
echo "All results: $RES_DIR/"
