#!/usr/bin/env bash
# Bring up the consolidated inference stack.
#
#   :8090  tsunami proxy — FastAPI front-end (/v1/chat → 8091, /v1/images → 8092)
#   :8091  llama-server  — Gemma-4-26B-A4B MXFP4 (agent LM)
#   :8092  ernie_server  — ERNIE-Image (DiT + Mistral3 TE + VAE, swap-capable)
#
# ERNIE_MODE knob:
#   gguf   (default) — Q4_K_M Turbo DiT, ~5 GB
#   bf16             — Turbo bf16 DiT, ~16 GB, /v1/admin/swap → Base works
#   base             — ERNIE-Image (50 steps, keeper quality), ~16 GB
#
# Future reserved ports (filled by animation backends when landed):
#   :8093 — SDXL+ControlNet (rigid motion library)
#   :8094 — Qwen-Edit (rotation sprite sheets)
#   :8095 — Wan Animate (unique effect animations)
#
# Idempotent: safe to re-run; skips services already listening.
# Run bin/down.sh for clean teardown.

set -euo pipefail

ARK="$(cd "$(dirname "$(realpath "$0")")/.." && pwd)"
MODELS="${TSUNAMI_MODELS_DIR:-/home/jb/models_gguf}"
LLAMA="$ARK/bin/llama-server"
VENV="${TSUNAMI_VENV:-/home/jb/ComfyUI/comfyui-env}"
LOG_DIR="/tmp"

# ─── Models ─────────────────────────────────────────────────────────────
GEMMA_GGUF="$MODELS/gemma-4-26B-A4B-it-MXFP4_MOE.gguf"
GEMMA_MMPROJ="$MODELS/mmproj-26B-F16.gguf"
ERNIE_GGUF="$MODELS/ernie-image-turbo-Q4_K_M.gguf"

# ─── Helpers ────────────────────────────────────────────────────────────
wait_port() {
    local port=$1 name=$2 url=${3:-/health}
    echo -n "  waiting for $name on :$port ..."
    for _ in $(seq 1 120); do
        if curl -sf --connect-timeout 1 "http://localhost:$port$url" > /dev/null 2>&1; then
            echo " ready"
            return 0
        fi
        sleep 2
    done
    echo " TIMEOUT (still booting?)"
    return 1
}

is_listening() {
    ss -tln 2>/dev/null | awk '{print $4}' | grep -q ":$1$"
}

# ─── :8091 Gemma-4 agent ────────────────────────────────────────────────
if is_listening 8091; then
    echo "[skip] :8091 already listening"
else
    echo "[up]  :8091 llama-server (Gemma-4-26B-A4B MXFP4)"
    nohup "$LLAMA" \
        --model "$GEMMA_GGUF" \
        --mmproj "$GEMMA_MMPROJ" \
        --port 8091 --host 0.0.0.0 \
        -ngl 999 -c 32768 --jinja \
        > "$LOG_DIR/tsu-llama.log" 2>&1 &
    wait_port 8091 "Gemma" /health
fi

# ─── :8092 ERNIE image-gen ──────────────────────────────────────────────
if is_listening 8092; then
    echo "[skip] :8092 already listening"
else
    ERNIE_MODE="${ERNIE_MODE:-gguf}"
    case "$ERNIE_MODE" in
        bf16)  ernie_args="--no-gguf --model Turbo";            desc="Turbo bf16 (16 GB, swap-capable)" ;;
        base)  ernie_args="--no-gguf --model Base";             desc="ERNIE-Image Base (16 GB, 50-step keeper)" ;;
        *)     ernie_args="--gguf $ERNIE_GGUF --model Turbo";   desc="Turbo Q4_K_M (5 GB)" ;;
    esac
    echo "[up]  :8092 ernie_server ($desc)"
    cd "$ARK"
    PYTHONPATH="$ARK" nohup "$VENV/bin/python" -m tsunami.tools.ernie_server \
        $ernie_args \
        --port 8092 --host 0.0.0.0 \
        --pe-url "" \
        > "$LOG_DIR/tsu-ernie.log" 2>&1 &
    wait_port 8092 "ERNIE" /healthz
fi

# ─── :8090 tsunami proxy ────────────────────────────────────────────────
if is_listening 8090; then
    echo "[skip] :8090 already listening"
else
    echo "[up]  :8090 tsunami proxy (forwards /v1/chat → 8091, /v1/images → 8092)"
    cd "$ARK"
    LLAMA_SERVER_URL=http://localhost:8091 \
    SD_SERVER_URL=http://localhost:8092 \
    PYTHONPATH="$ARK" \
    nohup python3 -u "$ARK/tsunami/serve_transformers.py" \
        --model none --image-model none \
        --port 8090 --host 0.0.0.0 \
        > "$LOG_DIR/tsu-proxy.log" 2>&1 &
    wait_port 8090 "proxy" /health
fi

echo
echo "─── Stack ready ───────────────────────────────────────────────"
echo "  :8090  tsunami proxy              tail -f $LOG_DIR/tsu-proxy.log"
echo "  :8091  Gemma-4-26B-A4B (LM)       tail -f $LOG_DIR/tsu-llama.log"
echo "  :8092  ERNIE-Image ($ERNIE_MODE)  tail -f $LOG_DIR/tsu-ernie.log"
echo
echo "  Health:  curl :8090/health     curl :8091/health     curl :8092/healthz"
echo "  Swap :   curl -X POST :8092/v1/admin/swap?kind=Base     (bf16 mode only)"
echo
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>&1 | grep -v warp || true
