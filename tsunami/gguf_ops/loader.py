"""GGUF file → HF-style state_dict of GGMLTensors, plus arch-specific remaps.

Port of the relevant pieces of city96/ComfyUI-GGUF loader.py (Apache-2.0).
Supports:
  - qwen3    → Qwen3Model  (Z-Image text encoder, standalone)
  - lumina2  → Z-Image DiT  (native GGUF naming preserved)
  - gemma3   → Gemma3ForCausalLM  (via the GEMMA3_SD_MAP)
  - gemma4   → HAS EXTRA TENSORS not handled yet — see GEMMA4_EXTRA

Flow: load_*_gguf(path, ...) → dict[str, GGMLTensor] with HF-style keys,
already permuted/corrected for the target architecture. Caller feeds it
into load_state_dict() on a model whose Linear layers have been swapped
for GGMLLinear (see ops.replace_linear_with_ggml).
"""
from __future__ import annotations

import logging
import warnings
from pathlib import Path

import gguf
import torch

from .ops import GGMLTensor
from .dequant import dequantize_tensor, is_quantized

log = logging.getLogger("tsunami.gguf_ops")


# ───────────────── Arch → HF tensor-name remaps ───────────────────────────

LLAMA_SD_MAP = {
    "blk.": "model.layers.",
    "attn_norm": "input_layernorm",
    "attn_q_norm.": "self_attn.q_norm.",
    "attn_k_norm.": "self_attn.k_norm.",
    "attn_v_norm.": "self_attn.v_norm.",
    "attn_q": "self_attn.q_proj",
    "attn_k": "self_attn.k_proj",
    "attn_v": "self_attn.v_proj",
    "attn_output": "self_attn.o_proj",
    "ffn_up": "mlp.up_proj",
    "ffn_down": "mlp.down_proj",
    "ffn_gate": "mlp.gate_proj",
    "ffn_norm": "post_attention_layernorm",
    "token_embd": "model.embed_tokens",
    "output_norm": "model.norm",
    "output.weight": "lm_head.weight",
}

GEMMA3_SD_MAP = {
    **LLAMA_SD_MAP,
    "ffn_norm": "pre_feedforward_layernorm",
    "post_ffw_norm": "post_feedforward_layernorm",
    "post_attention_norm": "post_attention_layernorm",
}

QWEN3_SD_MAP = dict(LLAMA_SD_MAP)

# Gemma-4 has extra tensors that Gemma-3 doesn't. Without HF-side naming
# verified against transformers.Gemma4ForCausalLM, do NOT auto-remap these
# yet — the model load will fail with unused keys, which is a cleaner
# signal than silently misnaming a tensor.
GEMMA4_EXTRA_TENSORS = frozenset({
    "per_layer_model_proj.weight",
    "per_layer_proj_norm.weight",
    "per_layer_token_embd.weight",
    "rope_freqs.weight",
    # Per-layer Gemma-4 additions:
    ".inp_gate.weight",
    ".layer_output_scale.weight",
    ".post_attention_norm.weight",
    ".post_ffw_norm.weight",
    ".post_norm.weight",
    ".proj.weight",
})


def _sd_map_replace(sd: dict, key_map: dict) -> dict:
    out = {}
    for k, v in sd.items():
        new_k = k
        for src, dst in key_map.items():
            new_k = new_k.replace(src, dst)
        out[new_k] = v
    return out


def _llama_permute(sd: dict, n_head: int, n_head_kv: int) -> dict:
    """Reverse llama.cpp's Q/K rotary permute so HF rotary application works."""
    def permute(t: torch.Tensor, h: int) -> torch.Tensor:
        return (
            t.reshape(h, t.shape[0] // h // 2, 2, *t.shape[1:])
             .swapaxes(1, 2)
             .reshape(t.shape)
        )
    for k, v in list(sd.items()):
        if k.endswith(("q_proj.weight", "q_proj.bias")):
            v.data = permute(v.data, n_head)
        elif k.endswith(("k_proj.weight", "k_proj.bias")):
            v.data = permute(v.data, n_head_kv)
    return sd


def _gemma3_norm_corrections(sd: dict) -> dict:
    """Gemma stores norm weights with +1 baked in. Reverse by subtracting 1."""
    patterns = (
        "input_layernorm.weight",
        "post_attention_layernorm.weight",
        "pre_feedforward_layernorm.weight",
        "post_feedforward_layernorm.weight",
        "self_attn.q_norm.weight",
        "self_attn.k_norm.weight",
        "model.norm.weight",
    )
    for k in list(sd.keys()):
        if any(p in k for p in patterns):
            v = sd[k]
            if is_quantized(v):
                sd[k] = dequantize_tensor(v, dtype=torch.float32) - 1.0
            else:
                sd[k] = v.float() - 1.0
    return sd


# ───────────────── GGUF reader → raw state_dict ────────────────────────────

def _load_raw_gguf(path: str | Path, handle_prefix: str | None = None) -> tuple[dict, str, dict]:
    reader = gguf.GGUFReader(str(Path(path).expanduser()))
    arch = _get_field(reader, "general.architecture", str) or "unknown"

    prefix_len = len(handle_prefix) if handle_prefix else 0
    has_prefix = handle_prefix and any(t.name.startswith(handle_prefix) for t in reader.tensors)

    state_dict: dict[str, GGMLTensor] = {}
    qtype_hist: dict[str, int] = {}

    for t in reader.tensors:
        sd_key = t.name
        if has_prefix:
            if not sd_key.startswith(handle_prefix):
                continue
            sd_key = sd_key[prefix_len:]

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="The given NumPy array is not writable")
            raw = torch.from_numpy(t.data)
        shape = torch.Size(tuple(int(d) for d in reversed(t.shape)))

        if t.tensor_type in (gguf.GGMLQuantizationType.F32, gguf.GGMLQuantizationType.F16):
            raw = raw.view(*shape)

        tensor = GGMLTensor(raw, tensor_type=t.tensor_type, tensor_shape=shape)

        if len(shape) <= 1 and t.tensor_type == gguf.GGMLQuantizationType.BF16:
            tensor = dequantize_tensor(tensor, dtype=torch.float32)

        state_dict[sd_key] = tensor

        name = getattr(t.tensor_type, "name", repr(t.tensor_type))
        qtype_hist[name] = qtype_hist.get(name, 0) + 1

    log.info(f"GGUF {Path(path).name}: arch={arch}, {len(state_dict)} tensors, qtypes={qtype_hist}")
    return state_dict, arch, {"qtype_histogram": qtype_hist}


def _get_field(reader, name: str, field_type):
    f = reader.get_field(name)
    if f is None:
        return None
    if field_type == str and len(f.types) == 1 and f.types[0] == gguf.GGUFValueType.STRING:
        return str(f.parts[f.data[-1]], encoding="utf-8")
    if field_type in (int, float, bool) and len(f.types) == 1:
        return field_type(f.parts[f.data[-1]].item())
    return None


# ───────────────── Public: arch-specific load-to-HF ───────────────────────

def load_qwen3_gguf(
    path: str | Path,
    n_head: int,
    n_head_kv: int,
    as_base_model: bool = False,
) -> dict[str, GGMLTensor]:
    """Load Qwen3 GGUF → HF state dict.

    as_base_model=False (default): keys prefixed with 'model.' for the
    Qwen3ForCausalLM wrapper class (model.embed_tokens, model.layers.N.*).

    as_base_model=True: keys without 'model.' prefix for standalone
    Qwen3Model (used as the Z-Image text encoder — there's no LM head,
    we feed hidden states straight to the DiT).
    """
    sd, arch, _ = _load_raw_gguf(path)
    if arch != "qwen3":
        log.warning(f"Expected arch=qwen3, got {arch}")
    sd = _sd_map_replace(sd, QWEN3_SD_MAP)
    sd = _llama_permute(sd, n_head, n_head_kv)
    if as_base_model:
        # Strip the leading "model." that the LLAMA map added, plus drop
        # the lm_head weight (not present on the base encoder).
        stripped = {}
        for k, v in sd.items():
            if k == "lm_head.weight":
                continue
            if k.startswith("model."):
                stripped[k[len("model."):]] = v
            else:
                stripped[k] = v
        sd = stripped
    return sd


def load_gemma_gguf(path: str | Path, n_head: int, n_head_kv: int) -> dict[str, GGMLTensor]:
    """Gemma-3 works out-of-the-box. Gemma-4 has extra tensors this map
    doesn't know about — expect load_state_dict to report unused keys for
    those. Do NOT use for gemma4 until HF-side names are verified."""
    sd, arch, _ = _load_raw_gguf(path)
    if arch not in ("gemma3", "gemma4"):
        log.warning(f"Expected arch=gemma3/gemma4, got {arch}")
    sd = _sd_map_replace(sd, GEMMA3_SD_MAP)
    sd = _llama_permute(sd, n_head, n_head_kv)
    sd = _gemma3_norm_corrections(sd)
    return sd


def load_lumina2_gguf(path: str | Path) -> dict[str, GGMLTensor]:
    """Z-Image / Lumina-2 DiT GGUF → diffusers ZImageTransformer2DModel
    state dict.

    The two naming conventions differ in three places:
      1. attention.qkv (fused, shape [3*dim, dim])
         → attention.to_q, attention.to_k, attention.to_v (split 3-way,
         shape [dim, dim] each). Same for context_refiner.* and
         noise_refiner.* blocks.
      2. attention.out → attention.to_out.0
      3. attention.q_norm → attention.norm_q
         attention.k_norm → attention.norm_k

    The fused qkv tensor is quantized; to split it cleanly we dequantize
    once at load time, chunk along dim 0, and keep the three resulting
    tensors in bf16 (~0.2% of total model size — cheap). All other
    tensors stay in their original quantized form.
    """
    sd, arch, _ = _load_raw_gguf(path)
    if arch not in ("lumina2", "zimage"):
        log.warning(f"Expected arch=lumina2, got {arch}")

    out: dict[str, GGMLTensor] = {}
    for k, v in sd.items():
        # Case 1: fused qkv → split to_q/to_k/to_v. `k` ends with
        # `attention.qkv.weight` — could be anywhere in the module tree.
        if k.endswith("attention.qkv.weight"):
            prefix = k[: -len(".qkv.weight")]  # e.g. "layers.0.attention"
            # Dequant then split. v.tensor_shape is the logical shape
            # [3*dim, dim]. Chunk along dim 0 into three equal pieces.
            dequant = dequantize_tensor(v, dtype=torch.bfloat16)
            q, kk, vv = dequant.chunk(3, dim=0)
            # Wrap each split as a non-quantized GGMLTensor (tensor_type=None
            # so the ops layer passes through .to(dtype) without dequant).
            def _as_plain(t: torch.Tensor) -> GGMLTensor:
                g = GGMLTensor(t.contiguous(), tensor_type=None,
                               tensor_shape=t.shape)
                return g
            out[f"{prefix}.to_q.weight"] = _as_plain(q)
            out[f"{prefix}.to_k.weight"] = _as_plain(kk)
            out[f"{prefix}.to_v.weight"] = _as_plain(vv)
            continue

        # Case 2: attention.out → attention.to_out.0 (weight + bias)
        if k.endswith("attention.out.weight"):
            out[k.replace("attention.out.weight", "attention.to_out.0.weight")] = v
            continue
        if k.endswith("attention.out.bias"):
            out[k.replace("attention.out.bias", "attention.to_out.0.bias")] = v
            continue

        # Case 3: q_norm / k_norm rename
        if "attention.q_norm." in k:
            out[k.replace("attention.q_norm.", "attention.norm_q.")] = v
            continue
        if "attention.k_norm." in k:
            out[k.replace("attention.k_norm.", "attention.norm_k.")] = v
            continue

        # Diffusers wraps x_embedder / final_layer in a multi-resolution
        # ModuleDict keyed by patchify ratio. Z-Image-Turbo only has the
        # "2-1" variant, so rebrand the single GGUF tensors to that slot.
        if k.startswith("x_embedder."):
            out[k.replace("x_embedder.", "all_x_embedder.2-1.", 1)] = v
            continue
        if k.startswith("final_layer."):
            out[k.replace("final_layer.", "all_final_layer.2-1.", 1)] = v
            continue

        # Pass-through for everything else (FFN, norms, adaLN, embedders, etc.)
        out[k] = v

    return out


# ───────────────── Lightweight inspector ──────────────────────────────────

def describe_gguf(path: str | Path) -> dict:
    """Quick audit: arch, tensor count, quant-type histogram, total MB."""
    p = str(Path(path).expanduser())
    reader = gguf.GGUFReader(p, "r")
    arch = _get_field(reader, "general.architecture", str) or "unknown"
    qtypes: dict[str, int] = {}
    total_bytes = 0
    for t in reader.tensors:
        n = getattr(t.tensor_type, "name", str(t.tensor_type))
        qtypes[n] = qtypes.get(n, 0) + 1
        total_bytes += t.data.nbytes
    return {
        "path": p, "arch": arch, "tensors": len(reader.tensors),
        "quant_histogram": dict(sorted(qtypes.items(), key=lambda kv: -kv[1])),
        "mb": round(total_bytes / (1024 * 1024), 1),
    }


def load_gguf(path):
    """Backward-compat: raw GGUF → state dict with GGUF-native names."""
    sd, _, _ = _load_raw_gguf(path)
    return sd
