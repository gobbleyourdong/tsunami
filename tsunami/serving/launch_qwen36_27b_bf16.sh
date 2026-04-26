#!/usr/bin/env bash
# Launch Qwen3.6-27B (BF16, dense) inside the NVIDIA PyTorch container.
#
# THIS IS THE DEFAULT LAUNCHER for tsunami's "qwen36" backend tier.
# Replaces launch_qwen36_fp8.sh (now deprecated — see banner there).
#
# Model: Qwen/Qwen3.6-27B — dense 27B BF16, multimodal (vision + text + thinking).
#   Shipped 2026-04-23. ~54 GB BF16 fits in GB10's 128 GB unified pool with
#   KV cache + activations. Smaller, simpler, and faster to load than the
#   35B-A3B-FP8 MoE; matches Qwen3.6 instruct sampling presets out of the box.
#
# Port: 8095 — the canonical qwen36 backend port (test_stack_smoke.py, the
#   tsunami proxy at :8090, and harness/server_monitor.py all expect it).
#
# Same script (serve_qwen36_fp8.py — keeping the legacy filename to avoid a
# big rename across tests/imports) handles both 27B-BF16 and 35B-A3B-FP8;
# its `_load_model` has a non-MoE branch that loads dense weights via
# `dtype="auto"` (→ BF16 from the model's config). The MoE-only fusion
# path skips when num_experts is 0.
#
# Constants verified against https://huggingface.co/Qwen/Qwen3.6-27B (model card):
#   * 27B params, 64 layers, hidden=5120, vocab=248320 (padded), FFN=17408
#   * Hybrid: 16× (3× Gated DeltaNet + 1× Gated Attention)
#       DeltaNet: 48V/16QK heads, head_dim=128
#       Attention: 24Q/4KV heads, head_dim=256, RoPE dim=64
#   * Native context 262144 (YaRN-extensible to 1010000) — server caps at 65536
#     by default (see _CACHE_CEILING in serve_qwen36_fp8.py); raise via env if
#     a workload needs more.
#   * Vision encoder + MTP — both intact under AutoModelForImageTextToText.
#   * Apache 2.0 licence.
#   * Sampling defaults in serve_qwen36_fp8.py:ChatRequest match the model
#     card's "instruct mode for general tasks" preset (temp=0.7, top_p=0.8,
#     top_k=20, presence_penalty=1.5, repetition_penalty=1.0).
#
# GB10 Blackwell (compute cap 13.1) requires torch ≥ 2.11 built against
# CUDA ≥ 13.x — only the nvcr.io/nvidia/pytorch:26.03-py3 image satisfies
# that. Host venvs (comfyui-env) cap at CUDA 12.9 and produce numerical
# garbage on Blackwell.
#
# Usage:
#   ./launch_qwen36_27b_bf16.sh              # foreground, port 8096
#   PORT=8097 ./launch_qwen36_27b_bf16.sh    # override port
set -euo pipefail

PORT="${PORT:-8095}"
MODEL="${MODEL:-Qwen/Qwen3.6-27B}"
IMAGE="${IMAGE:-nvcr.io/nvidia/pytorch:26.03-py3}"
NAME="${NAME:-qwen36-bf16-server}"

HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"  # …/CelebV-HQ

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
    -v "$HOME/.cache/qwen36_pip":/root/.cache/pip \
    -v "$REPO":/workspace/CelebV-HQ \
    -w /workspace/CelebV-HQ/tsunami/serving \
    -e HF_HUB_ENABLE_HF_TRANSFER=1 \
    "$IMAGE" \
    bash -lc "
set -e
# transformers main carries the qwen3_5 + qwen3_6 architectures (4.57.0.dev0+).
# Pin the commit by date via main branch — update together with the image
# when the model receives breaking config changes.
python -m pip install --quiet \
    'transformers[serving] @ git+https://github.com/huggingface/transformers.git@main' \
    'accelerate>=1.2' \
    'hf_transfer' \
    'kernels' \
    'fastapi' 'uvicorn' 'pydantic' 'httpx' 'pillow'
# Fast-path kernels for Qwen3.6's gated DeltaNet linear-attention. WITHOUT
# these, transformers falls back to a torch reference that's correct but
# ~10x slower (1.5 tok/s vs ~15 tok/s observed on GB10 sm_121). Earlier
# revisions installed in background (nohup) to keep boot fast — that lost
# the race with the import-at-startup in transformers, so the running python
# stayed on the slow path until the next container restart. Install
# SYNCHRONOUSLY now (~30s on warm pip cache; ~5min cold on ARM since
# causal-conv1d compiles via nvcc) so the python process below picks them
# up. Container is --rm so the install evaporates with the container; cost
# is paid every cold boot until we bake these into a derived docker image.
python -m pip install --quiet 'causal-conv1d' 'flash-linear-attention' 2>&1 | tail -5
python -c 'import fla; import causal_conv1d; print(\"FLA fast path:\", fla.__version__)'
echo '=== versions ==='
python -c 'import torch,transformers,accelerate; print(\"torch\",torch.__version__,\"cuda\",torch.version.cuda); print(\"transformers\",transformers.__version__); print(\"accelerate\",accelerate.__version__)'
exec python -u serve_qwen36_fp8.py --model '$MODEL' --port '$PORT' --host 0.0.0.0
"
