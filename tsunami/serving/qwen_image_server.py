"""Qwen-Image-Edit HTTP server — single-pipeline, LoRA-hot-swappable.

Matches the ernie_server.py architecture: single worker, single GPU,
pipeline loaded once at startup, held warm. Serves /healthz,
/v1/images/generate (base gen), /v1/images/edit (the distinctive
edit-image capability), and /v1/admin/lora for hot-swapping the
Multiple-Angles-LoRA when sprite-sheet work is active.

  python -m tsunami.serving.qwen_image_server --port 8094

Motivating use case (sprite sheet generation):
  1. Base sprite rendered once via /v1/images/generate (canonical pose)
  2. LoRA attach via /v1/admin/lora?name=multiple_angles
  3. Per-frame edit via /v1/images/edit — same character, rotated/posed
     per prompt ("facing left, walk frame 3", "attack windup")
  4. LoRA detach when done (/v1/admin/lora?name=none) to free modules

Identity consistency across frames is the point: plain text-to-image
re-rolls the character each time. Edit-mode preserves it.

Memory footprint (bf16):
  Qwen-Image-Edit-2511:   ~27 GB on GPU (bf16 from ~54 GB disk)
  Lightning distill:      same shape, fewer steps (4-8 vs 20-30)
  Multiple-Angles-LoRA:   ~150 MB

Co-existence on DGX Spark (128 GB unified):
  Qwen3.6-35B-FP8:        ~35 GB   (/v1/chat)
  ERNIE-Image-Turbo bf16: ~22 GB   (/v1/images — fast text-to-image)
  Qwen3-Embedding-0.6B:   ~1 GB    (/v1/embeddings)
  Qwen-Image-Edit-2511:   ~27 GB   (this server)
  ─────────────────────────────────
  Total:                  ~85 GB — fits with ~43 GB headroom, but tight
  under warmup spikes. For reliable operation, consider ramping Qwen3.6
  down when sprite work is active (see `tsu swap` pattern for ERNIE).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import logging
import time
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from PIL import Image
import uvicorn

log = logging.getLogger("tsunami.qwen_image_server")

# Globals — pipeline lives here for the process's lifetime.
# Matches ernie_server.py conventions: module-level pipe + locks, CLI
# args captured in _args, startup loads once, swap functions take the
# _swap_lock so they pre-empt cleanly without racing generation calls.
_pipe = None
_loaded_model: str = ""          # HF model id or local path that's resident
_loaded_loras: list[str] = []    # LoRA adapter names currently attached
_lock = asyncio.Lock()           # serialize gens (diffusers pipes aren't reentrant)
_swap_lock = asyncio.Lock()      # LoRA/model swap lock, separate from _lock
_args: argparse.Namespace = None  # type: ignore

# Locked from the Qwen-Image-Edit-2511 model card:
DEFAULT_STEPS_BASE = 30           # non-lightning base steps
DEFAULT_STEPS_LIGHTNING = 8       # lightning-distilled steps
DEFAULT_GUIDANCE = 4.0            # Qwen-Image-Edit classifier-free default
DEFAULT_SIZE = 1024

# LoRA registry — HF repo ids for each named adapter. Keeps the
# operator-facing `name` param stable even if we change providers.
_LORA_REGISTRY: dict[str, str] = {
    "multiple_angles": "fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA",
    "lightning": "lightx2v/Qwen-Image-Edit-2511-Lightning",
}


class GenRequest(BaseModel):
    """Base text-to-image generation (no input image)."""
    prompt: str
    negative_prompt: Optional[str] = None
    height: int = DEFAULT_SIZE
    width: int = DEFAULT_SIZE
    num_inference_steps: int = DEFAULT_STEPS_BASE
    guidance_scale: float = DEFAULT_GUIDANCE
    seed: Optional[int] = None
    n: int = Field(1, ge=1, le=4, description="num images")
    response_format: str = Field("b64_json", description="b64_json or save_path")
    save_path: Optional[str] = None


class ImageInput(BaseModel):
    """Provide input image either as base64 PNG or a server-readable path."""
    b64_json: Optional[str] = None
    path: Optional[str] = None


class EditRequest(GenRequest, ImageInput):
    """Edit an input image conditioned on a text prompt. The distinctive
    Qwen-Image-Edit capability: same identity, pose/angle/context varied
    per the prompt. For sprite sheets, `path` is the base-sprite PNG,
    `prompt` describes the target frame (e.g. 'same character, 3/4 back
    view, mid-stride in a run cycle')."""
    # Edit-specific knobs — how much to deviate from the input image.
    # Lower = more faithful to input (just pose tweaks); higher = more
    # creative (but risks identity drift, the whole reason we're using
    # edit-mode instead of pure T2I).
    strength: float = Field(0.75, ge=0.0, le=1.0,
                            description="input-image adherence (0=copy, 1=full redraw)")


class LoraSwapRequest(BaseModel):
    """Attach a single LoRA (by registry name) or detach all with name='none'."""
    name: str = Field(description="LoRA registry name, or 'none' to detach all")
    scale: float = Field(1.0, ge=0.0, le=2.0,
                          description="LoRA strength multiplier; 1.0 = as-published")


class GenResponseImage(BaseModel):
    b64_json: Optional[str] = None
    save_path: Optional[str] = None


class GenResponse(BaseModel):
    created: int
    data: list[GenResponseImage]
    timing: dict
    loaded_loras: list[str]


def _load_input_image(req: ImageInput) -> Image.Image:
    """Mirror of ernie_server._load_input_image — same contract."""
    if req.path:
        return Image.open(req.path).convert("RGB")
    if req.b64_json:
        raw = base64.b64decode(req.b64_json)
        return Image.open(io.BytesIO(raw)).convert("RGB")
    raise HTTPException(400, "must provide either `b64_json` or `path`")


def _pack_image(img: Image.Image, response_format: str, save_path: Optional[str]) -> GenResponseImage:
    """Mirror of ernie_server._pack_image — same contract."""
    if response_format == "save_path":
        p = Path(save_path or f"/tmp/qwen_img_{int(time.time())}.png")
        p.parent.mkdir(parents=True, exist_ok=True)
        img.save(p)
        return GenResponseImage(save_path=str(p))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return GenResponseImage(b64_json=base64.b64encode(buf.getvalue()).decode("ascii"))


app = FastAPI(title="Qwen-Image-Edit server")


@app.on_event("startup")
def _load_pipe():
    """Load the edit pipeline once. Uses diffusers' AutoPipelineForImage2Image
    which dispatches to QwenImageEditPipeline for the Qwen-Image-Edit-2511
    repo. bf16 on CUDA."""
    global _pipe, _loaded_model
    log.info(f"Loading pipeline: {_args.model}")
    t0 = time.time()
    try:
        from diffusers import AutoPipelineForImage2Image
    except ImportError as e:
        log.error(f"diffusers import failed: {e}. Install: pip install diffusers accelerate")
        raise

    _pipe = AutoPipelineForImage2Image.from_pretrained(
        _args.model,
        torch_dtype=torch.bfloat16,
    )
    _pipe = _pipe.to(_args.device)
    _loaded_model = _args.model
    # Startup LoRA — operator can specify at boot for sprite-sheet workflows.
    if _args.lora and _args.lora != "none":
        _attach_lora_sync(_args.lora, scale=1.0)

    torch.cuda.synchronize()
    vram = torch.cuda.memory_allocated() / (1024**3)
    log.info(f"Pipeline loaded in {time.time()-t0:.1f}s ({_loaded_model}), "
             f"resident VRAM {vram:.2f} GB, loras={_loaded_loras}")


def _attach_lora_sync(name: str, scale: float = 1.0) -> None:
    """Core LoRA attach — sync helper used by startup + admin endpoint.
    Raises HTTPException on unknown registry name."""
    if name not in _LORA_REGISTRY:
        raise HTTPException(400,
            f"unknown lora name {name!r}; registered: {list(_LORA_REGISTRY)}")
    repo = _LORA_REGISTRY[name]
    log.info(f"Attaching LoRA: {name} ({repo}, scale={scale})")
    _pipe.load_lora_weights(repo, adapter_name=name)
    # diffusers' set_adapters wants the full list of active adapters
    active = _loaded_loras + [name] if name not in _loaded_loras else list(_loaded_loras)
    scales = [scale] * len(active)
    _pipe.set_adapters(active, adapter_weights=scales)
    if name not in _loaded_loras:
        _loaded_loras.append(name)


def _detach_all_loras_sync() -> None:
    log.info(f"Detaching all LoRAs ({_loaded_loras})")
    if hasattr(_pipe, "unload_lora_weights"):
        _pipe.unload_lora_weights()
    _loaded_loras.clear()


@app.get("/healthz")
def healthz():
    """Liveness probe — matches ernie_server shape so dispatch code can
    test both endpoints identically."""
    vram_gb = 0.0
    if torch.cuda.is_available():
        vram_gb = torch.cuda.memory_allocated() / (1024**3)
    return {
        "status": "ok",
        "pipe_loaded": _pipe is not None,
        "loaded_model": _loaded_model,
        "loaded_loras": list(_loaded_loras),
        "vram_gb": vram_gb,
    }


@app.post("/v1/admin/lora")
async def admin_lora(req: LoraSwapRequest):
    """Hot-swap the attached LoRA set. `name='none'` detaches all.
    Otherwise attaches the named adapter from _LORA_REGISTRY."""
    async with _swap_lock:
        # Wait for in-flight gens to complete — LoRA attach during
        # generation is undefined behavior in diffusers.
        async with _lock:
            if req.name == "none":
                _detach_all_loras_sync()
            else:
                _attach_lora_sync(req.name, scale=req.scale)
            return {
                "loaded_loras": list(_loaded_loras),
                "loaded_model": _loaded_model,
            }


@app.post("/v1/images/generate", response_model=GenResponse)
async def generate(req: GenRequest):
    """Text-to-image. For spritesheet workflow, use this ONCE for the
    canonical base sprite, then switch to /v1/images/edit for per-frame
    variations."""
    if _pipe is None:
        raise HTTPException(503, "pipeline not loaded")
    t0 = time.time()
    async with _lock:
        gen_args = dict(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=req.guidance_scale,
            num_images_per_prompt=req.n,
        )
        if req.seed is not None:
            gen_args["generator"] = torch.Generator(device=_args.device).manual_seed(req.seed)
        result = _pipe(**gen_args)
    imgs: list[Image.Image] = result.images
    data = [_pack_image(im, req.response_format, req.save_path) for im in imgs]
    return GenResponse(
        created=int(time.time()),
        data=data,
        timing={"elapsed_s": round(time.time() - t0, 2)},
        loaded_loras=list(_loaded_loras),
    )


@app.post("/v1/images/edit", response_model=GenResponse)
async def edit(req: EditRequest):
    """Image-to-image edit — the distinctive Qwen-Image-Edit capability.
    Feeds `image` alongside `prompt` so identity is preserved while the
    pose/angle/context varies per the prompt. Combined with the
    Multiple-Angles-LoRA (/v1/admin/lora?name=multiple_angles), this is
    the sprite-sheet generator's core primitive."""
    if _pipe is None:
        raise HTTPException(503, "pipeline not loaded")
    img = _load_input_image(req)
    t0 = time.time()
    async with _lock:
        gen_args = dict(
            prompt=req.prompt,
            image=img,
            negative_prompt=req.negative_prompt,
            strength=req.strength,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=req.guidance_scale,
            num_images_per_prompt=req.n,
        )
        if req.seed is not None:
            gen_args["generator"] = torch.Generator(device=_args.device).manual_seed(req.seed)
        result = _pipe(**gen_args)
    imgs: list[Image.Image] = result.images
    data = [_pack_image(im, req.response_format, req.save_path) for im in imgs]
    return GenResponse(
        created=int(time.time()),
        data=data,
        timing={"elapsed_s": round(time.time() - t0, 2)},
        loaded_loras=list(_loaded_loras),
    )


def main():
    """CLI mirror of ernie_server.main — same flags + a --lora startup option.

    Usage:
      python -m tsunami.serving.qwen_image_server --port 8094
      python -m tsunami.serving.qwen_image_server --port 8094 --lora multiple_angles
      python -m tsunami.serving.qwen_image_server --model Qwen/Qwen-Image-Edit-2511 \\
                                                   --lora lightning --port 8094
    """
    global _args
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen-Image-Edit-2511",
                    help="HF repo id for the base pipeline")
    ap.add_argument("--lora", default="none",
                    help="LoRA name to attach at startup (registry: "
                         "multiple_angles / lightning / none)")
    ap.add_argument("--port", type=int, default=8094)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--device", default="cuda")
    _args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    uvicorn.run(app, host=_args.host, port=_args.port, log_level="info")


if __name__ == "__main__":
    main()
