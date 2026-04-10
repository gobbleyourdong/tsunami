"""Ternary quantizer — convert fp16/bf16 weights to {-1, 0, +1}.

BitNet b1.58 approach:
1. Per-group absmean scaling: scale = mean(|W_group|)
2. Normalize: W' = W / scale
3. Round to ternary: {-1, 0, +1} with threshold

The gasket mask identifies which weights lost the most precision
in the ternary representation, for targeted residual correction.

Usage:
    from tsunami.ternary.quantize import quantize_model, TernaryModel
    tmodel = quantize_model("models/gemma-4-31B-it", group_size=128)
    tmodel.save("models/gemma-4-31B-ternary")
"""

from __future__ import annotations

import logging
import math
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn

log = logging.getLogger("tsunami.ternary.quantize")


@dataclass
class QuantStats:
    """Statistics from quantizing one tensor."""
    name: str
    shape: tuple
    sparsity: float      # fraction of zeros
    hole_fraction: float  # fraction of weights in gasket holes
    max_error: float     # max quantization error
    mean_error: float    # mean absolute error


def ternary_quantize_tensor(
    weight: torch.Tensor,
    group_size: int = 128,
    threshold: float = 0.5,
) -> tuple[torch.Tensor, torch.Tensor, QuantStats]:
    """Quantize a weight tensor to ternary {-1, 0, +1}.

    Args:
        weight: fp16/bf16 weight tensor
        group_size: quantize in groups for better precision
        threshold: values below this (after normalization) become 0

    Returns:
        (ternary_weights: int8, scales: fp16, stats)
        ternary_weights are packed as int8 {-1, 0, 1}
        scales are per-group scaling factors
    """
    original_shape = weight.shape
    dtype = weight.dtype
    device = weight.device

    # Flatten to 2D for group quantization
    if weight.ndim == 1:
        weight_2d = weight.unsqueeze(0)
    else:
        weight_2d = weight.reshape(-1, weight.shape[-1])

    rows, cols = weight_2d.shape

    # Pad columns to group_size multiple
    pad = (group_size - cols % group_size) % group_size
    if pad > 0:
        weight_2d = torch.nn.functional.pad(weight_2d, (0, pad))
    padded_cols = weight_2d.shape[1]

    # Reshape into groups
    grouped = weight_2d.reshape(rows, padded_cols // group_size, group_size)

    # Per-group absmean scaling (BitNet b1.58)
    scales = grouped.abs().mean(dim=-1, keepdim=True).clamp(min=1e-8)

    # Normalize
    normalized = grouped / scales

    # Ternary round: {-1, 0, +1}
    # BitNet b1.58 approach: use RoundClip with absmean scaling
    # round(clip(W/scale, -1, 1)) where scale = absmean
    # This means: values > 0.5 → +1, < -0.5 → -1, between → 0
    # But we use a LOWER threshold for better coverage
    ternary = torch.zeros_like(normalized, dtype=torch.int8)
    # Adaptive threshold: use 1/3 of absmean-normalized range
    # This gives ~33% each of {-1, 0, +1} instead of 70% zeros
    adaptive_threshold = 1.0 / 3.0
    ternary[normalized > adaptive_threshold] = 1
    ternary[normalized < -adaptive_threshold] = -1

    # Compute quantization error for gasket mask
    reconstructed = ternary.float() * scales
    error = (grouped.float() - reconstructed).abs()
    mean_error = error.mean().item()
    max_error = error.max().item()

    # Gasket hole detection: weights where error > mean_error
    # These are the positions that need residual correction
    hole_mask = error > error.mean()
    hole_fraction = hole_mask.float().mean().item()

    # Sparsity (fraction of zeros)
    sparsity = (ternary == 0).float().mean().item()

    # Reshape back
    ternary_flat = ternary.reshape(rows, padded_cols)
    if pad > 0:
        ternary_flat = ternary_flat[:, :cols]
    ternary_out = ternary_flat.reshape(original_shape)

    scales_flat = scales.squeeze(-1)  # [rows, n_groups]

    stats = QuantStats(
        name="",
        shape=tuple(original_shape),
        sparsity=sparsity,
        hole_fraction=hole_fraction,
        max_error=max_error,
        mean_error=mean_error,
    )

    return ternary_out, scales_flat, stats


def ternary_matmul(ternary_w: torch.Tensor, x: torch.Tensor, scales: torch.Tensor, group_size: int = 128) -> torch.Tensor:
    """Ternary matrix multiplication — adds and subtracts only.

    For each group:
        y = scale * (sum of x where w=+1) - (sum of x where w=-1)

    This avoids ALL multiplications in the matmul itself.
    The only multiply is the single scale factor per group.
    """
    # For now, use the dequantize-then-matmul path
    # TODO: custom CUDA kernel for true ternary matmul
    out_features = ternary_w.shape[0]
    in_features = ternary_w.shape[1]

    # Reconstruct fp16 weights from ternary + scales
    n_groups = scales.shape[-1]
    pad = (group_size - in_features % group_size) % group_size

    w_padded = ternary_w
    if pad > 0:
        w_padded = torch.nn.functional.pad(ternary_w.float(), (0, pad))

    w_grouped = w_padded.reshape(out_features, n_groups, group_size)
    w_dequant = (w_grouped * scales.unsqueeze(-1)).reshape(out_features, -1)

    if pad > 0:
        w_dequant = w_dequant[:, :in_features]

    return torch.nn.functional.linear(x, w_dequant.to(x.dtype))


class TernaryLinear(nn.Module):
    """Drop-in replacement for nn.Linear using ternary weights."""

    def __init__(self, ternary_w: torch.Tensor, scales: torch.Tensor,
                 bias: torch.Tensor | None, group_size: int = 128):
        super().__init__()
        self.register_buffer('ternary_w', ternary_w)
        self.register_buffer('scales', scales)
        if bias is not None:
            self.register_buffer('bias', bias)
        else:
            self.bias = None
        self.group_size = group_size
        self.out_features = ternary_w.shape[0]
        self.in_features = ternary_w.shape[1]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = ternary_matmul(self.ternary_w, x, self.scales, self.group_size)
        if self.bias is not None:
            out = out + self.bias
        return out

    def extra_repr(self) -> str:
        return f"in={self.in_features}, out={self.out_features}, ternary=True, groups={self.scales.shape[-1]}"


def quantize_linear_layer(layer: nn.Linear, group_size: int = 128) -> TernaryLinear:
    """Replace a nn.Linear with a TernaryLinear."""
    ternary_w, scales, stats = ternary_quantize_tensor(
        layer.weight.data, group_size=group_size
    )
    return TernaryLinear(
        ternary_w=ternary_w,
        scales=scales,
        bias=layer.bias.data if layer.bias is not None else None,
        group_size=group_size,
    )


def quantize_model(
    model_path: str,
    group_size: int = 128,
    skip_layers: list[str] | None = None,
) -> tuple[nn.Module, list[QuantStats]]:
    """Quantize all linear layers in a model to ternary.

    Args:
        model_path: path to HuggingFace model directory
        group_size: quantization group size
        skip_layers: layer name patterns to skip (e.g. ["lm_head", "embed"])

    Returns:
        (quantized_model, list_of_stats)
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    skip_layers = skip_layers or ["embed", "lm_head", "norm"]

    log.info(f"Loading model from {model_path}...")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="cpu",  # quantize on CPU first
        trust_remote_code=True,
    )

    all_stats = []
    replaced = 0
    skipped = 0

    log.info("Quantizing linear layers to ternary...")
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear):
            # Check skip list
            if any(skip in name for skip in skip_layers):
                skipped += 1
                continue

            # Get parent module and attribute name
            parts = name.rsplit(".", 1)
            if len(parts) == 2:
                parent_name, attr_name = parts
                parent = dict(model.named_modules())[parent_name]
            else:
                parent = model
                attr_name = name

            # Quantize
            ternary_layer = quantize_linear_layer(module, group_size)
            setattr(parent, attr_name, ternary_layer)

            stats = QuantStats(
                name=name,
                shape=tuple(module.weight.shape),
                sparsity=(ternary_layer.ternary_w == 0).float().mean().item(),
                hole_fraction=0,  # computed during quantize_tensor
                max_error=0,
                mean_error=0,
            )
            all_stats.append(stats)
            replaced += 1

    log.info(f"Quantized {replaced} layers, skipped {skipped}")

    # Compute model size
    ternary_bytes = sum(
        p.nelement() for n, p in model.named_parameters()
        if 'ternary_w' in n
    ) * 1  # 1 byte per int8, but logically 1.58 bits
    scale_bytes = sum(
        p.nelement() * 2 for n, p in model.named_parameters()
        if 'scales' in n
    )
    other_bytes = sum(
        p.nelement() * p.element_size() for n, p in model.named_parameters()
        if 'ternary_w' not in n and 'scales' not in n
    )

    log.info(f"Ternary weights: {ternary_bytes / 1e9:.2f}GB (int8 storage)")
    log.info(f"Scales: {scale_bytes / 1e9:.2f}GB")
    log.info(f"Other (embed/norm/head): {other_bytes / 1e9:.2f}GB")
    log.info(f"Total: {(ternary_bytes + scale_bytes + other_bytes) / 1e9:.2f}GB")

    return model, all_stats
