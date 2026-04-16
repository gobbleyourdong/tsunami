#!/usr/bin/env bash
# Bring up the consolidated Spark inference stack.
#   :8091  llama-server — Gemma-4-26B-A4B (agent)
#   :8094  llama-server — Ministral-3-3B-Instruct (prompt enhancer)
#   :8093  ernie_server — Python ERNIE-Image-Turbo (DiT GGUF + bf16 TE)
#
# Each service backgrounds with logs in /tmp/<service>.log.
# Run bin/down.sh to take it all down.

set -euo pipefail

ARK="/home/jb/ComfyUI/CelebV-HQ/ark"
MODELS="/home/jb/models_gguf"
LLAMA="$ARK/bin/llama-server"
VENV="/home/jb/ComfyUI/comfyui-env"
LOG_DIR="/tmp"

# ─── Models ─────────────────────────────────────────────────────────────
GEMMA_GGUF="$MODELS/gemma-4-26B-A4B-it-MXFP4_MOE.gguf"
GEMMA_MMPROJ="$MODELS/mmproj-26B-F16.gguf"
MIN3_GGUF="$MODELS/ministral-3-3b-instruct-Q4_K_M.gguf"
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

# ─── 1. Gemma agent ─────────────────────────────────────────────────────
if is_listening 8091; then
    echo "[skip] :8091 already listening"
else
    echo "[up]  :8091 llama-server (Gemma-4-26B-A4B)"
    nohup "$LLAMA" \
        --model "$GEMMA_GGUF" \
        --mmproj "$GEMMA_MMPROJ" \
        --port 8091 --host 0.0.0.0 \
        -ngl 999 -c 32768 --jinja \
        > "$LOG_DIR/gemma_server.log" 2>&1 &
    wait_port 8091 "Gemma" /health
fi

# ─── 2. Ministral-3 prompt enhancer ─────────────────────────────────────
if is_listening 8094; then
    echo "[skip] :8094 already listening"
else
    echo "[up]  :8094 llama-server (Ministral-3-3B-Instruct, pe)"
    nohup "$LLAMA" \
        --model "$MIN3_GGUF" \
        --port 8094 --host 0.0.0.0 \
        --ctx-size 8192 \
        --n-gpu-layers 999 \
        --threads 8 \
        --jinja \
        > "$LOG_DIR/min3_server.log" 2>&1 &
    wait_port 8094 "Ministral-3" /health
fi

# ─── 3. ERNIE image-gen ─────────────────────────────────────────────────
if is_listening 8093; then
    echo "[skip] :8093 already listening"
else
    echo "[up]  :8093 ernie_server (DiT GGUF + bf16 TE + VAE)"
    cd "$ARK"
    # ERNIE_MODE: "gguf" (default, 5 GB Q4_K_M Turbo) or "bf16" (16 GB Turbo bf16) or "base" (16 GB non-turbo, 50 steps)
    ERNIE_MODE="${ERNIE_MODE:-gguf}"
    case "$ERNIE_MODE" in
        bf16)  ernie_args="--no-gguf --model Turbo";  echo "      ERNIE_MODE=bf16  → Turbo bf16 (16 GB DiT)";;
        base)  ernie_args="--no-gguf --model Base";   echo "      ERNIE_MODE=base  → ERNIE-Image (16 GB DiT, 50 steps)";;
        *)     ernie_args="--gguf $ERNIE_GGUF --model Turbo"; echo "      ERNIE_MODE=gguf  → Turbo Q4_K_M (5 GB DiT)";;
    esac
    nohup "$VENV/bin/python" -m tsunami.tools.ernie_server \
        $ernie_args \
        --port 8093 --host 0.0.0.0 \
        --pe-url http://localhost:8094 \
        > "$LOG_DIR/ernie_server.log" 2>&1 &
    wait_port 8093 "ERNIE" /healthz
fi

echo
echo "─── Stack ready ───────────────────────────────────────────────"
echo "  :8091  Gemma-4-26B-A4B (agent)            tail -f $LOG_DIR/gemma_server.log"
echo "  :8094  Ministral-3-3B-Instruct (pe)       tail -f $LOG_DIR/min3_server.log"
echo "  :8093  ERNIE-Image-Turbo (DiT GGUF)       tail -f $LOG_DIR/ernie_server.log"
echo
echo "  Health checks:"
echo "    curl :8091/health         curl :8094/health         curl :8093/healthz"
echo
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>&1 | grep -v warp || true
