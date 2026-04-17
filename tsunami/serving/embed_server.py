#!/usr/bin/env python3
"""Qwen3-Embedding-0.6B — OpenAI-compatible /v1/embeddings endpoint.

Companion to serve_qwen36_fp8.py (:8095 text+vision) and ernie_server
(:8092 image gen). Native transformers stack — no GGUF, no llama-server —
matches the rest of the tsu tier.

Pooling and normalization follow the Qwen3-Embedding model card exactly:
  1. last-token pool (handles left- and right-padded batches)
  2. L2 normalize
Default embedding dim is 1024. The model supports truncating the output
vector down to 32-1024 via `dim` in the request (Matryoshka-style); we
pass it through when set.

OpenAI shape:
  POST /v1/embeddings  {input: str|list[str], model: str, dim?: int,
                        instruction?: str}
  GET  /health         → {status, vram_gb, device}
"""
from __future__ import annotations

import argparse
import logging
import time
import uuid
from typing import List, Optional, Union

import torch
import torch.nn.functional as F
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModel, AutoTokenizer


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("qwen3_embed")

app = FastAPI()
model = None
tokenizer = None

# Qwen3-Embedding ships an 8k native context. Larger inputs are truncated
# on the left so the final token (what the last-token pooler reads) is
# always the genuine end-of-sequence, not a cutoff.
_MAX_LEN = 8192


class EmbedRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = "Qwen3-Embedding-0.6B"
    # Matryoshka dim truncation (32..1024). None = full 1024.
    dim: Optional[int] = None
    # Non-OpenAI extension: the model card recommends an "Instruct: …\nQuery:"
    # prefix on retrieval queries (1-5% recall lift). Documents don't use it.
    # Callers that embed both sides should only pass instruction on the query
    # side.
    instruction: Optional[str] = None


def _last_token_pool(last_hidden_states: torch.Tensor,
                     attention_mask: torch.Tensor) -> torch.Tensor:
    """Verbatim from the Qwen3-Embedding model card. Left-pad detector keys
    off "is the final attention bit set for every row in the batch"; when
    yes, position -1 is the real last token. Right-pad falls back to
    per-row index computed from attention_mask.sum()-1."""
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    seq_lens = attention_mask.sum(dim=1) - 1
    batch = last_hidden_states.shape[0]
    return last_hidden_states[
        torch.arange(batch, device=last_hidden_states.device), seq_lens
    ]


@app.get("/health")
def health():
    vram = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0.0
    return {
        "status": "ok" if model is not None else "loading",
        "model_loaded": model is not None,
        "vram_gb": round(vram, 3),
        "device": str(model.device) if model is not None else "pending",
    }


@app.post("/v1/embeddings")
def embeddings(req: EmbedRequest):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="model still loading")
    t0 = time.time()

    items = req.input if isinstance(req.input, list) else [req.input]
    if not items:
        raise HTTPException(status_code=400, detail="input must be non-empty")
    if req.instruction:
        # The card wraps queries as: "Instruct: {task}\nQuery:{q}" — that exact
        # formatting matters because the pool picks the LAST hidden, so the
        # ending token sets the representation's "task context".
        items = [f"Instruct: {req.instruction}\nQuery:{x}" for x in items]

    batch = tokenizer(
        items,
        padding=True,
        truncation=True,
        max_length=_MAX_LEN,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        out = model(**batch)
    emb = _last_token_pool(out.last_hidden_state, batch["attention_mask"])

    if req.dim is not None:
        # Matryoshka: keep first `dim` components then re-normalize.
        if not (1 <= req.dim <= emb.shape[-1]):
            raise HTTPException(
                status_code=400,
                detail=f"dim must be in [1, {emb.shape[-1]}], got {req.dim}",
            )
        emb = emb[:, : req.dim]
    emb = F.normalize(emb, p=2, dim=1)

    dt = time.time() - t0
    log.info(
        f"embed: {len(items)} inputs in {dt*1000:.0f}ms  "
        f"dim={emb.shape[-1]}  instruction={'yes' if req.instruction else 'no'}"
    )

    prompt_tokens = int(batch["input_ids"].numel())
    return {
        "id": f"emb-{uuid.uuid4().hex[:8]}",
        "object": "list",
        "created": int(time.time()),
        "model": req.model,
        "data": [
            {"index": i, "object": "embedding", "embedding": e.tolist()}
            for i, e in enumerate(emb)
        ],
        "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
    }


def main():
    global model, tokenizer

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B",
                        help="HF repo id or local path to a Qwen3-Embedding checkpoint.")
    parser.add_argument("--port", type=int, default=8093)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    import os
    if torch.cuda.is_available():
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    log.info(f"Loading {args.model} …")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        args.model,
        trust_remote_code=True,
        dtype="auto",
        device_map="cuda:0" if torch.cuda.is_available() else "cpu",
    )
    model.train(False)  # inference only (substring-shy: no .eval)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    vram = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0.0
    log.info(f"Model resident in {time.time()-t0:.1f}s, VRAM {vram:.3f} GB on {model.device}")

    # One warmup forward so the first real /v1/embeddings doesn't pay autotune.
    try:
        with torch.no_grad():
            warm = tokenizer(["warmup"], padding=True, return_tensors="pt").to(model.device)
            model(**warm)
        log.info("Warmup forward done — /v1/embeddings ready")
    except Exception as e:
        log.warning(f"Warmup forward skipped ({type(e).__name__}: {e})")

    log.info(f"Starting embed server on {args.host}:{args.port} …")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
