"""Calibrated ternary quantization — GPTQ-style output-aware rounding.

The naive approach (round-to-nearest ternary) produces garbage because it
minimizes WEIGHT error, not OUTPUT error. GPTQ showed that optimal quantization
should minimize: ||Wx - Q(W)x||^2 where x is calibration data.

This module:
1. Runs calibration data through the model to capture layer activations
2. For each linear layer, solves for optimal ternary weights that minimize
   output error given the actual input distribution
3. Uses the Hessian diagonal (x^T x) to weight-scale the rounding decisions

The key insight: weights that multiply by large activations need more precision
than weights that multiply by near-zero activations. GPTQ-style rounding
respects this; naive rounding doesn't.

For the gasket residual: the calibration also identifies WHICH outputs have
the highest remaining error — these are the gasket holes.
"""

from __future__ import annotations

import logging
import time
import torch
import torch.nn as nn
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("tsunami.ternary.calibrated_quantize")


@dataclass
class CalibrationStats:
    """Stats from calibrating one layer."""
    name: str
    output_error_before: float  # MSE of naive ternary vs fp16
    output_error_after: float   # MSE of calibrated ternary vs fp16
    improvement: float          # ratio
    sparsity: float


def collect_activations(
    model,
    tokenizer,
    calibration_texts: list[str],
    target_layers: list[str],
    max_samples: int = 32,
) -> dict[str, list[torch.Tensor]]:
    """Run calibration data through the model and capture layer inputs.

    Returns {layer_name: [input_tensor_1, input_tensor_2, ...]}.
    """
    activations: dict[str, list[torch.Tensor]] = {name: [] for name in target_layers}
    hooks = []

    def make_hook(name):
        def hook_fn(module, input, output):
            if isinstance(input, tuple):
                activations[name].append(input[0].detach().cpu())
            else:
                activations[name].append(input.detach().cpu())
        return hook_fn

    # Register hooks
    for name, module in model.named_modules():
        if name in target_layers:
            hooks.append(module.register_forward_hook(make_hook(name)))

    # Run calibration data
    model_device = next(model.parameters()).device
    for i, text in enumerate(calibration_texts[:max_samples]):
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(model_device) for k, v in inputs.items()}
        with torch.no_grad():
            model(**inputs)
        if (i + 1) % 8 == 0:
            log.info(f"Calibration: {i+1}/{min(len(calibration_texts), max_samples)}")

    # Remove hooks
    for h in hooks:
        h.remove()

    return activations


def calibrated_ternary_quantize(
    weight: torch.Tensor,
    activations: list[torch.Tensor],
    group_size: int = 128,
) -> tuple[torch.Tensor, torch.Tensor, CalibrationStats]:
    """Quantize a weight matrix to ternary using calibration data.

    Instead of naive round(W/scale), we solve:
        minimize ||Wx - Qx||^2
    where Q is ternary and x are real activations.

    Uses the diagonal Hessian approximation:
        H_ii = sum(x_i^2) across calibration samples
    Weights multiplied by large activations get priority for non-zero assignment.
    """
    W = weight.float()
    out_features, in_features = W.shape

    # Compute Hessian diagonal from activations
    H_diag = torch.zeros(in_features)
    n_samples = 0
    for act in activations:
        # act shape: [batch, seq_len, in_features] or [batch, in_features]
        flat = act.reshape(-1, in_features).float()
        H_diag += (flat * flat).sum(dim=0)
        n_samples += flat.shape[0]

    if n_samples > 0:
        H_diag /= n_samples
    H_diag = H_diag.clamp(min=1e-8)

    # Per-group quantization with Hessian-weighted rounding
    pad = (group_size - in_features % group_size) % group_size
    if pad > 0:
        W_padded = nn.functional.pad(W, (0, pad))
        H_padded = nn.functional.pad(H_diag, (0, pad))
    else:
        W_padded = W
        H_padded = H_diag

    n_groups = W_padded.shape[1] // group_size
    W_grouped = W_padded.reshape(out_features, n_groups, group_size)
    H_grouped = H_padded.reshape(n_groups, group_size)

    # Per-group scales
    scales = W_grouped.abs().mean(dim=-1, keepdim=True).clamp(min=1e-8)
    W_norm = W_grouped / scales

    # Hessian-weighted ternary assignment
    # Priority score: |w_normalized| * sqrt(H_ii)
    # Higher priority → more likely to be non-zero
    importance = W_norm.abs() * H_grouped.unsqueeze(0).sqrt()

    # Adaptive threshold based on importance
    # Top 2/3 of weights by importance get non-zero assignment
    flat_importance = importance.reshape(-1)
    if flat_importance.numel() > 0:
        threshold = flat_importance.quantile(0.33).item()
    else:
        threshold = 0.0

    # Assign ternary values
    ternary = torch.zeros_like(W_norm, dtype=torch.int8)
    mask = importance > threshold
    ternary[mask & (W_norm > 0)] = 1
    ternary[mask & (W_norm < 0)] = -1

    # Compute output error
    W_recon = (ternary.float() * scales).reshape(out_features, -1)
    if pad > 0:
        W_recon = W_recon[:, :in_features]

    # Sample error on calibation data
    error_before = 0.0
    error_after = 0.0
    for act in activations[:4]:
        flat = act.reshape(-1, in_features).float()
        true_out = flat @ W.T
        naive_scale = W.abs().mean()
        naive_ternary = torch.zeros_like(W, dtype=torch.int8)
        naive_ternary[W > naive_scale / 3] = 1
        naive_ternary[W < -naive_scale / 3] = -1
        naive_out = flat @ (naive_ternary.float() * naive_scale).T
        calib_out = flat @ W_recon.T

        error_before += (true_out - naive_out).pow(2).mean().item()
        error_after += (true_out - calib_out).pow(2).mean().item()

    n = max(len(activations[:4]), 1)
    error_before /= n
    error_after /= n
    improvement = error_before / max(error_after, 1e-10)

    # Reshape output
    ternary_flat = ternary.reshape(out_features, -1)
    if pad > 0:
        ternary_flat = ternary_flat[:, :in_features]

    scales_out = scales.squeeze(-1)
    sparsity = (ternary_flat == 0).float().mean().item()

    stats = CalibrationStats(
        name="",
        output_error_before=error_before,
        output_error_after=error_after,
        improvement=improvement,
        sparsity=sparsity,
    )

    return ternary_flat, scales_out, stats


# Default calibration texts (Tsunami-relevant prompts)
DEFAULT_CALIBRATION = [
    "Build a React counter component with increment and decrement buttons using useState.",
    "Write a TypeScript interface for a User with name, email, and optional avatar fields.",
    "Create a dashboard layout with a sidebar navigation and main content area.",
    "Implement a search function that filters an array of objects by a query string.",
    "Build a weather app that displays temperature, humidity, and a 5-day forecast chart.",
    "Write CSS for a dark theme with glassmorphism cards and a blue accent color.",
    "Create a REST API endpoint that handles CRUD operations for a todo list.",
    "Implement drag and drop functionality for a kanban board with multiple columns.",
    "Build a form with validation for email, password, and confirm password fields.",
    "Write a custom React hook called useLocalStorage that persists state.",
    "Create a responsive navigation bar that collapses into a hamburger menu on mobile.",
    "Implement a modal dialog component with backdrop click to close and escape key.",
    "Build a data table with sorting, filtering, and pagination.",
    "Write a WebSocket client that reconnects automatically on disconnect.",
    "Create an audio player component with play, pause, volume, and progress bar.",
    "Implement a color picker with hex input, RGB sliders, and a preview swatch.",
    "Build a markdown editor with live preview side by side.",
    "Write a function that converts CSV text into a sorted HTML table.",
    "Create a timer component with start, stop, reset, and lap functionality.",
    "Implement an infinite scroll list that loads more items when reaching the bottom.",
    "Build a chart component using SVG that displays bar, line, and pie charts.",
    "Write a state management solution using React context and useReducer.",
    "Create a file upload component with drag and drop, progress bar, and preview.",
    "Implement a toast notification system with auto-dismiss and stacking.",
    "Build a quiz game with multiple choice questions, score tracking, and timer.",
    "Write a TreeView component that renders nested data with expand/collapse.",
    "Create a calendar component with month navigation, event markers, and date selection.",
    "Implement keyboard shortcuts for an application with a command palette.",
    "Build a multi-step wizard form with validation at each step.",
    "Write a real-time collaborative text editor simulation with cursor positions.",
    "Create a photo gallery with masonry layout, lightbox, and category filters.",
    "Implement a virtual scrolling list that renders only visible items for performance.",
]
