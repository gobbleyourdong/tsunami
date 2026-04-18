# NVFP4 W4A4 migration path

Target: Qwen3.6-35B-A3B-FP8 → Qwen3.6-35B-A3B-NVFP4 (W4A4) on GB10 / sm_121.
Expected ceiling per `~/agentic_speed/tier1/nvfp4.md`: **50-67 tok/s**
(vs our current FP8 + CUDA-graph ceiling of ~38 tok/s).

This is a **multi-cycle project**. Not completed as of 2026-04-18.

## What's in the way

1. **`llm-compressor` wants torch 2.10 + transformers 4.57** — our serving
   stack runs torch 2.13.dev + transformers 5.x. Installing in-place would
   downgrade the whole stack, same conflict pattern we hit with vLLM earlier.
   Solution: isolated venv for quantization only. See SPARK repo's Docker
   split (separate quant container vs serving container).

2. **No FP8 → NVFP4 clean path.** `llm-compressor`'s NVFP4 recipe calls
   `.to(torch.bfloat16)` on load and works from bf16 weights. Loading FP8
   would dequant to bf16 and lose the precision the FP8 scales encoded.
   Must restart from the bf16 master. Qwen publishes both; the bf16 master
   is ~70GB and needs downloading separately.

3. **`cutlass_moe_fp4` is broken on sm_121** — SMEM overflow (99 KB on GB10
   vs 228 KB on SM100). **Marlin W4A4-dequant is the only production path**
   on our hardware. Mandatory env before serving NVFP4:
   ```
   VLLM_USE_FLASHINFER_MOE_FP4=0
   VLLM_NVFP4_GEMM_BACKEND=marlin
   VLLM_TEST_FORCE_FP8_MARLIN=1
   ```
   (These are vLLM vars — for our serving stack we'd need to port the
   Marlin W4A4 kernel into `tsunami/serving/vendor/`.)

## Step-by-step recipe

### 1. Download bf16 master (offline, ~70GB)

```bash
huggingface-cli download Qwen/Qwen3.6-35B-A3B --local-dir \
    ~/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B/snapshots/<SHA> \
    --resume
```

Disk check: `df -h ~` should show >100GB free.

### 2. Set up isolated venv

```bash
cd tsunami/serving/quant
python3 -m venv venv_llmc
source venv_llmc/bin/activate
pip install llmcompressor torch==2.10.0 transformers==4.57.6
```

Verify torch is CUDA-enabled: our earlier vLLM attempt got torch 2.10 CPU-only
from pypi default. Need the cu130 wheel index:
```bash
pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu130 \
    --force-reinstall
```

### 3. Run calibration

Recipe per `tier1/nvfp4.md` §1 (SPARK reference):
- Scheme: NVFP4 W4A4
- Group size: 16
- Global scales: per-tensor FP32 for weights AND activations
- Activation scales: static min/max global + dynamic per-group at inference
- MoE: `moe_calibrate_all_experts=True`
- Ignore list: `lm_head`, MoE gate proj, embeddings, shared-expert gate, linear_attn
- Dataset: ultrachat_200k, 20-512 samples × max_seq_len=2048

Wall time on GB10: ~90 min per tier1 research. Result: ~15GB packed checkpoint.

Script skeleton (fill in from llm-compressor examples):
```python
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from datasets import load_dataset

model = "path/to/Qwen3.6-35B-A3B-bf16"
dataset = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft[:512]")
recipe = QuantizationModifier(
    targets="Linear",
    scheme="NVFP4",
    ignore=["lm_head", "re:.*gate$", "re:.*embeddings.*"],
    moe_calibrate_all_experts=True,
)
oneshot(model=model, dataset=dataset, recipe=recipe,
        output_dir="Qwen3.6-35B-A3B-NVFP4",
        max_seq_length=2048, num_calibration_samples=512)
```

### 4. Port Marlin W4A4 kernel

vLLM's Marlin W4A4 kernel (`csrc/quantization/marlin/fp4/`) is the production
path on sm_121. Options:
- Vendor the `.cu` files into `tsunami/serving/vendor/marlin_fp4/`, compile
  as a torch CUDA extension at build time
- Lift from SGLang's SM120 CUTLASS NVFP4 port (PR #21314, merged)

### 5. Wire into lean_decode

Monkey-patch equivalent to our current `_ds_w8a8_fp8_matmul` shim but
against the NVFP4 entry point (likely `compressed_tensors.nvfp4_gemm` or
similar). The serving model loads the NVFP4 checkpoint with
`load_weights()` which dispatches to the Marlin kernel for per-layer matmul.

### 6. Validate

- Check accuracy on a small eval (e.g., 20-prompt sanity set vs the FP8
  baseline — no more than 1-2% quality drop expected per research)
- Bench tok/s — target 50+ tok/s on /debug/lean_decode
- Verify streaming + tool_call paths still work end-to-end

## Status

- [ ] bf16 master downloaded (needs ~70GB + hf-cli auth)
- [ ] `venv_llmc` set up + torch cu130 installed
- [ ] Calibration script fleshed out
- [ ] Calibration run (~90min)
- [ ] Marlin W4A4 kernel vendored + compiled
- [ ] Integration with lean_decode + serve_qwen36_fp8
- [ ] Accuracy validation
- [ ] Throughput bench vs FP8 baseline

Start with step 1 (download) since it's background-able and unblocks
everything else. Then step 2-3 in parallel with starting step 4.
