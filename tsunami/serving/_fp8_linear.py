"""Minimal FP8-scaled `nn.Linear` subclass for diffusers transformers.

Matches the subset of ComfyUI's `mixed_precision_ops.Linear` behavior
that's needed to load Comfy-Org's fp8_e4m3fn safetensors into a stock
diffusers model architecture. Deliberately narrow — no CPU-offload
streams, no memory_management dispatch, no LoRA weight_function hooks
(PEFT wraps this subclass directly since it IS an nn.Linear).

## What this solves

Diffusers v0.38's `QwenImageTransformer2DModel` uses plain
`torch.nn.Linear`. The Comfy-Org fp8 safetensors contain per-tensor or
per-row `weight_scale` keys adjacent to every `weight` key. Stock
nn.Linear has no slot for those scales — they're dropped during
load_state_dict, and the weight tensor gets upcast to bf16 silently,
losing the VRAM win entirely.

`FP8ScaledLinear` adds the scale slot and a load hook that captures it.
Forward is `F.linear(input, weight.to(bf16) * weight_scale, bias)` —
the classic dequant-on-forward pattern. No FP8 tensor-core math (that
needs torch._scaled_mm with strict shape constraints), but the VRAM
drop is the main prize and this is the numerically-cleanest dequant.

## Supported scale shapes

- scalar (per-tensor): weight_scale shape () or (1,)
- per-row: weight_scale shape (out_features, 1), broadcasts over in dim

These cover every Comfy-Org and lightx2v Qwen-Image fp8 variant we've
seen. Block-wise scales (smaller tile grids) aren't handled — would
need a reshape-aware dequant.

## Usage — context manager

The patching helper swaps `torch.nn.Linear = FP8ScaledLinear` inside a
specific module's namespace for the duration of a `with` block, so any
model constructed inside sees our subclass. Scoped narrow so unrelated
diffusers components stay on stock nn.Linear.

    from tsunami.serving._fp8_linear import patch_nn_linear_for_fp8

    with patch_nn_linear_for_fp8("diffusers.models.transformers.transformer_qwenimage"):
        transformer = QwenImageTransformer2DModel.from_single_file(fp8_path, ...)
    # After exit, diffusers.models.transformers.transformer_qwenimage.nn.Linear
    # is restored.
"""
from __future__ import annotations

import contextlib
import importlib
import logging
from typing import Optional

import torch
from torch import nn

log = logging.getLogger("tsunami.fp8_linear")


class FP8ScaledLinear(nn.Linear):
    """nn.Linear drop-in that stores weight as float8_e4m3fn + per-tensor
    or per-row scale.

    Memory: weight at 1 byte/elem (vs 2 for bf16) → ~50% weight VRAM.
    Compute: dequant weight to bf16 at forward, then stock F.linear.

    PEFT/LoRA compatibility: `isinstance(module, nn.Linear) is True`
    because of the subclass relationship, so peft.LoraLayer wraps us
    exactly like any other Linear.
    """

    def __init__(self, in_features: int, out_features: int,
                 bias: bool = True, device=None, dtype=None):
        super().__init__(in_features, out_features, bias=bias,
                         device=device, dtype=dtype)
        # Register an empty scale buffer. _load_from_state_dict will
        # repopulate it with the checkpoint's weight_scale; if the
        # checkpoint has no scale for this Linear, the buffer stays as
        # a scalar 1.0 and the forward is a plain bf16 matmul.
        self.register_buffer("weight_scale",
                             torch.tensor(1.0, dtype=torch.float32),
                             persistent=False)

    def _load_from_state_dict(self, state_dict, prefix, local_metadata,
                              strict, missing_keys, unexpected_keys,
                              error_msgs):
        # Intercept scale keys (not in stock nn.Linear's expected param
        # list) and plant them on our buffer before delegating to
        # nn.Module's default loader. Two naming conventions in the wild:
        #   - Comfy-Org transformer fp8mixed / lightx2v lightning fp8:
        #     `<prefix>weight_scale` (+ optional `weight_scale_2`)
        #   - Comfy-Org Qwen2.5-VL text encoder fp8:
        #     `<prefix>scale_weight` (+ `scale_input` which we discard)
        for key_suffix in ("weight_scale", "scale_weight"):
            k = prefix + key_suffix
            if k in state_dict:
                v = state_dict.pop(k)
                self.weight_scale = v.to(dtype=torch.float32).detach()
                break
        # Some checkpoints also ship a per-Linear input_scale (activation
        # calibration). We don't consume it in the dequant-on-forward
        # path — silently drop to avoid unexpected-key warnings.
        state_dict.pop(prefix + "scale_input", None)
        state_dict.pop(prefix + "input_scale", None)
        super()._load_from_state_dict(
            state_dict, prefix, local_metadata, strict,
            missing_keys, unexpected_keys, error_msgs,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Dequant weight fp8 → bf16, scale, matmul. Per-row scales
        # broadcast over the input dimension automatically because
        # (out, 1) * (out, in) = (out, in).
        w = self.weight
        if w.dtype == torch.float8_e4m3fn:
            w = w.to(torch.bfloat16) * self.weight_scale.to(torch.bfloat16)
        # When weight is already bf16 (e.g. Linear wasn't in the fp8
        # set in the checkpoint, layer loaded as-is), skip scaling.
        return nn.functional.linear(x, w, self.bias)


@contextlib.contextmanager
def patch_nn_linear_for_fp8(module_path: str):
    """Temporarily replace `torch.nn.Linear` inside a given module's
    namespace with `FP8ScaledLinear`.

    Why not patch `torch.nn.Linear` globally? — that would affect every
    model loaded during the patch window, including text encoders and
    VAE that don't have fp8 safetensors. Scoping to the transformer
    module's namespace keeps the blast radius narrow.

    The module must already be imported (we need its `nn` reference
    to rebind). If `module.nn` doesn't exist (some diffusers modules
    use `from torch.nn import Linear` directly instead of
    `import torch.nn as nn`), we also walk the module's __dict__ for
    a bound `Linear` name.
    """
    mod = importlib.import_module(module_path)
    saved: list[tuple[object, str, object]] = []

    # Case 1: `import torch.nn as nn` → mod.nn.Linear
    if hasattr(mod, "nn") and getattr(mod.nn, "Linear", None) is nn.Linear:
        saved.append((mod.nn, "Linear", mod.nn.Linear))
        mod.nn.Linear = FP8ScaledLinear

    # Case 2: `from torch.nn import Linear` → mod.Linear
    if getattr(mod, "Linear", None) is nn.Linear:
        saved.append((mod, "Linear", mod.Linear))
        mod.Linear = FP8ScaledLinear

    if not saved:
        log.warning(
            f"[fp8-linear] neither `nn.Linear` nor bare `Linear` found in "
            f"{module_path} namespace — patch did nothing"
        )

    try:
        log.info(
            f"[fp8-linear] patched {len(saved)} Linear ref(s) in {module_path}"
        )
        yield
    finally:
        for owner, name, original in saved:
            setattr(owner, name, original)


def load_fp8_text_encoder(
    fp8_path: str,
    config_repo: str = "Qwen/Qwen-Image-Edit-2511",
    config_subfolder: str = "text_encoder",
    device: str = "cuda:0",
):
    """Load a Comfy-Org fp8-quantized Qwen2_5_VL text encoder without
    any bf16 scaffold materialization.

    Pattern (mirrors ComfyUI's DGXSparkSafetensorsLoader):
      1. Fetch config from hub (no weights).
      2. init_empty_weights() → meta-init the model. Zero memory.
      3. patch_nn_linear_for_fp8 so every Linear becomes FP8ScaledLinear.
      4. fastsafetensors → fp8 state_dict on GPU (one DMA copy).
      5. Normalize ComfyUI scale-key convention → our weight_scale.
      6. load_state_dict(..., strict=False, assign=True) — replaces
         every meta tensor with its fp8 file equivalent.

    This works because the Comfy-Org fp8 safetensors contains ALL
    params the model needs (embeds bf16, layernorms bf16, Linear
    weights fp8, biases bf16, per-Linear scales fp32). The hub's
    bf16 weights are never downloaded or instantiated.

    Args:
        fp8_path: path to qwen_2.5_vl_7b_fp8_scaled.safetensors.
        config_repo: HF repo id for the text_encoder config.
        config_subfolder: subfolder inside the repo containing config.json.
        device: target device for the fp8 tensors + meta-init replacement.

    Returns:
        Qwen2_5_VLForConditionalGeneration with fp8 Linear weights +
        bf16 embeds/norms, fully populated, on `device`.

    Raises if any meta tensors remain after load (missing params in
    the fp8 file that the model's forward would need).
    """
    import accelerate
    from transformers import AutoConfig, Qwen2_5_VLForConditionalGeneration
    from tsunami.serving._zero_copy import load_state_dict_zero_copy

    log.info(f"[fp8-te] fetching config from {config_repo}/{config_subfolder}")
    config = AutoConfig.from_pretrained(config_repo, subfolder=config_subfolder)

    log.info(f"[fp8-te] meta-init model from config")
    with accelerate.init_empty_weights(), patch_nn_linear_for_fp8(
        "transformers.models.qwen2_5_vl.modeling_qwen2_5_vl"
    ):
        model = Qwen2_5_VLForConditionalGeneration(config)

    log.info(f"[fp8-te] streaming fp8 state_dict → {device}")
    fp8_sd = load_state_dict_zero_copy(fp8_path, device=device)

    # Normalize ComfyUI's scale-key naming. Our FP8ScaledLinear's
    # _load_from_state_dict already accepts both `weight_scale` and
    # `scale_weight`; we still strip the sentinel + input scales here
    # since they'd show up as unexpected keys.
    normalized = {}
    sentinels_dropped = 0
    for k, v in fp8_sd.items():
        if k == "scaled_fp8":
            sentinels_dropped += 1
            continue
        if k.endswith(".scale_input"):
            sentinels_dropped += 1  # activation-calibration, unused
            continue
        normalized[k] = v

    log.info(
        f"[fp8-te] state_dict: {len(normalized)} keys (dropped "
        f"{sentinels_dropped} sentinel/input-scale keys)"
    )

    missing, unexpected = model.load_state_dict(
        normalized, strict=False, assign=True
    )

    # Sanity: ensure no tensors remain on meta. If any do, the fp8 file
    # didn't cover them — we can't `.to(cuda)` a partially-meta model.
    still_meta = [
        n for n, p in model.named_parameters() if p.is_meta
    ] + [
        n for n, b in model.named_buffers() if b.is_meta
    ]
    if still_meta:
        raise RuntimeError(
            f"[fp8-te] {len(still_meta)} params/buffers still on meta "
            f"after fp8 load; model can't move to {device}. "
            f"First 5: {still_meta[:5]}"
        )

    log.info(
        f"[fp8-te] loaded (missing={len(missing)}, unexpected={len(unexpected)})"
    )
    return model


__all__ = [
    "FP8ScaledLinear",
    "patch_nn_linear_for_fp8",
    "load_fp8_text_encoder",
]
