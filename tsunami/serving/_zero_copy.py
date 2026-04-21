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
    log.info(f"[zero-copy] loading {path} → {device} via fastsafetensors")
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


__all__ = ["load_state_dict_zero_copy"]
