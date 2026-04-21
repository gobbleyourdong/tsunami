"""Zero-copy safetensors loading for DGX Spark unified memory.

The HuggingFace safetensors library's default load path reads the file
into CPU memory, then PyTorch's `.to(device)` copies every tensor to
GPU — producing a transient 2x-model-size peak. On a discrete-VRAM
machine that's unavoidable; on DGX Spark (Grace-Blackwell GB10, 128 GB
unified memory), it wastes unified memory bandwidth AND doubles the
resident footprint at load time.

`fastsafetensors` (IBM Foundation Model Stack) does DMA-direct load
from NVMe to GPU buffers — one copy, no CPU intermediate. On GB10
this is both faster and half the peak memory.

## API

  sd = load_state_dict_zero_copy("/path/to/weights.safetensors", device="cuda")

Returns a dict[str, Tensor] where every tensor lives on `device`.
Consumable by `model.load_state_dict(sd, strict=False)` — drop-in
replacement for safetensors.torch.load_file + to(device).

Reusable from any model-serving script: qwen_image_server (diffusion
transformer + VAE), serve_qwen36_fp8 (text LLM), ernie_server (image
gen), embed_server (embeddings).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import torch

log = logging.getLogger("tsunami.zero_copy")


def _fastsafetensors_available() -> bool:
    """True if fastsafetensors is importable. Call once, cache result."""
    try:
        import fastsafetensors  # noqa: F401
        return True
    except ImportError:
        return False


_FAST = None  # cached


def load_state_dict_zero_copy(
    path: Union[str, Path],
    device: str = "cuda",
    framework: str = "pt",
    nogds: bool = True,
) -> dict[str, torch.Tensor]:
    """Load a safetensors file with one-copy DMA to `device`.

    Args:
        path: path to a .safetensors file.
        device: target device, e.g. "cuda" or "cuda:0".
        framework: fastsafetensors framework kwarg; "pt" for PyTorch.
        nogds: True to skip GPU Direct Storage (works without GDS support).
            Set False only when GDS is proven present; otherwise fastsafetensors
            will fall through to a pread path that's still faster than stock.

    Returns:
        state_dict: {tensor_name: Tensor} with every tensor on `device`.

    Falls back to safetensors.torch.load_file + .to(device) if
    fastsafetensors isn't installed, so callers don't need to guard."""
    global _FAST
    if _FAST is None:
        _FAST = _fastsafetensors_available()

    if not _FAST:
        log.warning(
            f"[zero-copy] fastsafetensors not installed; falling back to "
            f"safetensors + .to({device}) (2x peak memory). "
            f"Install: pip install fastsafetensors"
        )
        from safetensors.torch import load_file
        sd = load_file(str(path))
        return {k: v.to(device) for k, v in sd.items()}

    from fastsafetensors import fastsafe_open

    path = str(path)
    # fastsafetensors needs a device with explicit index. Normalize "cuda"
    # → "cuda:0"; leave "cuda:N" and "cpu" alone.
    device_norm = device
    if device == "cuda":
        device_norm = "cuda:0"
    log.info(f"[zero-copy] loading {path} → {device_norm} via fastsafetensors")
    device = device_norm
    sd: dict[str, torch.Tensor] = {}
    with fastsafe_open(
        filenames=[path],
        framework=framework,
        device=device,
        nogds=nogds,
    ) as f:
        for k in f.keys():
            # clone().detach() so the returned tensor doesn't share the
            # loader's internal buffer — once the `with` block exits, the
            # loader frees its arena, so we need our own storage.
            sd[k] = f.get_tensor(k).clone().detach()
    log.info(f"[zero-copy] loaded {len(sd)} tensors to {device}")
    return sd


import contextlib


@contextlib.contextmanager
def patch_diffusers_load_state_dict(device: str = "cuda:0"):
    """Temporarily monkey-patch `diffusers.models.model_loading_utils
    .load_state_dict` to use fastsafetensors. This preserves all of
    diffusers' quant-aware module construction (e.g. `from_single_file`
    detects `weight_scale` keys in the safetensors and swaps standard
    Linear layers for QuantLinear subclasses automatically) — we only
    substitute the file-read step with zero-copy DMA.

    The patched load_state_dict keeps the original signature; extra
    kwargs that fastsafetensors doesn't support (`dduf_entries`,
    `disable_mmap`, `map_location`) are silently ignored, but the
    return-type contract (a plain dict of GPU-resident Tensors) is
    preserved.

    Usage:

        with patch_diffusers_load_state_dict(device="cuda:0"):
            model = SomeDiffusersModel.from_single_file(fp8_path, ...)

    Inside the `with` block, any call from diffusers to load a
    .safetensors file routes through fastsafetensors. On exit, the
    original loader is restored.

    Falls through gracefully if fastsafetensors isn't installed —
    diffusers' default loader stays in effect, unchanged.
    """
    if not _fastsafetensors_available():
        log.info("[zero-copy] patch noop — fastsafetensors not installed")
        yield
        return

    import diffusers.models.model_loading_utils as _mlu
    original = _mlu.load_state_dict

    def _patched(checkpoint_file, dduf_entries=None, disable_mmap=False,
                 map_location="cpu"):
        # Only intercept .safetensors; fall through for .ckpt / .gguf / etc.
        if isinstance(checkpoint_file, dict):
            return checkpoint_file
        path_str = str(checkpoint_file)
        if not path_str.endswith(".safetensors") or dduf_entries:
            return original(checkpoint_file, dduf_entries=dduf_entries,
                            disable_mmap=disable_mmap, map_location=map_location)
        return load_state_dict_zero_copy(path_str, device=device)

    _mlu.load_state_dict = _patched
    try:
        yield
    finally:
        _mlu.load_state_dict = original


__all__ = ["load_state_dict_zero_copy", "patch_diffusers_load_state_dict"]
