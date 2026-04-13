# Training Recipe — Gemma 4 E4B on DGX Spark (GB10)

> **Last verified**: 2026-04-12 via v89-clean retrain.
> **Source truth**: this document + `training/train_unsloth.py` + `docker/` image.
> If training fails, the error you're seeing is almost certainly a dep/container version mismatch — start by reading this file end-to-end.

## The One Command

```bash
docker run --gpus all -d --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  -e PYTHONUNBUFFERED=1 \
  -e UNSLOTH_SKIP_TORCHVISION_CHECK=1 \
  -e HF_HUB_ENABLE_HF_TRANSFER=0 \
  -e HF_HUB_DISABLE_TELEMETRY=1 \
  -e UNSLOTH_DISABLE_STATISTICS=1 \
  -v /home/jb/ComfyUI/CelebV-HQ/ark:/workspace \
  -v /home/jb/.cache/huggingface:/root/.cache/huggingface \
  -w /workspace \
  --name <RUN_NAME> \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -c "
    set -e
    pip install --upgrade 'huggingface-hub>=1.5,<2' tokenizers safetensors hf_xet --no-deps -q --root-user-action ignore
    pip install transformers bitsandbytes 'datasets==4.3.0' --no-deps -q --root-user-action ignore
    pip install unsloth unsloth_zoo trl peft accelerate tyro shtab hf_transfer msgspec xformers --no-deps -q --root-user-action ignore
    python3 -c 'import torch; assert torch.cuda.is_available(), \"CUDA MISSING\"'
    python3 -u training/train_unsloth.py \
      --data <PATH_TO_JSONL> \
      --output models/<OUTPUT_NAME> \
      --epochs 3 \
      --lora-r 8 \
      --run-name <RUN_NAME>
  "
```

## Why each piece is required

### Image: `nvcr.io/nvidia/pytorch:25.11-py3`

- Contains NVIDIA's custom-built `pytorch 2.10.0a0+b558c98.nv25.11` with Blackwell (GB10, sm_120) kernels.
- Blackwell requires CUDA 12.9+ binaries; the generic torch on PyPI doesn't ship them and produces numerical garbage (see `MEMORY.md`).
- The newer `nvcr.io/nvidia/pytorch:26.03-py3` **should also work per commit `9f994ab`** ("FlashAttn blocked, falls back to xformers automatically"), but as of Apr 12 its FlashAttn raises a fatal `head dimension at most 256` error instead of falling back. Use 25.11 for now.

### `--gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864`

- Docker GPU passthrough + NVIDIA-recommended shared memory / ulimits (per PyTorch container warning on launch).

### Volume mounts

- `-v /home/jb/ComfyUI/CelebV-HQ/ark:/workspace` — source code, training data, output dir.
- `-v /home/jb/.cache/huggingface:/root/.cache/huggingface` — base model cache. Without this every container re-downloads Gemma 4 E4B.

### Env vars

- `UNSLOTH_SKIP_TORCHVISION_CHECK=1` — the container's `torchvision==0.25` is older than unsloth wants but works fine; this skips the check.
- `HF_HUB_ENABLE_HF_TRANSFER=0` — `hf_transfer` segfaults on some downloads; fall back to stable path.
- `HF_HUB_DISABLE_TELEMETRY=1` + `UNSLOTH_DISABLE_STATISTICS=1` — belt-and-suspenders; earlier versions tried to phone home to HF for stats using `xet_get` with a kwarg mismatch.

### **THE CRITICAL CONSTRAINT: `--no-deps` on every pip install**

**Plain `pip install unsloth` silently uninstalls the container's custom NV torch and replaces it with generic torch. That kills CUDA visibility.** All installs must use `--no-deps` and we install required deps explicitly.

### Required pins

| Package | Version constraint | Reason |
|---|---|---|
| `huggingface-hub` | `>=1.5,<2` | transformers 5.x requires >=1.5; some older containers ship 1.1.x |
| `datasets` | `==4.3.0` | Unsloth rejects 4.4.x with recursion-error check |
| `hf_xet` | upgrade to latest | older versions call `download_files(request_headers=)` which new hf_hub doesn't accept |
| `tokenizers`, `safetensors` | upgrade to latest | compatibility with transformers 5.x |
| `bitsandbytes` | install even if not using 4-bit | Unsloth `models/_utils.py` imports `bitsandbytes as bnb` at module load. The missing `cuda132` binary only matters at 4-bit runtime. |
| `transformers`, `trl`, `peft`, `accelerate`, `tyro`, `shtab`, `hf_transfer`, `msgspec`, `xformers` | latest with `--no-deps` | rest of the Unsloth/TRL stack |

## The training script — `training/train_unsloth.py`

- Real SFTTrainer invocation, saves PEFT adapter by default (no `--merge` flag).
- Output: `<OUTPUT_DIR>/adapter_model.safetensors` ≈ 81 MB at `--lora-r 8`.
- Champion (v89) args: `--epochs 3 --lora-r 8` with default LR 2e-4, grad_accum 16, batch 1, max_len 16384.
- Adapter config: r=8, alpha=2*r (=16 during training, saved as 8 by Unsloth merge/save path — don't chase this, v89 works in production with the saved config).

## End-to-end verification

1. **Training**:
   ```
   docker run [above recipe] ... --run-name v89-clean
   ```
   Expected output after ~5-15 min: `models/gemma-4-e4b-tsunami-v89-clean/adapter_model.safetensors` (~81 MB).

2. **Serving (eval endpoint on :8095, isolated from prod :8090)**:
   ```
   python3 serve_transformers.py \
     --model google/gemma-4-e4b-it \
     --adapter models/gemma-4-e4b-tsunami-v89-clean \
     --port 8095 --image-model none
   ```

3. **Eval**:
   ```
   python3 training/eval_all.py --endpoint http://localhost:8095 --quick
   ```
   Expected: ~471/500 for v89-clean (matches original champion per MEMORY.md).

## Things that broke during Apr 12 recovery (for future reference)

Sequential dep-peel failures encountered while reproducing this recipe — each one silently introduced by a dep version drift since Apr 10:

1. `pip install unsloth` (no `--no-deps`) → CUDA unavailable (torch swapped out)
2. `--no-deps` unsloth + transformers not installed → `ModuleNotFoundError: transformers`
3. bitsandbytes skipped → `ModuleNotFoundError: bitsandbytes` at unsloth import time (not just at 4-bit)
4. pytorch 26.03-py3 + Gemma 4 → FlashAttention `head dimension at most 256` fatal (downgrade to 25.11)
5. huggingface-hub 1.1.2 vs transformers 5.5.3 requires >=1.5 → import error
6. datasets 4.4.1 vs unsloth wants 4.3.0 → recursion-error check rejects
7. hf_xet API mismatch with new hf_hub → `TypeError: download_files() got an unexpected keyword argument 'request_headers'`

All resolved by the pinned install list above.

## Git commits that capture parts of this recipe

- `9f994ab` (Apr 10 19:20) — "Transformers-native inference server + E4B v81r trained on Spark" — documented the 26.03-py3 stack choice.
- `945b04c` (Apr 8 18:21) — "Add Unsloth training script for Gemma 4 E4B" — r=8, LR 2e-4 rationale.
- `f226d0c` (Apr 11 16:59) — "Cleanup: remove llama.cpp legacy" — removed 38 legacy training files and fragmented lineage.
