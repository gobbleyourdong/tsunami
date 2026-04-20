#!/usr/bin/env python3
"""Minimal load-and-forward test for RedHatAI/Qwen3.6-35B-A3B-NVFP4.

Verifies the main serving stack (transformers 5 + compressed-tensors 0.14)
can load NVFP4-pack-quantized weights and run one forward pass. Run from
the MAIN venv (not venv_llmc) so we're testing the serving stack, not the
calibration stack.

Not wired into serve_qwen36_fp8.py yet — this is the smoke test.
"""

from __future__ import annotations

import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig


MODEL_ID = "RedHatAI/Qwen3.6-35B-A3B-NVFP4"


def main() -> int:
    print(f"[nvfp4_load_test] torch {torch.__version__}, cuda {torch.cuda.is_available()}")

    print(f"[nvfp4_load_test] loading config …")
    cfg = AutoConfig.from_pretrained(MODEL_ID, trust_remote_code=True)
    arch = (cfg.architectures or ["?"])[0]
    print(f"  arch: {arch}")
    qc = getattr(cfg, "quantization_config", None)
    if isinstance(qc, dict):
        fmt = qc.get("format")
    else:
        fmt = getattr(qc, "format", None)
    print(f"  quant format: {fmt}")

    print(f"[nvfp4_load_test] loading tokenizer …")
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

    print(f"[nvfp4_load_test] loading model (this is where it might fail) …")
    t0 = time.time()
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="cuda:0",
        )
    except Exception as e:
        print(f"[nvfp4_load_test] LOAD FAILED: {type(e).__name__}: {e}")
        return 1
    print(f"  loaded in {time.time()-t0:.1f}s")
    print(f"  VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    print(f"[nvfp4_load_test] forward smoke test …")
    ids = tok("Count from 1 to 5:", return_tensors="pt").input_ids.to("cuda:0")
    try:
        t0 = time.time()
        with torch.no_grad():
            out = model(input_ids=ids, use_cache=False)
        torch.cuda.synchronize()
        print(f"  forward ok in {time.time()-t0:.2f}s, logits shape: {out.logits.shape}")
    except Exception as e:
        print(f"[nvfp4_load_test] FORWARD FAILED: {type(e).__name__}: {e}")
        return 2

    print(f"[nvfp4_load_test] argmax next token …")
    next_tok_id = int(out.logits[0, -1].argmax())
    next_tok = tok.decode([next_tok_id])
    print(f"  next token id={next_tok_id}  text={next_tok!r}")

    print(f"[nvfp4_load_test] SUCCESS — NVFP4 load + forward works on main stack")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
