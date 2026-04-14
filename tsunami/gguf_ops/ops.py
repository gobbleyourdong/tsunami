"""GGML-backed torch ops — holds quantized GGUF tensors, dequantizes lazily
on forward pass. Adapted from city96/ComfyUI-GGUF (Apache-2.0) but stripped
of comfy.ops / comfy.lora / comfy.model_management dependencies so it drops
into a plain transformers / diffusers pipeline.

Core idea: override `nn.Linear` (and optionally `nn.Embedding`) so the weight
is a GGMLTensor (quantized storage). On each forward, dequantize to the
input's dtype, run the matmul, let the dequantized copy fall out of scope.

Peak VRAM = (quantized storage always resident) + (ONE layer's dequantized
weights during its forward). For a 6B DiT at Q4_K_M that's ~5GB always +
a few hundred MB working set — vs 12GB fully-resident bf16.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import gguf

from .dequant import dequantize_tensor, is_quantized, TORCH_COMPATIBLE_QTYPES


class GGMLTensor(torch.Tensor):
    """Torch tensor subclass that carries the GGUF quant type + original
    logical shape. `.data` holds the raw quantized bytes (as uint8); the
    logical shape is what the tensor "looks like" after dequantization.
    """
    def __init__(self, *args, tensor_type, tensor_shape, **kwargs):
        super().__init__()
        self.tensor_type = tensor_type
        self.tensor_shape = tensor_shape

    def __new__(cls, *args, tensor_type, tensor_shape, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def to(self, *args, **kwargs):
        new = super().to(*args, **kwargs)
        new.tensor_type = getattr(self, "tensor_type", None)
        new.tensor_shape = getattr(self, "tensor_shape", new.data.shape)
        return new

    def clone(self, *args, **kwargs):
        return self

    def detach(self, *args, **kwargs):
        return self

    @property
    def shape(self):
        if not hasattr(self, "tensor_shape"):
            self.tensor_shape = self.size()
        return self.tensor_shape


def _dequant_if_needed(tensor: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    """Dequantize a GGMLTensor to `dtype`, or pass through a regular tensor."""
    if isinstance(tensor, GGMLTensor) or getattr(tensor, "tensor_type", None) not in TORCH_COMPATIBLE_QTYPES:
        return dequantize_tensor(tensor, dtype=dtype)
    return tensor.to(dtype)


class _GGMLLoadMixin:
    """Shared state-dict load override. Quantized GGMLTensors are uint8-backed,
    which trips nn.Parameter's float-only requires_grad default check — bypass
    the normal copy_ path (which also validates dtype/shape) and assign directly
    as a non-grad Parameter. This is what ComfyUI-GGUF does too."""
    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict,
                              missing_keys, unexpected_keys, error_msgs):
        wk, bk = f"{prefix}weight", f"{prefix}bias"
        if wk in state_dict:
            v = state_dict[wk]
            self.weight = nn.Parameter(v, requires_grad=False)
        elif strict:
            missing_keys.append(wk)
        if bk in state_dict:
            v = state_dict[bk]
            self.bias = nn.Parameter(v, requires_grad=False)
        elif getattr(self, "bias", None) is not None and strict:
            missing_keys.append(bk)


class GGMLLinear(_GGMLLoadMixin, nn.Linear):
    """nn.Linear that stores weight as a GGMLTensor and dequantizes
    per-forward. Benchmarked caching bf16 across forwards: peak memory
    4x-ed for only ~10% speed win — the dequant isn't the bottleneck on
    GB10 Blackwell, the matmul + attention is. Keep it simple: dequant
    every forward, let the allocator free the bf16 copy after."""
    def forward(self, input: torch.Tensor) -> torch.Tensor:
        w = _dequant_if_needed(self.weight, input.dtype)
        if w.device != input.device:
            w = w.to(input.device)
        b = None
        if self.bias is not None:
            b = _dequant_if_needed(self.bias, input.dtype)
            if b.device != input.device:
                b = b.to(input.device)
        return F.linear(input, w, b)


class GGMLEmbedding(_GGMLLoadMixin, nn.Embedding):
    """nn.Embedding with dequant-on-forward. Most GGUFs keep token_embd at
    F16/F32 so this usually passes through — but when it IS quantized
    (rare), we'd otherwise crash in the gather."""
    def forward(self, input: torch.Tensor) -> torch.Tensor:
        target_dtype = torch.get_default_dtype()
        w = _dequant_if_needed(self.weight, target_dtype)
        return F.embedding(
            input, w, self.padding_idx, self.max_norm, self.norm_type,
            self.scale_grad_by_freq, self.sparse,
        )


def replace_linear_with_ggml(module: nn.Module) -> int:
    """Recursively replace every nn.Linear in `module` with GGMLLinear,
    preserving (in_features, out_features, bias). Returns the number of
    layers replaced.

    Call this BEFORE load_state_dict — the replacements keep the same
    attribute structure so a GGUF state dict lines up exactly.
    """
    n = 0
    for name, child in module.named_children():
        if isinstance(child, nn.Linear) and not isinstance(child, GGMLLinear):
            new_layer = GGMLLinear(
                child.in_features, child.out_features,
                bias=child.bias is not None,
                device="meta",  # don't allocate weights — the state dict will
                dtype=child.weight.dtype,
            )
            setattr(module, name, new_layer)
            n += 1
        elif isinstance(child, nn.Embedding) and not isinstance(child, GGMLEmbedding):
            new_emb = GGMLEmbedding(
                child.num_embeddings, child.embedding_dim,
                padding_idx=child.padding_idx,
                max_norm=child.max_norm, norm_type=child.norm_type,
                scale_grad_by_freq=child.scale_grad_by_freq,
                sparse=child.sparse,
                device="meta",
                dtype=child.weight.dtype,
            )
            setattr(module, name, new_emb)
            n += 1
        else:
            n += replace_linear_with_ggml(child)
    return n
