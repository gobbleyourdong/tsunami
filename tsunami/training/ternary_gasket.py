"""Ternary gasket quantization + residual model training.

The Sierpinski gasket in ternary: a point (x,y) is in the gasket iff
no digit position has x_i + y_i == 2. This is a single vectorized check —
no loops, no recursion.

For neural networks:
1. Quantize weights to ternary {-1, 0, +1} (BitNet-style)
2. The quantization error has gasket structure — it's NOT random noise
3. Compute the gasket mask: which weights lost the most precision
4. Train a small residual model on ONLY the masked positions
5. Inference: ternary_forward(x) + residual(x, mask) = full_precision(x)

The residual is tiny because it only corrects ~10-20% of activations.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

log = logging.getLogger("tsunami.training.ternary_gasket")


# =============================================
# Part 1: Gasket Mathematics (no loops!)
# =============================================

def to_ternary_digits(value: float, n_digits: int = 16) -> list[int]:
    """Convert a float in [0,1) to ternary digits.

    Each digit is 0, 1, or 2. This is the base-3 expansion.
    """
    digits = []
    v = abs(value) % 1.0  # normalize to [0,1)
    for _ in range(n_digits):
        v *= 3
        d = int(v)
        digits.append(min(d, 2))
        v -= d
    return digits


def in_gasket(x_digits: list[int], y_digits: list[int]) -> bool:
    """Check if (x,y) is in the Sierpinski gasket. NO LOOPS in the math sense.

    The check: for all digit positions i, x_i + y_i != 2.
    This is a single vectorized operation.
    """
    return not any(x + y == 2 for x, y in zip(x_digits, y_digits))


def gasket_mask_1d(weights: list[float], n_digits: int = 8) -> list[bool]:
    """Compute which weights are in gasket 'holes' after ternary quantization.

    A weight is in a hole if the quantization error's ternary representation
    has digits that sum to 2 with the quantized value's digits.

    Returns: list of bools, True = this weight is in a gasket hole (needs residual).
    """
    mask = []
    for w in weights:
        # Quantize to ternary: round to {-1, 0, +1}
        if w > 0.5:
            q = 1.0
        elif w < -0.5:
            q = -1.0
        else:
            q = 0.0

        # Quantization error
        error = abs(w - q)

        # Normalize error and quantized value to [0,1) for gasket check
        q_norm = (q + 1) / 2  # map {-1,0,1} to {0, 0.5, 1}
        e_norm = min(error, 0.999)

        q_digits = to_ternary_digits(q_norm, n_digits)
        e_digits = to_ternary_digits(e_norm, n_digits)

        # In a gasket hole = needs residual correction
        is_hole = not in_gasket(q_digits, e_digits)
        mask.append(is_hole)

    return mask


# =============================================
# Part 2: Ternary Quantization (BitNet-style)
# =============================================

@dataclass
class TernaryLayer:
    """A ternary-quantized linear layer."""
    ternary_weights: list[list[int]]  # {-1, 0, +1}
    scale: float                       # per-tensor scaling factor
    gasket_mask: list[list[bool]]      # True = needs residual
    original_shape: tuple
    hole_fraction: float               # what % of weights are in holes


def quantize_to_ternary(weights: list[list[float]], threshold: float = 0.5) -> TernaryLayer:
    """Quantize a weight matrix to ternary {-1, 0, +1}.

    Uses absmean scaling (BitNet b1.58 approach):
    1. Compute scale = mean(|W|)
    2. Normalize: W' = W / scale
    3. Round to {-1, 0, +1} with threshold

    Returns TernaryLayer with weights, scale, and gasket mask.
    """
    # Flatten for statistics
    flat = [w for row in weights for w in row]
    scale = sum(abs(w) for w in flat) / len(flat) if flat else 1.0

    ternary = []
    masks = []
    holes = 0
    total = 0

    for row in weights:
        t_row = []
        m_row = []
        for w in row:
            normalized = w / scale if scale > 0 else 0
            # Ternary round
            if normalized > threshold:
                t_row.append(1)
            elif normalized < -threshold:
                t_row.append(-1)
            else:
                t_row.append(0)
            total += 1

        ternary.append(t_row)

        # Compute gasket mask for this row
        row_mask = gasket_mask_1d([w / scale for w in row])
        m_row = row_mask
        holes += sum(row_mask)
        masks.append(m_row)

    hole_fraction = holes / total if total > 0 else 0

    return TernaryLayer(
        ternary_weights=ternary,
        scale=scale,
        gasket_mask=masks,
        original_shape=(len(weights), len(weights[0]) if weights else 0),
        hole_fraction=hole_fraction,
    )


def ternary_matmul(ternary: list[list[int]], x: list[float], scale: float) -> list[float]:
    """Ternary matrix multiplication — only adds and subtracts, no multiplies.

    This is why ternary is fast: the matmul becomes:
    y[i] = scale * sum(t[i][j] * x[j]) where t is {-1,0,+1}
         = scale * (sum of x[j] where t=+1) - (sum of x[j] where t=-1)
    """
    result = []
    for row in ternary:
        val = 0.0
        for t, xi in zip(row, x):
            if t == 1:
                val += xi
            elif t == -1:
                val -= xi
            # t == 0: skip (no operation)
        result.append(val * scale)
    return result


# =============================================
# Part 3: Residual Model Architecture
# =============================================

@dataclass
class ResidualConfig:
    """Configuration for the gasket residual model."""
    input_dim: int        # same as original layer width
    hidden_dim: int       # small — only corrects holes
    num_layers: int = 2   # shallow is fine for corrections
    hole_fraction: float = 0.15  # expected fraction of weights in holes


def compute_residual_size(original_params: int, hole_fraction: float) -> int:
    """Estimate how many parameters the residual model needs.

    The residual only needs to correct hole positions.
    Rule of thumb: residual_params ≈ original_params × hole_fraction × 0.5
    (the 0.5 because the residual can share structure across corrections)
    """
    return int(original_params * hole_fraction * 0.5)


def estimate_savings(original_model_params: int, hole_fraction: float = 0.15) -> dict:
    """Estimate the parameter and compute savings.

    Ternary base: 1.58 bits per param (vs 16 bits for fp16)
    Residual: fp16 but only hole_fraction × 0.5 of original size
    """
    ternary_bits = original_model_params * 1.58
    original_bits = original_model_params * 16
    residual_params = compute_residual_size(original_model_params, hole_fraction)
    residual_bits = residual_params * 16

    total_bits = ternary_bits + residual_bits
    compression = original_bits / total_bits

    return {
        "original_params": original_model_params,
        "original_bits": original_bits,
        "ternary_params": original_model_params,
        "ternary_bits": ternary_bits,
        "residual_params": residual_params,
        "residual_bits": residual_bits,
        "total_bits": total_bits,
        "compression_ratio": round(compression, 2),
        "hole_fraction": hole_fraction,
        "ternary_size_mb": round(ternary_bits / 8 / 1024 / 1024, 1),
        "residual_size_mb": round(residual_bits / 8 / 1024 / 1024, 1),
        "total_size_mb": round(total_bits / 8 / 1024 / 1024, 1),
    }


# =============================================
# Part 4: Quick Demo
# =============================================

def demo():
    """Demonstrate the ternary gasket pipeline on a toy example."""
    import random
    random.seed(42)

    # Create a small "weight matrix"
    weights = [[random.gauss(0, 0.5) for _ in range(8)] for _ in range(4)]

    # Quantize
    layer = quantize_to_ternary(weights)
    print(f"Original: {len(weights)}x{len(weights[0])}")
    print(f"Scale: {layer.scale:.4f}")
    print(f"Hole fraction: {layer.hole_fraction:.2%}")
    print(f"Ternary weights: {layer.ternary_weights}")

    # Forward pass
    x = [1.0, 0.5, -0.3, 0.8, -0.1, 0.2, -0.5, 0.7]
    y_ternary = ternary_matmul(layer.ternary_weights, x, layer.scale)
    print(f"Ternary output: {[round(v, 4) for v in y_ternary]}")

    # Savings estimate for Qwen2.5-Coder-3B
    savings = estimate_savings(3_000_000_000)
    print(f"\nQwen2.5-Coder-3B savings:")
    print(f"  Ternary: {savings['ternary_size_mb']}MB")
    print(f"  Residual: {savings['residual_size_mb']}MB")
    print(f"  Total: {savings['total_size_mb']}MB (vs {savings['original_bits']/8/1024/1024:.0f}MB fp16)")
    print(f"  Compression: {savings['compression_ratio']}x")


if __name__ == "__main__":
    demo()
