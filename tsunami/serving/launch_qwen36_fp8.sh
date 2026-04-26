#!/usr/bin/env bash
# DEPRECATED 2026-04-25 — use launch_qwen36_27b_bf16.sh.
#
# Qwen3.6-27B (dense BF16, multimodal) shipped 2026-04-23 and is now the
# default backend on tsunami's :8095 port. It loads in ~5 min vs ~12 min for
# the 35B-A3B-FP8 MoE, has no expert-fusion gymnastics, and matches the
# Qwen3.6 instruct sampling preset out of the box.
#
# This script is preserved for the case where you specifically need the MoE
# FP8 build (e.g. comparing throughput at higher params, or a workload that
# benefits from sparse-expert capacity). Pass FORCE_FP8=1 to actually run.
#
# GB10 Blackwell (compute cap 13.1) requires torch ≥ 2.11 built against
# CUDA ≥ 13.x — only the nvcr.io/nvidia/pytorch:26.03-py3 image satisfies
# that. Host venvs (comfyui-env) cap at CUDA 12.9 and produce numerical
# garbage on Blackwell.
#
# Usage:
#   FORCE_FP8=1 ./launch_qwen36_fp8.sh                 # foreground, port 8095
#   FORCE_FP8=1 ./launch_qwen36_fp8.sh --port 8096     # override port
#   FORCE_FP8=1 PORT=8096 ./launch_qwen36_fp8.sh       # same via env
set -euo pipefail

if [ "${FORCE_FP8:-}" != "1" ]; then
    echo "ERROR: launch_qwen36_fp8.sh is deprecated. Use launch_qwen36_27b_bf16.sh." >&2
    echo "       Pass FORCE_FP8=1 to bypass this check and load the legacy MoE." >&2
    exit 2
fi

PORT="${PORT:-8095}"
MODEL="${MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
IMAGE="${IMAGE:-nvcr.io/nvidia/pytorch:26.03-py3}"
NAME="${NAME:-qwen36-fp8-server}"

# Mount host HF cache so the 55GB download persists across container runs.
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"  # …/CelebV-HQ

# Remove any stale container — docker refuses to re-use the name otherwise.
docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "Launching $NAME on :$PORT using $IMAGE"
echo "  model : $MODEL"
echo "  repo  : $REPO"
echo "  hf    : $HF_CACHE"

exec docker run --rm --name "$NAME" \
    --gpus all --ipc=host \
    --ulimit memlock=-1 --ulimit stack=67108864 \
    -p "${PORT}:${PORT}" \
    -v "$HF_CACHE":/root/.cache/huggingface \
    -v "$REPO":/workspace/CelebV-HQ \
    -w /workspace/CelebV-HQ/tsunami/serving \
    -e HF_HUB_ENABLE_HF_TRANSFER=1 \
    "$IMAGE" \
    bash -lc "
set -e
# transformers main is required for the qwen3_5 architecture (4.57.0.dev0).
# Pin the commit by date via main branch — update together with the image
# when the model receives breaking config changes.
python -m pip install --no-cache-dir --quiet \
    'transformers[serving] @ git+https://github.com/huggingface/transformers.git@main' \
    'accelerate>=1.2' \
    'hf_transfer' \
    'kernels' \
    'fastapi' 'uvicorn' 'pydantic' 'httpx' 'pillow'
# Optional fast-path kernels for Qwen3.5-Moe's gated DeltaNet linear-attention.
# Without these, transformers falls back to a torch reference that's correct
# but slow. The packages ship source-only and the nvcc build fans out across
# every supported compute cap — that's 15-30 min of blocking compile on ARM,
# so we kick it off in the BACKGROUND and let the server come up immediately.
# On the next cold boot, already-built wheels (from TORCH_EXTENSIONS_DIR cache)
# will be reused and the kernels become available.
nohup bash -c \"python -m pip install --no-cache-dir --quiet 'causal-conv1d' 'flash-linear-attention' > /tmp/fla_install.log 2>&1\" &
echo '=== versions ==='
python -c 'import torch,transformers,accelerate; print(\"torch\",torch.__version__,\"cuda\",torch.version.cuda); print(\"transformers\",transformers.__version__); print(\"accelerate\",accelerate.__version__)'
exec python -u serve_qwen36_fp8.py --model '$MODEL' --port '$PORT' --host 0.0.0.0
"
