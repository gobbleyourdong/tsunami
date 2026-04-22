"""Copy the raw bytes of the three Qwen-Image-Edit fp8 safetensors files
into GPU memory. No parsing, no model construction, no tensors —
literal file contents as a uint8 buffer on GPU.

Each file becomes one 1D torch.uint8 tensor on `--device`. Script
reports resident VRAM after each load + optionally blocks on stdin to
hold the memory for inspection via nvidia-smi / free -h.

Usage:

    python scripts/asset/probe_fp8_fit.py \\
        --transformer /home/jb/.cache/huggingface/hub/manual/qwen_image_edit_2511_fp8_e4m3fn_scaled_lightning_8steps_v1.0.safetensors \\
        --text-encoder /home/jb/.cache/huggingface/hub/manual/qwen_2.5_vl_7b_fp8_scaled.safetensors \\
        --vae /home/jb/.cache/huggingface/hub/manual/qwen_image_vae.safetensors

All three flags optional; pass only the ones you want to test.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import torch

log = logging.getLogger("fp8_probe")


def _report_vram(stage: str) -> None:
    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / (1024**3)
        reserved = torch.cuda.memory_reserved() / (1024**3)
        log.info(f"[{stage}] VRAM allocated={alloc:.2f} GB reserved={reserved:.2f} GB")


def _load_file_bytes_to_gpu(path: Path, device: str) -> torch.Tensor:
    """Raw file → uint8 CUDA tensor. One CPU-side read pass, one H2D
    copy. On unified memory the H2D copy is very cheap; on discrete
    GPU it's a single PCIe/NVLink transfer."""
    size = path.stat().st_size
    log.info(f"[load] {path.name} ({size / (1024**3):.2f} GB)")
    # open in raw binary, read into CPU bytes, view as uint8 tensor,
    # copy to GPU. Plenty of Pythonic approaches; this is simplest.
    with open(path, "rb") as f:
        cpu_tensor = torch.frombuffer(f.read(), dtype=torch.uint8)
    # Move to GPU. On GB10 unified memory this is fast; on discrete
    # GPU it's a PCIe DMA.
    return cpu_tensor.to(device, non_blocking=False)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--transformer", type=Path, default=None)
    p.add_argument("--text-encoder", type=Path, default=None)
    p.add_argument("--vae", type=Path, default=None)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--hold", action="store_true",
                   help="block on stdin after load to keep memory resident")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    kept: dict[str, torch.Tensor] = {}
    _report_vram("start")

    for label, path in (
        ("transformer", args.transformer),
        ("text_encoder", args.text_encoder),
        ("vae", args.vae),
    ):
        if path is None:
            continue
        if not path.is_file():
            log.error(f"file not found: {path}")
            return 2
        t = _load_file_bytes_to_gpu(path, args.device)
        log.info(f"[{label}] on {t.device}: {t.numel() / (1024**3):.2f} GB uint8")
        kept[label] = t
        _report_vram(f"after {label}")

    log.info("--- all files loaded ---")
    _report_vram("final")
    total = sum(t.numel() for t in kept.values()) / (1024**3)
    log.info(f"total bytes resident: {total:.2f} GB across {len(kept)} files")

    if args.hold:
        log.info("blocking on stdin; press enter / ctrl-D to release")
        try:
            input()
        except EOFError:
            pass
        log.info("releasing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
