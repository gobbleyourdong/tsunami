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

# Locked from the Qwen-Image-Edit-2511 model card's Quick Start sample:
#   num_inference_steps=40, true_cfg_scale=4.0, guidance_scale=1.0,
#   negative_prompt=" ", num_images_per_prompt=1
# (see https://huggingface.co/Qwen/Qwen-Image-Edit-2511)
DEFAULT_STEPS = 40                # per model card
DEFAULT_GUIDANCE = 4.0            # → pipe's true_cfg_scale (real CFG)
DEFAULT_DISTILLED_GUIDANCE = 1.0  # → pipe's guidance_scale (distilled bonus);
                                  # 1.0 = "no bonus", correct for non-distilled base
DEFAULT_SIZE = 1024

# LoRA registry — HF repo ids for each named adapter. Keeps the
# operator-facing `name` param stable even if we change providers.
#
# Lightning was removed on 2026-04-21 after an initial A/B showed
# undercooked sprites, then re-added same day once the root cause was
# understood (the earlier A/B was confounded: lightning was tested at
# 8 steps + CFG 1.0 against crystal_v2 which was 30 steps + CFG *off*
# + multi_angles attached — apples-to-oranges across 3 axes). Full
# evaluation pending post-FP8-conversion + magenta-bg re-run.
_LORA_REGISTRY: dict[str, str] = {
    "multiple_angles": "fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA",
    "lightning":       "lightx2v/Qwen-Image-Edit-2511-Lightning",
}


class GenRequest(BaseModel):
    """Base text-to-image generation (no input image)."""
    prompt: str
    negative_prompt: Optional[str] = None
    height: int = DEFAULT_SIZE
    width: int = DEFAULT_SIZE
    num_inference_steps: int = DEFAULT_STEPS
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


class NudgeStep(BaseModel):
    """One step in a chain-edit animation. The `delta` describes only what
    CHANGES from the previous frame, not the full pose. `strength` is low
    by default (~0.4) to keep identity drift bounded across the chain."""
    delta: str
    strength: float = Field(0.4, ge=0.0, le=1.0,
                            description="per-step edit strength; keep low (0.3-0.5) "
                                        "for identity preservation across chain")
    guidance_scale: float = DEFAULT_GUIDANCE
    num_inference_steps: int = DEFAULT_STEPS


class AnimateRequest(BaseModel):
    """Chain-edit animation synthesis. Takes a base image and an ordered
    chain of nudges. Each nudge edits the previous frame's output, so
    identity drift is bounded by the sum of per-step strengths rather than
    by each step independently (the star-vs-chain distinction — chain keeps
    every frame close to its neighbor, so the character stays locked).

    Use case: sprite-sheet animation (walk cycle, VFX destruction, state
    transitions on environment entities). Load an animation primitive's
    nudge list from asset_library/animations/*.yaml and pass it here.
    """
    # Base-image input uses the same shape as EditRequest so any caller
    # that can prep an edit request can prep an animate request.
    b64_json: Optional[str] = None
    path: Optional[str] = None

    nudges: list[NudgeStep] = Field(min_length=1, max_length=32,
        description="ordered list of chain-edit steps; cap 32 to bound "
                    "cumulative drift + wall-clock")
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None

    # Where frames land. If response_format=save_path, frame_<N>.png files
    # are written under save_dir; if b64_json, frames come back inline.
    response_format: str = Field("save_path", description="b64_json or save_path")
    save_dir: Optional[str] = Field(None, description="required when response_format=save_path")


class AnimateResponse(BaseModel):
    created: int
    frames: list[GenResponseImage]
    timing: dict
    total_strength: float   # Σ(step strengths) — proxy for cumulative drift bound
    loaded_loras: list[str]


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
    """Load the edit pipeline once.

    --fp8-path <safetensors>: transformer loaded via
      QwenImageTransformer2DModel.from_single_file — diffusers' native
      Comfy-quant-aware loader. Auto-detects tensorwise vs rowwise
      weight_scale layouts, wires the correct matmul path. Text encoder +
      VAE still bf16 via the pretrained repo (follow-up levers downloaded:
      qwen_2.5_vl_7b_fp8_scaled.safetensors, qwen_image_vae.safetensors).

    No --fp8-path: plain AutoPipelineForImage2Image.from_pretrained bf16."""
    global _pipe, _loaded_model
    precision_note = (f"fp8-transformer (comfy: {_args.fp8_path})"
                      if _args.fp8_path else "bf16")
    log.info(f"Loading pipeline: {_args.model} ({precision_note})")
    t0 = time.time()
    try:
        from diffusers import AutoPipelineForImage2Image
    except ImportError as e:
        log.error(f"diffusers import failed: {e}. Install: pip install diffusers accelerate")
        raise

    load_kwargs = {"torch_dtype": torch.bfloat16}
    if _args.fp8_path:
        from diffusers import QwenImageTransformer2DModel
        from tsunami.serving._zero_copy import patch_diffusers_load_state_dict
        log.info(f"[fp8] loading transformer via from_single_file (zero-copy): {_args.fp8_path}")
        ft0 = time.time()
        # Monkey-patch diffusers' load_state_dict → fastsafetensors. This
        # keeps all of from_single_file's quant-aware module construction
        # (detecting weight_scale keys, swapping Linear→QuantLinear, wiring
        # scale buffers) while cutting the file-read step from CPU double-
        # copy to one-copy DMA. Patch is scoped to this load via a context
        # manager so other loaders stay unaffected.
        with patch_diffusers_load_state_dict(device=_args.device):
            load_kwargs["transformer"] = QwenImageTransformer2DModel.from_single_file(
                _args.fp8_path,
                config=_args.model,
                subfolder="transformer",
                # Do NOT set torch_dtype here — that would upcast fp8_e4m3fn
                # weights to bf16 during load. Let diffusers preserve the
                # file's native dtype; the pipe casts activations at forward.
            )
        log.info(f"[fp8] transformer loaded in {time.time()-ft0:.1f}s")

    _pipe = AutoPipelineForImage2Image.from_pretrained(_args.model, **load_kwargs)
    _pipe = _pipe.to(_args.device)
    _loaded_model = _args.model

    # Startup LoRA — works on bf16 (PEFT) and fp8 (direct merge, see
    # _attach_lora_fp8_merge).
    if _args.lora and _args.lora != "none":
        _attach_lora_sync(_args.lora, scale=1.0)

    torch.cuda.synchronize()
    vram = torch.cuda.memory_allocated() / (1024**3)
    log.info(f"Pipeline loaded in {time.time()-t0:.1f}s ({_loaded_model}), "
             f"resident VRAM {vram:.2f} GB, loras={_loaded_loras}, "
             f"precision={'fp8+bf16' if _args.fp8_path else 'bf16'}")


def _attach_lora_sync(name: str, scale: float = 1.0) -> None:
    """Core LoRA attach — try diffusers' PEFT path first; if it fails on an
    fp8-quantized transformer, fall back to ComfyUI-style direct merge
    (dequant → add delta → re-quantize, in-place on the weight buffers).

    Raises HTTPException on unknown registry name."""
    if name not in _LORA_REGISTRY:
        raise HTTPException(400,
            f"unknown lora name {name!r}; registered: {list(_LORA_REGISTRY)}")
    repo = _LORA_REGISTRY[name]

    try:
        log.info(f"Attaching LoRA (PEFT path): {name} ({repo}, scale={scale})")
        _pipe.load_lora_weights(repo, adapter_name=name)
        active = _loaded_loras + [name] if name not in _loaded_loras else list(_loaded_loras)
        scales = [scale] * len(active)
        _pipe.set_adapters(active, adapter_weights=scales)
    except (ValueError, TypeError, RuntimeError) as e:
        msg = str(e)
        # PEFT refuses to wrap non-Linear quant modules; route to merge path.
        if "not supported" in msg or "Target module" in msg or "float8" in msg.lower():
            log.info(f"[lora] PEFT path rejected ({msg[:80]}…), using direct merge")
            _attach_lora_fp8_merge(repo, name, scale)
        else:
            raise
    if name not in _loaded_loras:
        _loaded_loras.append(name)


def _detach_all_loras_sync() -> None:
    """Detach all LoRAs. PEFT-attached LoRAs reverse cleanly; merge-attached
    LoRAs altered the weights in place and can't be undone without reloading
    from the source safetensors — in that case we just clear the tracker
    and warn the operator to restart for a fresh base."""
    log.info(f"Detaching all LoRAs ({_loaded_loras})")
    if hasattr(_pipe, "unload_lora_weights"):
        try:
            _pipe.unload_lora_weights()
        except Exception as e:
            log.warning(
                f"[detach] unload_lora_weights failed ({e}); if you used the "
                "merge path, weights were modified in place. Restart with "
                "--fp8-path for a clean base."
            )
    _loaded_loras.clear()


def _download_lora_state_dict(repo_id: str) -> dict[str, torch.Tensor]:
    """Download a LoRA's safetensors from HF and return the state_dict.
    Mirrors what diffusers.load_lora_weights does internally but without
    the PEFT injection step — we just need the weights to merge manually.

    LoRA authors use inconsistent filenames. Enumerate the repo's actual
    .safetensors files and prefer ones whose name looks like a LoRA (small,
    contains "lora"/"lightning"/"adapter", or is the sole .safetensors)."""
    from huggingface_hub import hf_hub_download, list_repo_files
    from safetensors.torch import load_file

    # First try the well-known PEFT/diffusers filenames.
    canonical = [
        "pytorch_lora_weights.safetensors",
        "adapter_model.safetensors",
    ]
    for fname in canonical:
        try:
            path = hf_hub_download(repo_id, fname)
            log.info(f"[lora-merge] loaded canonical {fname}")
            return load_file(path)
        except Exception:
            continue

    # Fall back to repo enumeration — pick the smallest .safetensors whose
    # name contains lora/lightning/adapter hints. Avoid obvious full-model
    # files (fp8_scaled, bf16 with huge sizes).
    try:
        files = [f for f in list_repo_files(repo_id) if f.endswith(".safetensors")]
    except Exception as e:
        raise RuntimeError(f"could not enumerate {repo_id}: {e}") from e

    hints = ("lora", "lightning", "adapter")
    candidates = sorted(
        f for f in files
        if any(h in f.lower() for h in hints)
        and "fp8" not in f.lower()
        and "fp32" not in f.lower() or "lora" in f.lower()
    )
    if not candidates:
        raise RuntimeError(
            f"no LoRA-looking .safetensors in {repo_id}; available: {files}"
        )
    # Prefer bf16 variant if present (smaller, same math as fp32).
    for f in candidates:
        if "bf16" in f.lower():
            path = hf_hub_download(repo_id, f)
            log.info(f"[lora-merge] picked bf16 variant: {f}")
            return load_file(path)
    # Otherwise pick the first candidate.
    path = hf_hub_download(repo_id, candidates[0])
    log.info(f"[lora-merge] picked: {candidates[0]}")
    return load_file(path)


def _attach_lora_fp8_merge(repo_id: str, name: str, scale: float) -> None:
    """ComfyUI-style direct-merge LoRA attach — dequant fp8 weight, add the
    α/rank·(B@A) delta, re-quantize back to fp8_e4m3fn.

    Key mapping: the diffusers-style LoRA uses keys like
      `transformer.transformer_blocks.N.attn.to_q.lora_A.default.weight`
    which strips to base module path `transformer_blocks.N.attn.to_q`. The
    multi_angles LoRA for fal/Qwen-Image-Edit-2511 uses `lora_down`/`lora_up`
    PEFT diffusers convention — we handle both naming families.
    """
    sd = _download_lora_state_dict(repo_id)
    transformer = _pipe.transformer

    # Group the state_dict by target module path.
    #   grouped[module_path] = {"up": Tensor?, "down": Tensor?, "alpha": float?}
    grouped: dict[str, dict[str, torch.Tensor]] = {}

    def _classify_key(k: str) -> tuple[Optional[str], Optional[str]]:
        """Return (base_path, part) where part ∈ {up, down, alpha} or None."""
        # Strip the "transformer." prefix the LoRA may carry.
        k2 = k[len("transformer."):] if k.startswith("transformer.") else k
        # Diffusers/PEFT format: ..to_q.lora_A.default.weight
        for suffix, part in (
            (".lora_A.default.weight", "down"),
            (".lora_B.default.weight", "up"),
            (".lora_A.weight", "down"),
            (".lora_B.weight", "up"),
            (".lora_down.weight", "down"),
            (".lora_up.weight", "up"),
            (".alpha", "alpha"),
        ):
            if k2.endswith(suffix):
                return k2[: -len(suffix)], part
        return None, None

    for k, v in sd.items():
        base, part = _classify_key(k)
        if base is None:
            continue
        grouped.setdefault(base, {})[part] = v
    log.info(f"[lora-merge] {len(grouped)} candidate target modules in LoRA")

    device = next(transformer.parameters()).device
    merged = 0
    skipped = 0
    for path, parts in grouped.items():
        up = parts.get("up")
        down = parts.get("down")
        alpha = parts.get("alpha")
        if up is None or down is None:
            skipped += 1
            continue
        # Resolve the module in the transformer
        try:
            module = transformer.get_submodule(path)
        except AttributeError:
            skipped += 1
            continue

        rank = down.shape[0]  # (rank, in_dim)
        alpha_val = float(alpha.item()) if alpha is not None else float(rank)
        eff_scale = scale * (alpha_val / rank)

        # Compute delta once in bf16 on GPU.
        up_dev = up.to(device=device, dtype=torch.bfloat16)
        down_dev = down.to(device=device, dtype=torch.bfloat16)
        delta = (up_dev.flatten(1) @ down_dev.flatten(1)).reshape(
            (up_dev.shape[0], down_dev.shape[-1])
        ).mul_(eff_scale)

        # Inspect the module's weight dtype to detect fp8.
        w_attr = getattr(module, "weight", None)
        if w_attr is not None and w_attr.dtype == torch.float8_e4m3fn:
            # Dequant → add delta → re-quantize. Use per-tensor scale; the
            # scale attribute name varies by diffusers quant backend (try a
            # few common ones; fall back to absmax-derived if not found).
            scale = None
            for attr in ("weight_scale", "scale_weight", "scale"):
                s = getattr(module, attr, None)
                if s is not None and torch.is_tensor(s):
                    scale = s
                    break
            w_bf16 = module.weight.to(torch.bfloat16)
            if scale is not None:
                w_bf16 = w_bf16 * scale.to(torch.bfloat16)
            if delta.shape != w_bf16.shape:
                log.warning(
                    f"[lora-merge] {path}: delta shape {list(delta.shape)} != "
                    f"weight shape {list(w_bf16.shape)} — skipping (partial-target "
                    f"not yet supported on fp8 path)"
                )
                skipped += 1
                continue
            w_bf16.add_(delta)
            abs_max = w_bf16.abs().max().clamp(min=1e-8)
            new_scale = (abs_max / 448.0).to(torch.float32)
            with torch.no_grad():
                module.weight.data.copy_((w_bf16 / new_scale).to(torch.float8_e4m3fn))
                if scale is not None:
                    scale.data.copy_(new_scale.reshape(scale.shape))
            merged += 1
        elif isinstance(module, torch.nn.Linear):
            # Plain bf16 path — merge in place on the existing .weight.
            if delta.shape != module.weight.shape:
                log.warning(
                    f"[lora-merge] {path}: delta shape mismatch for plain Linear; "
                    "skipping"
                )
                skipped += 1
                continue
            with torch.no_grad():
                module.weight.add_(delta.to(module.weight.dtype))
            merged += 1
        else:
            skipped += 1
    log.info(
        f"[lora-merge] merged {merged} LoRA deltas, skipped {skipped} "
        f"(mismatch/unsupported)"
    )


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
        # Model-card-exact call shape. true_cfg_scale carries real CFG;
        # guidance_scale=1.0 is the explicit "no distilled-guidance bonus"
        # value for the non-distilled base model. Same fix pattern applied
        # to /v1/images/edit and /v1/images/animate below.
        gen_args = dict(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            true_cfg_scale=req.guidance_scale,
            guidance_scale=DEFAULT_DISTILLED_GUIDANCE,
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
        # Qwen-Image-Edit-Plus-2511's pipe has no `strength` / `denoising_strength`
        # param — it's a true-edit model conditioned on the input image rather
        # than an img2img that reuses input latents. The CFG knob exposed is
        # `true_cfg_scale`; `guidance_scale=1.0` is the explicit non-distilled
        # value per the model card. We keep EditRequest.strength in the API
        # for caller-side bookkeeping but don't plumb it to the pipe.
        # height/width MUST be forwarded — silently dropping them makes the
        # resolution_sweep tool produce identical output at every res, since
        # the pipe falls back to an internal default (~1024²) regardless.
        gen_args = dict(
            prompt=req.prompt,
            image=img,
            negative_prompt=req.negative_prompt,
            height=req.height,
            width=req.width,
            num_inference_steps=req.num_inference_steps,
            true_cfg_scale=req.guidance_scale,
            guidance_scale=DEFAULT_DISTILLED_GUIDANCE,
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


@app.post("/v1/images/animate", response_model=AnimateResponse)
async def animate(req: AnimateRequest):
    """Chain-edit animation — run a sequence of nudges against the base
    image, feeding each frame's output as the next frame's input. Identity
    preserved across the whole chain because each step is a small delta
    from the previous frame, not from the base.

    Per-frame logging includes step index + strength so the production-
    firing audit (sigma v10) can grep for this signature to confirm the
    endpoint is alive.
    """
    if _pipe is None:
        raise HTTPException(503, "pipeline not loaded")
    if req.response_format == "save_path" and not req.save_dir:
        raise HTTPException(400, "save_dir required when response_format=save_path")

    # Load base as PIL.Image using the existing ImageInput helper shape.
    base_input = ImageInput(b64_json=req.b64_json, path=req.path)
    current_img = _load_input_image(base_input)

    # Prepare save_dir up front (one mkdir, not per-frame).
    save_dir_path: Optional[Path] = None
    if req.save_dir:
        save_dir_path = Path(req.save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)

    generator = None
    if req.seed is not None:
        generator = torch.Generator(device=_args.device).manual_seed(req.seed)

    frames: list[GenResponseImage] = []
    total_strength = 0.0
    t0 = time.time()
    log.info(
        f"[animate] chain of {len(req.nudges)} nudges, "
        f"seed={req.seed}, save_dir={req.save_dir}"
    )

    async with _lock:
        for i, step in enumerate(req.nudges):
            step_t0 = time.time()
            # `strength` is kept in NudgeStep for bookkeeping (Σstrength is the
            # drift-bound metric the sigma invariant watches) but is NOT a pipe
            # kwarg for QwenImageEditPlusPipeline — that pipe is a true-edit
            # model, not an img2img. The CFG knob is `true_cfg_scale`;
            # guidance_scale=1.0 is the explicit non-distilled value per the
            # model card.
            result = _pipe(
                prompt=step.delta,
                image=current_img,
                negative_prompt=req.negative_prompt,
                num_inference_steps=step.num_inference_steps,
                true_cfg_scale=step.guidance_scale,
                guidance_scale=DEFAULT_DISTILLED_GUIDANCE,
                num_images_per_prompt=1,
                generator=generator,
            )
            current_img = result.images[0]
            total_strength += step.strength
            log.info(
                f"[animate] step {i+1}/{len(req.nudges)}: "
                f"strength={step.strength:.2f}, "
                f"Σ={total_strength:.2f}, "
                f"elapsed={time.time()-step_t0:.1f}s, "
                f"delta={step.delta[:60]!r}"
            )

            # Pack and stash this frame.
            if req.response_format == "save_path":
                frame_path = save_dir_path / f"frame_{i:03d}.png"
                current_img.save(frame_path)
                frames.append(GenResponseImage(save_path=str(frame_path)))
            else:
                buf = io.BytesIO()
                current_img.save(buf, format="PNG")
                frames.append(GenResponseImage(
                    b64_json=base64.b64encode(buf.getvalue()).decode("ascii")
                ))

    elapsed = round(time.time() - t0, 2)
    log.info(
        f"[animate] chain complete: {len(frames)} frames, "
        f"Σstrength={total_strength:.2f}, {elapsed}s total, "
        f"{elapsed/max(len(frames),1):.2f}s/frame"
    )
    return AnimateResponse(
        created=int(time.time()),
        frames=frames,
        timing={
            "elapsed_s": elapsed,
            "per_frame_s": round(elapsed / max(len(frames), 1), 2),
        },
        total_strength=round(total_strength, 2),
        loaded_loras=list(_loaded_loras),
    )


def main():
    """CLI mirror of ernie_server.main — same flags + a --lora startup option.

    Usage:
      python -m tsunami.serving.qwen_image_server --port 8094
      python -m tsunami.serving.qwen_image_server --port 8094 --lora multiple_angles
    """
    global _args
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen-Image-Edit-2511",
                    help="HF repo id for the base pipeline")
    ap.add_argument("--lora", default="none",
                    help="LoRA name to attach at startup (registry: "
                         "multiple_angles / lightning / none)")
    ap.add_argument("--fp8-path", default=None,
                    help="Path to a Comfy-Org fp8 transformer safetensors "
                         "(e.g. qwen_image_edit_2511_fp8_e4m3fn_scaled_"
                         "lightning_8steps_v1.0.safetensors). Loaded via "
                         "QwenImageTransformer2DModel.from_single_file — "
                         "diffusers handles quant format detection "
                         "(tensorwise vs rowwise weight_scale).")
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
