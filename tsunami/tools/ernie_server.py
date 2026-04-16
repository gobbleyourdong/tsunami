"""ERNIE-Image HTTP server (BF16 pipeline, Turbo + Base DiT swap).

Loads the pipeline once at startup (DiT + Mistral3 TE + VAE all bf16 from
Baidu HF snapshot), holds it warm, serves /v1/images/generate (OpenAI-shape)
and /healthz. Single worker, single GPU — Spark's GB10 unified memory.

  python -m tsunami.tools.ernie_server --port 8092 --model Turbo

Swap Turbo ↔ Base at runtime via POST /v1/admin/swap?kind=Base — only the
DiT changes, TE/VAE/scheduler stay resident. BF16 throughout — GGUF path
removed 2026-04-16 because text rendering quality was unusable at Q4_K_M.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import glob
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from tsunami.tools.ernie_eval import build_pipeline, _find_baidu_snapshot
from tsunami.tools.image_ops import (
    pixelize as _pixelize,
    extract_bg as _extract_bg,
    BgExtractConfig,
    run_workflow as _run_workflow,
)
from PIL import Image

log = logging.getLogger("tsunami.ernie_server")

# Globals — pipeline lives here for the process's lifetime
_pipe = None
_loaded_kind: str = ""           # "Turbo" or "Base"; tracks current DiT
_lock = asyncio.Lock()           # serialize gens (diffusers pipes aren't reentrant)
_swap_lock = asyncio.Lock()      # separate from _lock so swap can pre-empt cleanly
_args: argparse.Namespace = None  # type: ignore


# Locked from unsloth/ERNIE-Image-Turbo-GGUF model card:
DEFAULT_STEPS = 8        # Turbo default; Base wants 50
DEFAULT_CFG = 1.0        # Turbo default; Base wants 4.0

# System prompt for prompt-enhancement via a vanilla Instruct LLM. ERNIE's
# original `pe` was fine-tuned for this contract; we coax a generic
# Mistral-3-Instruct into the same shape.
PE_SYSTEM_PROMPT = (
    "You are a prompt enhancer for a text-to-image diffusion model. "
    "The user gives you a short prompt and a target resolution as JSON. "
    "Output ONE single richly-detailed image-generation prompt, in one paragraph. "
    "Include: subject specifics, lighting, mood, composition, materials, color palette, lens/angle. "
    "Output ONLY the enhanced prompt itself — no quotes, no preamble, no explanation, no markdown."
)

# Per-workflow gen-side defaults: model + sampler. The Turbo class is the
# everyday driver (8 steps, ~20s, "good enough" for icons/sprites/logos
# and a draft of any pixelized scene). Infographic is the keeper class —
# Base DiT at 50 steps, ~4 min, dramatically better LAYOUT and reliable
# text rendering of dense compound strings. Caller can still override any
# of these per-request.
WORKFLOW_GEN_DEFAULTS = {
    "scene":       {"model_kind": "Turbo", "steps": 8,  "cfg": 1.0},
    "pixelize":    {"model_kind": "Turbo", "steps": 8,  "cfg": 1.0},
    "logo":        {"model_kind": "Turbo", "steps": 8,  "cfg": 1.0},
    "sprite":      {"model_kind": "Turbo", "steps": 8,  "cfg": 1.0},
    "icon":        {"model_kind": "Turbo", "steps": 8,  "cfg": 1.0},
    "infographic": {"model_kind": "Base",  "steps": 50, "cfg": 4.0},
}

NATIVE_RESOLUTIONS = {
    (1024, 1024), (848, 1264), (1264, 848),
    (768, 1376), (1376, 768),
    (896, 1200), (1200, 896),
}


class GenRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = DEFAULT_STEPS
    guidance_scale: float = DEFAULT_CFG
    seed: Optional[int] = None
    n: int = Field(1, ge=1, le=4, description="num images")
    response_format: str = Field("b64_json", description="b64_json or save_path")
    save_path: Optional[str] = None  # used when response_format=save_path
    use_pe: bool = Field(False, description="Use prompt enhancer LLM (--pe-url) — usually slop, leave off")
    # Per-request DiT selection. Server swaps if it doesn't match what's loaded.
    # Turbo: 8 steps, ~20s, draft quality. Base: 50 steps, ~4 min, keeper quality
    # with much better layout + reliable text rendering. Server defaults to whichever
    # was loaded at startup; explicit value here triggers a swap if needed.
    model_kind: Optional[str] = Field(None, description="Turbo | Base; swaps DiT if needed")


class GenResponseImage(BaseModel):
    b64_json: Optional[str] = None
    save_path: Optional[str] = None


class GenResponse(BaseModel):
    created: int
    data: list[GenResponseImage]
    timing: dict
    enhanced_prompt: Optional[str] = None  # populated if use_pe=true


# ─── Post-processing tool requests ──────────────────────────────────────

class ImageInput(BaseModel):
    """Either provide an input image as base64 PNG, or a server-readable path."""
    b64_json: Optional[str] = None
    path: Optional[str] = None


class PixelizeRequest(ImageInput):
    pixel_rows: int = 120
    palette: int = 32
    upscale: int = 1
    response_format: str = Field("b64_json", description="b64_json or save_path")
    save_path: Optional[str] = None


class ExtractBgRequest(ImageInput):
    bg_match: float = 10.0
    fringe_threshold: float = 50.0
    keep_largest_only: bool = True
    alpha_erosion_px: int = 1
    response_format: str = Field("b64_json")
    save_path: Optional[str] = None


class WorkflowRequest(GenRequest):
    """Compose gen + post-processing in one call.
    `kind` selects pipeline: scene | pixelize | logo | icon | sprite | infographic."""
    kind: str = Field("scene", description="scene|pixelize|logo|icon|sprite|infographic")
    # Optional overrides for any post-processing knob
    overrides: dict = Field(default_factory=dict)


class ImageResponse(BaseModel):
    created: int
    timing: dict
    image: GenResponseImage


def _load_input_image(req: ImageInput) -> Image.Image:
    if req.path:
        return Image.open(req.path)
    if req.b64_json:
        raw = base64.b64decode(req.b64_json)
        return Image.open(io.BytesIO(raw))
    raise HTTPException(400, "must provide either `b64_json` or `path`")


def _pack_image(img: Image.Image, response_format: str, save_path: Optional[str]) -> GenResponseImage:
    if response_format == "save_path":
        p = Path(save_path or f"/tmp/img_{int(time.time())}.png")
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p)
        return GenResponseImage(save_path=str(p))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return GenResponseImage(b64_json=base64.b64encode(buf.getvalue()).decode("ascii"))


def _enhance_via_llamacpp(prompt: str, width: int, height: int,
                          pe_url: str, max_tokens: int = 512) -> tuple[str, float]:
    """Hit a llama-server /v1/chat/completions to expand a prompt. Returns
    (enhanced_text, elapsed_seconds). Falls back to original prompt on error."""
    user_content = json.dumps(
        {"prompt": prompt, "width": width, "height": height},
        ensure_ascii=False,
    )
    payload = {
        "messages": [
            {"role": "system", "content": PE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.6,
        "top_p": 0.95,
    }
    t0 = time.time()
    try:
        with httpx.Client(timeout=60.0) as c:
            r = c.post(pe_url + "/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"].strip()
        # Strip common "Sure, here is the enhanced prompt:" preambles + any wrapping quotes
        for prefix in ("Enhanced prompt:", "Output:", "Prompt:"):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        text = text.strip("\"'`")
        return text, time.time() - t0
    except Exception as e:
        log.warning(f"pe enhancement failed ({e}) — falling back to original prompt")
        return prompt, time.time() - t0


app = FastAPI(title="ERNIE-Image-Turbo server")


@app.on_event("startup")
def _load_pipe():
    global _pipe, _loaded_kind
    log.info(f"Loading pipeline (model={_args.model}, bf16) ...")
    t0 = time.time()
    # text_encoder/vae/scheduler always loaded from Turbo snapshot (those
    # components are shared between Turbo and Base — only the DiT differs).
    _pipe = build_pipeline(
        gguf_path=None,  # BF16-only; GGUF path removed 2026-04-16
        baidu_snapshot=_find_baidu_snapshot("Turbo"),
        transformer_snapshot=_find_baidu_snapshot(_args.model),
        device=_args.device,
        te_gguf=None,  # BF16-only
    )
    _loaded_kind = _args.model
    torch.cuda.synchronize()
    vram = torch.cuda.memory_allocated() / (1024**3)
    log.info(f"Pipeline loaded in {time.time()-t0:.1f}s ({_loaded_kind}), "
             f"resident VRAM {vram:.2f} GB")


def _swap_dit(target_kind: str) -> dict:
    """Replace the pipeline's transformer with the requested kind's DiT.
    Frees the old DiT, loads the new one from baidu snapshot. text_encoder/
    vae/scheduler stay put — only the transformer changes."""
    global _loaded_kind
    if target_kind == _loaded_kind:
        return {"swapped": False, "kind": _loaded_kind, "elapsed_s": 0.0}
    if target_kind not in ("Turbo", "Base"):
        raise HTTPException(400, f"unknown kind {target_kind!r}; pick Turbo or Base")
    import gc
    from diffusers import ErnieImageTransformer2DModel
    log.info(f"Swap: {_loaded_kind} → {target_kind} ...")
    t0 = time.time()
    snapshot = _find_baidu_snapshot(target_kind)
    # Drop the current transformer + free its VRAM
    _pipe.transformer = None
    gc.collect()
    torch.cuda.empty_cache()
    # Load the new one
    new_dit = ErnieImageTransformer2DModel.from_pretrained(
        snapshot / "transformer", torch_dtype=torch.bfloat16,
    ).to(_args.device)
    _pipe.transformer = new_dit
    _loaded_kind = target_kind
    torch.cuda.synchronize()
    elapsed = time.time() - t0
    vram = torch.cuda.memory_allocated() / (1024**3)
    log.info(f"Swap done in {elapsed:.1f}s — now {_loaded_kind}, VRAM {vram:.2f} GB")
    return {"swapped": True, "kind": _loaded_kind, "elapsed_s": round(elapsed, 1)}


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "pipe_loaded": _pipe is not None,
        "loaded_kind": _loaded_kind,
        "swap_supported": True,  # always bf16 now
        "vram_gb": torch.cuda.memory_allocated() / (1024**3),
        "vram_peak_gb": torch.cuda.max_memory_allocated() / (1024**3),
        "te_mode": "bf16",
    }


@app.post("/v1/admin/swap")
async def admin_swap(kind: str):
    """Pre-warm a DiT so the next gen doesn't pay the swap cost.
    POST /v1/admin/swap?kind=Base   or   ?kind=Turbo"""
    async with _swap_lock:
        async with _lock:  # block any in-flight gen
            return _swap_dit(kind)


@app.post("/v1/images/generate", response_model=GenResponse)
async def generate(req: GenRequest):
    if _pipe is None:
        raise HTTPException(503, "pipeline not loaded yet")

    if (req.width, req.height) not in NATIVE_RESOLUTIONS:
        log.warning(f"non-native resolution {req.width}x{req.height} — "
                    f"native: {sorted(NATIVE_RESOLUTIONS)}")

    # Per-request DiT swap if the user asked for a different kind than loaded
    swap_info = None
    if req.model_kind and req.model_kind != _loaded_kind:
        async with _swap_lock:
            async with _lock:
                swap_info = _swap_dit(req.model_kind)

    enhanced_prompt = None
    pe_elapsed = 0.0
    if req.use_pe:
        if not _args.pe_url:
            raise HTTPException(400, "use_pe=true but server started without --pe-url")
        enhanced_prompt, pe_elapsed = _enhance_via_llamacpp(
            req.prompt, req.width, req.height, _args.pe_url
        )
        log.info(f"pe enhanced in {pe_elapsed:.2f}s: "
                 f"'{req.prompt[:60]}…' → '{enhanced_prompt[:80]}…'")
    effective_prompt = enhanced_prompt if enhanced_prompt else req.prompt

    async with _lock:
        torch.cuda.reset_peak_memory_stats()
        t_total = time.time()
        gen = torch.Generator(device=_args.device)
        if req.seed is not None:
            gen.manual_seed(req.seed)

        step_times: list[float] = []
        def _on_step(p, idx, ts, kw):
            torch.cuda.synchronize()
            step_times.append(time.time())
            return kw

        # NOTE: we deliberately call pipe() synchronously on the event-loop
        # thread, NOT via asyncio.to_thread. Running in a worker thread put
        # us on a different CUDA stream context than the model was loaded
        # under, costing ~60% per-step latency (5300ms vs 3225ms direct).
        # The lock above already serializes gens, so async-ness during a gen
        # buys nothing.
        result = _pipe(
            prompt=[effective_prompt] * req.n,
            negative_prompt=[req.negative_prompt] * req.n if req.negative_prompt else None,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=req.guidance_scale,
            use_pe=False,  # we do enhancement upstream via _enhance_via_llamacpp
            generator=gen,
            callback_on_step_end=_on_step,
        )
        images = result.images
        torch.cuda.synchronize()
        elapsed = time.time() - t_total

        out_images: list[GenResponseImage] = []
        for i, img in enumerate(images):
            if req.response_format == "save_path":
                p = Path(req.save_path or f"/tmp/ernie_{int(time.time())}_{i}.png")
                p.parent.mkdir(parents=True, exist_ok=True)
                img.save(p)
                out_images.append(GenResponseImage(save_path=str(p)))
            else:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                out_images.append(GenResponseImage(
                    b64_json=base64.b64encode(buf.getvalue()).decode("ascii")
                ))

        deltas = [step_times[i] - step_times[i-1] for i in range(1, len(step_times))]
        timing = {
            "total_s": round(elapsed, 2),
            "pe_s": round(pe_elapsed, 2) if req.use_pe else None,
            "swap_s": swap_info["elapsed_s"] if swap_info else None,
            "kind": _loaded_kind,
            "mean_step_ms": round(sum(deltas)/max(1,len(deltas))*1000, 0) if deltas else None,
            "step_ms": [round(d*1000, 0) for d in deltas],
            "peak_vram_gb": round(torch.cuda.max_memory_allocated()/(1024**3), 2),
        }

    return GenResponse(
        created=int(time.time()), data=out_images, timing=timing,
        enhanced_prompt=enhanced_prompt,
    )


# ─── Stand-alone post-processing endpoints ──────────────────────────────

@app.post("/v1/images/pixelize", response_model=ImageResponse)
def pixelize_endpoint(req: PixelizeRequest):
    """Block-downsample + palette-quantize. No alpha extraction — preserves
    background. For sprite/icon use, run /v1/images/extract-bg first."""
    src = _load_input_image(req)
    t0 = time.time()
    out = _pixelize(src, pixel_rows=req.pixel_rows, palette=req.palette, upscale=req.upscale)
    elapsed = time.time() - t0
    return ImageResponse(
        created=int(time.time()),
        timing={"pixelize_s": round(elapsed, 3),
                "out_size": [out.size[0], out.size[1]]},
        image=_pack_image(out, req.response_format, req.save_path),
    )


@app.post("/v1/images/extract-bg", response_model=ImageResponse)
def extract_bg_endpoint(req: ExtractBgRequest):
    """Alpha-key the background. Auto-detects bg color from edge pixels,
    iteratively peels fringe, returns RGBA at input resolution."""
    src = _load_input_image(req)
    t0 = time.time()
    cfg = BgExtractConfig(
        bg_match=req.bg_match,
        fringe_threshold=req.fringe_threshold,
        keep_largest_only=req.keep_largest_only,
        alpha_erosion_px=req.alpha_erosion_px,
    )
    out = _extract_bg(src, cfg)
    elapsed = time.time() - t0
    return ImageResponse(
        created=int(time.time()),
        timing={"extract_bg_s": round(elapsed, 3)},
        image=_pack_image(out, req.response_format, req.save_path),
    )


# ─── Workflow gateway ───────────────────────────────────────────────────

@app.post("/v1/workflows/{kind}", response_model=GenResponse)
async def workflow(kind: str, req: WorkflowRequest):
    """Gen + (optional) extract_bg + (optional) pixelize, gated by kind:

      scene       = Turbo gen only (raw cartoon, ~20s)
      pixelize    = Turbo gen → pixelize(270 rows, 32 colors, 4× upscale) — pixel-art look
      logo        = Turbo gen → extract_bg (transparent PNG; keep_largest_only=False for wordmarks)
      icon        = Turbo gen → extract_bg (transparent PNG; keep_largest_only=True single-subject)
      sprite      = Turbo gen → extract_bg → pixelize(64 rows, 16 colors, 8×) — only workflow that combines both
      infographic = BASE gen (50 steps, cfg=4.0, ~4 min) — keeper-quality

    For pixelizing an existing image (photo or generated output), POST to
    /v1/images/pixelize directly instead — this /v1/workflows/pixelize route
    is the gen+pixelize composed version.
                    layout + reliable text rendering. No post-processing.

    Per-request `model_kind`, `num_inference_steps`, `guidance_scale` overrides
    take precedence over the workflow defaults.
    """
    if kind not in WORKFLOW_GEN_DEFAULTS:
        raise HTTPException(400, f"unknown kind {kind!r} — pick one of {list(WORKFLOW_GEN_DEFAULTS)}")

    # Apply per-workflow gen-side defaults if the client didn't override them.
    defaults = WORKFLOW_GEN_DEFAULTS[kind]
    raw = req.model_dump()
    if raw.get("model_kind") is None:
        raw["model_kind"] = defaults["model_kind"]
    # The pydantic defaults for steps/cfg are Turbo (8/1.0). We override only
    # if the workflow wants something else AND the caller didn't explicitly
    # pass non-Turbo values. Detection: if the request matches Turbo defaults
    # exactly, assume client didn't customize; apply workflow's preset.
    if raw["num_inference_steps"] == DEFAULT_STEPS and raw["guidance_scale"] == DEFAULT_CFG:
        raw["num_inference_steps"] = defaults["steps"]
        raw["guidance_scale"] = defaults["cfg"]

    # Force gen-side in-memory so we can pipe to post-processing without disk.
    raw["response_format"] = "b64_json"
    raw["save_path"] = None
    gen_req = GenRequest(**raw)

    # Reuse the existing /generate handler logic — keep DRY by just calling it
    gen_resp = await generate(gen_req)
    # Decode the first image into PIL
    first = gen_resp.data[0]
    raw_bytes = base64.b64decode(first.b64_json)
    pil = Image.open(io.BytesIO(raw_bytes))

    t0 = time.time()
    out, wf_timings = _run_workflow(pil, kind, **req.overrides)
    out_pack = _pack_image(out, req.response_format, req.save_path)

    timing = {**gen_resp.timing, "workflow_s": round(time.time() - t0, 3),
              **wf_timings, "kind": kind}
    return GenResponse(
        created=int(time.time()), data=[out_pack], timing=timing,
        enhanced_prompt=gen_resp.enhanced_prompt,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=("Turbo", "Base"), default="Turbo",
                   help="ERNIE-Image-Turbo (8 steps, distilled) or ERNIE-Image (50 steps, full). "
                        "Swap at runtime via POST /v1/admin/swap?kind=Base.")
    p.add_argument("--port", type=int, default=8092)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--device", default="cuda")
    p.add_argument("--pe-url", default="http://localhost:8094",
                   help="llama-server URL for prompt enhancement (set to '' to disable)")
    global _args
    _args = p.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(app, host=_args.host, port=_args.port, log_level="info")


if __name__ == "__main__":
    main()
