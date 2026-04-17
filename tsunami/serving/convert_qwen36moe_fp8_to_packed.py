#!/usr/bin/env python3
"""Convert Qwen3.5-MoE / Qwen3.6-A3B FP8 checkpoints from the on-disk
unpacked layout (per-expert `gate_proj` / `up_proj` / `down_proj`) into the
packed layout (`experts.gate_up_proj` / `experts.down_proj`) that
transformers v5's qwen3_5_moe modeling expects.

Unpacked (HF checkpoint):
    layers.L.mlp.experts.<e>.gate_proj.weight             (I, H)  fp8_e4m3
    layers.L.mlp.experts.<e>.gate_proj.weight_scale_inv   (I/128, H/128)  fp32
    layers.L.mlp.experts.<e>.up_proj.weight               (I, H)  fp8_e4m3
    layers.L.mlp.experts.<e>.up_proj.weight_scale_inv     (I/128, H/128)  fp32
    layers.L.mlp.experts.<e>.down_proj.weight             (H, I)  fp8_e4m3
    layers.L.mlp.experts.<e>.down_proj.weight_scale_inv   (H/128, I/128)  fp32

Packed (transformers expects):
    layers.L.mlp.experts.gate_up_proj             (E, 2*I, H)  fp8_e4m3
    layers.L.mlp.experts.gate_up_proj_scale_inv   (E, 2*I/128, H/128)  fp32
    layers.L.mlp.experts.down_proj                (E, H, I)  fp8_e4m3
    layers.L.mlp.experts.down_proj_scale_inv      (E, H/128, I/128)  fp32

Streams per-layer so peak RAM = one layer's worth of expert weights.

Usage:
    python3 convert_qwen36moe_fp8_to_packed.py \
        --src  ~/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/<sha> \
        --dst  /home/jb/training_stage/qwen36_a3b_fp8_packed
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

EXPERT_RE = re.compile(
    r"^(model\.language_model\.layers\.\d+\.mlp\.experts)\.(\d+)\.(gate_proj|up_proj|down_proj)\.(weight|weight_scale_inv)$"
)


def _open_shards(src: Path) -> dict[str, Path]:
    """Return {tensor_name -> file path} from the model.safetensors.index.json.
    Each source shard is opened lazily via safe_open when we pull tensors out."""
    idx = json.loads((src / "model.safetensors.index.json").read_text())
    return {name: src / fname for name, fname in idx["weight_map"].items()}


def _collect_experts_by_layer(name2path: dict[str, Path]) -> dict[int, list[str]]:
    """Group all expert weight keys by layer index. Drops the layer.N prefix."""
    per_layer: dict[int, list[str]] = defaultdict(list)
    for name in name2path:
        m = EXPERT_RE.match(name)
        if not m:
            continue
        layer_idx = int(name.split("layers.")[1].split(".")[0])
        per_layer[layer_idx].append(name)
    return dict(sorted(per_layer.items()))


def _load_tensor(name: str, name2path: dict[str, Path]) -> torch.Tensor:
    with safe_open(str(name2path[name]), framework="pt", device="cpu") as f:
        return f.get_tensor(name)


def _stack_packed_layer(layer: int, expert_keys: list[str],
                        name2path: dict[str, Path]) -> dict[str, torch.Tensor]:
    """Fuse one layer's expert weights: per expert concat gate+up, then stack
    across experts. Returns {packed_name -> tensor} ready to save."""
    # Bucket by expert idx → proj → suffix
    per_expert: dict[int, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    prefix = None
    for name in expert_keys:
        m = EXPERT_RE.match(name)
        assert m, name
        prefix, eidx, proj, suffix = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        per_expert[eidx][proj][suffix] = name
    num_experts = max(per_expert) + 1
    assert set(per_expert) == set(range(num_experts)), f"missing experts at layer {layer}"
    assert prefix is not None

    # Gate + Up fused per expert, then stacked across experts.
    gate_up_w_list: list[torch.Tensor] = []
    gate_up_s_list: list[torch.Tensor] = []
    down_w_list: list[torch.Tensor] = []
    down_s_list: list[torch.Tensor] = []
    for e in range(num_experts):
        slots = per_expert[e]
        gate_w = _load_tensor(slots["gate_proj"]["weight"], name2path)
        up_w = _load_tensor(slots["up_proj"]["weight"], name2path)
        gate_s = _load_tensor(slots["gate_proj"]["weight_scale_inv"], name2path)
        up_s = _load_tensor(slots["up_proj"]["weight_scale_inv"], name2path)
        down_w = _load_tensor(slots["down_proj"]["weight"], name2path)
        down_s = _load_tensor(slots["down_proj"]["weight_scale_inv"], name2path)
        # Concat along the first (output) dim — transformers does
        # `.chunk(2, dim=-1)` on (B @ gate_up_proj[e]) — the linear output is
        # [B, 2*I], whose last dim splits as (gate, up). That means in the
        # weight's [out=2*I, in=H] layout, gate is rows [0:I], up is rows [I:2I].
        gate_up_w_list.append(torch.cat([gate_w, up_w], dim=0))
        gate_up_s_list.append(torch.cat([gate_s, up_s], dim=0))
        down_w_list.append(down_w)
        down_s_list.append(down_s)

    gate_up_w = torch.stack(gate_up_w_list, dim=0)   # (E, 2I, H)
    gate_up_s = torch.stack(gate_up_s_list, dim=0)   # (E, 2I/128, H/128)
    down_w = torch.stack(down_w_list, dim=0)         # (E, H, I)
    down_s = torch.stack(down_s_list, dim=0)         # (E, H/128, I/128)

    return {
        f"{prefix}.gate_up_proj": gate_up_w.contiguous(),
        f"{prefix}.gate_up_proj_scale_inv": gate_up_s.contiguous(),
        f"{prefix}.down_proj": down_w.contiguous(),
        f"{prefix}.down_proj_scale_inv": down_s.contiguous(),
    }


def _iter_non_expert_tensors(name2path: dict[str, Path]):
    """Yield (name, tensor) for every param that is NOT a per-expert weight.
    Those pass through unchanged."""
    for name, path in name2path.items():
        if EXPERT_RE.match(name):
            continue
        yield name, _load_tensor(name, name2path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path,
                    help="HF snapshot dir containing model.safetensors.index.json + layers-*.safetensors")
    ap.add_argument("--dst", required=True, type=Path,
                    help="Output dir for packed checkpoint (will be created / cleared)")
    ap.add_argument("--shard-max-gb", type=float, default=5.0,
                    help="Rough max size per output safetensors shard")
    args = ap.parse_args()

    src: Path = args.src.expanduser().resolve()
    dst: Path = args.dst.expanduser().resolve()
    assert src.is_dir(), f"not a dir: {src}"
    dst.mkdir(parents=True, exist_ok=True)

    print(f"src: {src}")
    print(f"dst: {dst}")

    name2path = _open_shards(src)
    per_layer = _collect_experts_by_layer(name2path)
    print(f"layers with experts: {len(per_layer)}")
    expert_keys_set = set()
    for keys in per_layer.values():
        expert_keys_set.update(keys)
    print(f"expert tensors to fuse: {len(expert_keys_set)}")
    print(f"non-expert tensors to copy: {len(name2path) - len(expert_keys_set)}")

    shard_max_bytes = int(args.shard_max_gb * (1024**3))
    shard_idx = 0
    shard_buf: dict[str, torch.Tensor] = {}
    shard_bytes = 0
    weight_map: dict[str, str] = {}
    total_bytes = 0

    def flush_shard():
        nonlocal shard_idx, shard_buf, shard_bytes, total_bytes
        if not shard_buf:
            return
        fname = f"model-{shard_idx:05d}.safetensors"
        out = dst / fname
        save_file(shard_buf, str(out),
                  metadata={"format": "pt", "source": "converted-from-unpacked-fp8"})
        for k in shard_buf:
            weight_map[k] = fname
        total_bytes += shard_bytes
        print(f"  wrote {fname} ({shard_bytes / (1024**3):.2f} GB, {len(shard_buf)} tensors)")
        shard_buf = {}
        shard_bytes = 0
        shard_idx += 1

    def add(name: str, t: torch.Tensor):
        nonlocal shard_bytes
        nb = t.element_size() * t.numel()
        if shard_bytes + nb > shard_max_bytes and shard_buf:
            flush_shard()
        shard_buf[name] = t
        shard_bytes += nb

    # 1) Pack one layer at a time so peak RAM stays bounded.
    t0 = time.time()
    for layer, keys in per_layer.items():
        lt = time.time()
        packed = _stack_packed_layer(layer, keys, name2path)
        elapsed = time.time() - lt
        sz = sum(v.element_size() * v.numel() for v in packed.values()) / (1024**3)
        print(f"layer {layer:2d}: packed 4 tensors ({sz:.2f} GB) in {elapsed:.1f}s")
        for name, tens in packed.items():
            add(name, tens)

    # 2) Stream every non-expert tensor straight through.
    print("copying non-expert tensors …")
    for name, tens in _iter_non_expert_tensors(name2path):
        add(name, tens)
    flush_shard()

    # 3) Emit matching safetensors index.
    index = {
        "metadata": {"total_size": total_bytes, "converted_from": str(src)},
        "weight_map": weight_map,
    }
    (dst / "model.safetensors.index.json").write_text(json.dumps(index, indent=2))
    print(f"wrote model.safetensors.index.json ({len(weight_map)} entries, "
          f"{total_bytes / (1024**3):.2f} GB total) in {time.time() - t0:.1f}s")

    # 4) Copy over config + tokenizer + chat template etc. so the dst is a
    # fully self-contained model directory we can hand to from_pretrained.
    small_files = [
        "config.json", "configuration.json", "generation_config.json",
        "chat_template.jinja", "tokenizer.json", "tokenizer_config.json",
        "vocab.json", "merges.txt",
        "preprocessor_config.json", "video_preprocessor_config.json",
        "LICENSE", "README.md",
    ]
    for fn in small_files:
        sp = src / fn
        if sp.exists():
            shutil.copy2(sp, dst / fn)
    print("done.")


if __name__ == "__main__":
    main()
