#!/bin/bash
# train_adapter.sh — one-shot: train → serve (prod parity) → eval → report
#
# Usage:
#   ./training/train_adapter.sh <training_data.jsonl> <eval_script.py> [adapter_name]
#
# Example:
#   ./training/train_adapter.sh \
#     workspace/training_data/e4b_toolcall_train_v89.jsonl \
#     training/eval.py \
#     v90-test
#
# Behavior:
#   1. Train LoRA via train.py (native python3)
#   2. Start serve_transformers.py on port 8095 with the EXACT production
#      deployment command — same model, same image-model, same flags. Only
#      differences from prod: port 8095 (not 8090), and --adapter points at
#      the just-trained adapter (not --adapters-dir).
#   3. Run the provided eval script against http://localhost:8095
#   4. Shut down eval server, print JSON summary (adapter path, eval result).
#
# State:
#   - Adapter: models/gemma-4-e4b-tsunami-<name>/
#   - Merged (if --merge was passed to training, default yes): models/gemma-4-e4b-tsunami-<name>-merged/
#   - Logs: training/logs/<name>.{train,serve,eval}.log
#   - Prod on :8090 untouched.

set -euo pipefail

REPO="/home/jb/ComfyUI/CelebV-HQ/ark"
cd "$REPO"

# ---- args ----
DATA="${1:-}"
EVAL_SCRIPT="${2:-}"
if [[ -z "$DATA" || -z "$EVAL_SCRIPT" ]]; then
  echo "Usage: $0 <training_data.jsonl> <eval_script.py> [adapter_name]" >&2
  echo "  training_data.jsonl — SFT data for train.py" >&2
  echo "  eval_script.py      — any script taking --endpoint <url>" >&2
  echo "  adapter_name        — optional; default <basename>-YYYYMMDD-HHMM" >&2
  exit 2
fi
if [[ ! -f "$DATA" ]]; then
  echo "ERROR: training data not found: $DATA" >&2
  exit 2
fi
if [[ ! -f "$EVAL_SCRIPT" ]]; then
  echo "ERROR: eval script not found: $EVAL_SCRIPT" >&2
  exit 2
fi

TS="$(date +%Y%m%d-%H%M)"
BASENAME="$(basename "$DATA" .jsonl)"
BASENAME="${BASENAME#e4b_toolcall_train_}"
NAME="${3:-${BASENAME}-${TS}}"
ADAPTER_DIR="models/gemma-4-e4b-tsunami-${NAME}"

LOG_DIR="training/logs"
mkdir -p "$LOG_DIR"
TRAIN_LOG="$LOG_DIR/${NAME}.train.log"
SERVE_LOG="$LOG_DIR/${NAME}.serve.log"
EVAL_LOG="$LOG_DIR/${NAME}.eval.log"

echo "[train_adapter] name=$NAME"
echo "[train_adapter] data=$DATA"
echo "[train_adapter] eval=$EVAL_SCRIPT"
echo "[train_adapter] output=$ADAPTER_DIR"

# ---- 1. train (native) ----
export UNSLOTH_SKIP_TORCHVISION_CHECK=1

echo "[train_adapter] training..."
python3 -u training/train.py \
  --data "$DATA" \
  --output "$ADAPTER_DIR" \
  --epochs 10 --grad-accum 4 --lr 2e-4 --lora-r 8 --merge \
  > "$TRAIN_LOG" 2>&1
TRAIN_RC=$?

if [[ $TRAIN_RC -ne 0 ]]; then
  echo "[train_adapter] TRAINING FAILED rc=$TRAIN_RC — see $TRAIN_LOG" >&2
  tail -20 "$TRAIN_LOG" >&2
  exit 1
fi

if [[ ! -f "$ADAPTER_DIR/adapter_model.safetensors" ]]; then
  echo "[train_adapter] FAIL: $ADAPTER_DIR/adapter_model.safetensors not produced" >&2
  exit 1
fi
ADAPTER_SIZE=$(stat -c '%s' "$ADAPTER_DIR/adapter_model.safetensors")
echo "[train_adapter] trained. adapter_size=$((ADAPTER_SIZE/1024/1024))MB"

# ---- 2. start eval server (production parity) ----
EVAL_PORT=8095
# Kill stale eval server if running
pkill -f "serve_transformers.py.*--port ${EVAL_PORT}" 2>/dev/null || true
sleep 1

# This invocation MATCHES production deployment on :8090 except:
#   - port 8095 (not 8090) to avoid conflict
#   - --adapter points at the just-trained adapter (single, pinned)
# Prod uses --adapters-dir with multiple adapters + runtime routing;
# eval pins one adapter so evals measure THIS adapter's behavior.
# All other flags identical so the request/response path is prod-equivalent.
echo "[train_adapter] starting eval server on :${EVAL_PORT} (prod-parity)..."
setsid nohup python3 -u serve_transformers.py \
  --model google/gemma-4-e4b-it \
  --image-model Tongyi-MAI/Z-Image-Turbo \
  --adapter "$ADAPTER_DIR" \
  --port "$EVAL_PORT" \
  > "$SERVE_LOG" 2>&1 < /dev/null &
SERVE_PID=$!
disown
trap 'echo "[train_adapter] stopping eval server pid=$SERVE_PID"; kill '"$SERVE_PID"' 2>/dev/null || true' EXIT

# Wait for health (image model load takes ~30-60s)
echo "[train_adapter] waiting for /health on :${EVAL_PORT}..."
READY=0
for i in $(seq 1 180); do
  if curl -s -m 2 "http://localhost:${EVAL_PORT}/health" > /dev/null 2>&1; then
    READY=1
    echo "[train_adapter] ready (took ${i}s)"
    break
  fi
  if ! kill -0 "$SERVE_PID" 2>/dev/null; then
    echo "[train_adapter] EVAL SERVER CRASHED — see $SERVE_LOG" >&2
    tail -30 "$SERVE_LOG" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$READY" != "1" ]]; then
  echo "[train_adapter] EVAL SERVER DIDN'T BECOME READY within 180s" >&2
  tail -30 "$SERVE_LOG" >&2
  exit 1
fi

# ---- 3. run eval script (user-provided) ----
echo "[train_adapter] running eval: python3 $EVAL_SCRIPT --endpoint http://localhost:${EVAL_PORT}"
EVAL_RC=0
python3 "$EVAL_SCRIPT" --endpoint "http://localhost:${EVAL_PORT}" > "$EVAL_LOG" 2>&1 || EVAL_RC=$?

EVAL_SUMMARY=""
if [[ -f "$EVAL_LOG" ]]; then
  # Pull the last relevant-looking lines for summary
  EVAL_SUMMARY=$(tail -40 "$EVAL_LOG" | grep -iE "total|score|L[1-5]:|pass|fail|pct|/500|/274" | tail -15 | tr '\n' ';' || true)
fi

# ---- 4. shutdown via trap; summary below ----
kill "$SERVE_PID" 2>/dev/null || true
sleep 1

# ---- 5. report ----
echo ""
echo "=========================================="
echo "train_adapter result"
echo "=========================================="
cat <<EOF
{
  "name": "$NAME",
  "adapter_path": "$ADAPTER_DIR",
  "merged_path": "${ADAPTER_DIR}-merged",
  "adapter_size_mb": $((ADAPTER_SIZE/1024/1024)),
  "training_data": "$DATA",
  "eval_script": "$EVAL_SCRIPT",
  "eval_rc": $EVAL_RC,
  "train_log": "$TRAIN_LOG",
  "serve_log": "$SERVE_LOG",
  "eval_log": "$EVAL_LOG",
  "eval_summary": "$(echo "$EVAL_SUMMARY" | sed 's/"/\\"/g' | tr -d '\n')"
}
EOF

exit $EVAL_RC
