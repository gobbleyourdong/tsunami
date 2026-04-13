#!/bin/bash
# sweep_one.sh NAME R LR EPOCHS GPU PORT
# Full pipeline for one hparam config: train → merge → serve → eval → kill.
# Pinned to a single GPU via CUDA_VISIBLE_DEVICES. Full log per run.
set -eu

NAME=$1
R=$2
LR=$3
EPOCHS=$4
GPU=$5
PORT=$6

export CUDA_VISIBLE_DEVICES=$GPU
export UNSLOTH_SKIP_TORCHVISION_CHECK=1
export HF_HUB_DISABLE_TELEMETRY=1

DATA=workspace/training_data/champion.jsonl
OUT=models/sweep/$NAME
MERGED=${OUT}-merged
LOG=training/logs/sweep/${NAME}.log
EVAL_JSON=workspace/training_data/sweep/${NAME}.json

mkdir -p models/sweep training/logs/sweep workspace/training_data/sweep

{
  echo "=== $NAME ==="
  echo "GPU=$GPU PORT=$PORT R=$R LR=$LR EPOCHS=$EPOCHS"
  echo "DATA=$DATA OUT=$OUT MERGED=$MERGED"
  echo "started: $(date -Iseconds)"
} > "$LOG"

echo "[$NAME] TRAIN" | tee -a "$LOG"
python3 -u training/train.py \
  --data "$DATA" \
  --output "$OUT" \
  --run-name "$NAME" \
  --lora-r "$R" \
  --lr "$LR" \
  --epochs "$EPOCHS" \
  --merge \
  >> "$LOG" 2>&1

echo "[$NAME] SERVE on port $PORT" | tee -a "$LOG"
PYTHONPATH=. python3 -u tsunami/serve_transformers.py \
  --model "$MERGED" \
  --port "$PORT" \
  --image-model none \
  >> "$LOG" 2>&1 &
SERVE_PID=$!

# Wait up to 5 minutes for health
READY=0
for i in $(seq 1 30); do
  if curl -s -m 2 "http://localhost:$PORT/health" >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 10
done

if [ $READY -eq 0 ]; then
  echo "[$NAME] SERVER FAILED TO START" | tee -a "$LOG"
  kill $SERVE_PID 2>/dev/null || true
  exit 1
fi

echo "[$NAME] EVAL against http://localhost:$PORT" | tee -a "$LOG"
PYTHONPATH=. python3 -u training/eval.py \
  --endpoint "http://localhost:$PORT" \
  --output "$EVAL_JSON" \
  >> "$LOG" 2>&1 || echo "[$NAME] EVAL exited non-zero" | tee -a "$LOG"

echo "[$NAME] KILL server" | tee -a "$LOG"
kill $SERVE_PID 2>/dev/null || true
wait $SERVE_PID 2>/dev/null || true

echo "[$NAME] done: $(date -Iseconds)" | tee -a "$LOG"
