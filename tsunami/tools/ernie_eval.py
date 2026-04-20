"""ERNIE-Image-Turbo parallel-eval scaffold.

A throwaway bench rig — loads Q4_K_M DiT via our custom gguf_ops, pairs it
with the bf16 Mistral3 text encoder / VAE / scheduler from the Baidu
snapshot, generates one image, reports per-step time and peak VRAM. Does
NOT touch prod (ERNIE-Image-Turbo runs on ernie_server :8092, unaffected).

The VAE is the one Baidu ships inside the ERNIE-Image-Turbo repo (168 MB
bf16, 32 latent channels, same architecture BFL introduced with Flux.2 —
hence the diffusers class is `AutoencoderKLFlux2`). We don't pull it from
BFL; it's already under Baidu's vae/ folder.

Constants come from unsloth/ERNIE-Image-Turbo-GGUF model card — not guessed:
  num_inference_steps = 8
  guidance_scale      = 1.0
  resolutions         = 1024x1024, 848x1264, 1264x848, 768x1376, 896x1200,
                        1376x768, 1200x896
  use_pe              = True (default on page)

We run with use_pe=False because transformers 4.57.1 doesn't ship
Ministral3ForCausalLM yet; this doesn't affect DiT/VAE latency — it just
skips the prompt-rewriting LLM in front.

Usage:
  python -m tsunami.tools.ernie_eval \\
    --gguf /home/jb/models_gguf/ernie-image-turbo-Q4_K_M.gguf \\
    --baidu-snapshot ~/.cache/huggingface/hub/models--baidu--ERNIE-Image-Turbo/snapshots/<hash> \\
    --prompt "a cat sitting on a windowsill at sunset" \\
    --height 1024 --width 1024 --steps 8 --cfg 1.0 \\
    --out /tmp/ernie_eval.png
"""
from __future__ import annotations

import argparse
import glob
import json
import time
from pathlib import Path

import torch

from tsunami.gguf_ops import (
    load_ernie_image_gguf, load_mistral3_lang_gguf,
    replace_linear_with_ggml, describe_gguf,
)


def _find_baidu_snapshot(model: str = "Turbo") -> Path:
    """`model` is "Turbo" (distilled, 8 steps) or "Base" (full, 50 steps)."""
    repo = "ERNIE-Image-Turbo" if model == "Turbo" else "ERNIE-Image"
    hits = sorted(glob.glob(
        str(Path.home() / f".cache/huggingface/hub/models--baidu--{repo}/snapshots/*")
    ))
    if not hits:
        raise SystemExit(
            f"No baidu/{repo} snapshot found. Run:\n"
            f"  huggingface-cli download baidu/{repo} "
            "--include 'text_encoder/*' 'tokenizer/*' 'vae/*' 'scheduler/*' "
            "'model_index.json' 'transformer/config.json' 'transformer/*.safetensors'"
        )
    return Path(hits[-1])


def _bytes_gb(b: int) -> float:
    return b / (1024 ** 3)


def build_pipeline(gguf_path: Path | None, baidu_snapshot: Path, device: str,
                   te_gguf: Path | None = None,
                   transformer_snapshot: Path | None = None):
    """Build the ErnieImagePipeline.

    `baidu_snapshot` provides text_encoder/vae/scheduler/tokenizer (always
    pulled from the Turbo snapshot; these components are shared between
    Turbo and Base).

    `transformer_snapshot` is where the DiT weights live (Turbo or Base
    snapshot). Defaults to `baidu_snapshot` when None.

    If `gguf_path` is set, loads quantized DiT from GGUF (5 GB, may degrade
    fine glyph rendering). If gguf_path is None, loads bf16 from
    `transformer_snapshot/transformer/` (16 GB, full fidelity).
    """
    transformer_snapshot = transformer_snapshot or baidu_snapshot
    from diffusers import (
        ErnieImagePipeline, ErnieImageTransformer2DModel,
        AutoencoderKLFlux2, FlowMatchEulerDiscreteScheduler,
    )
    from transformers import (
        AutoTokenizer, AutoModel, PreTrainedTokenizerFast,
        Mistral3Model, Mistral3Config,
    )

    if gguf_path is None:
        # bf16 path — let diffusers do the heavy lifting
        print(f"[1+2/5] Loading bf16 transformer from {transformer_snapshot/'transformer'}")
        t0 = time.time()
        transformer = ErnieImageTransformer2DModel.from_pretrained(
            transformer_snapshot / "transformer",
            torch_dtype=torch.bfloat16,
        ).to(device)
        print(f"      transformer loaded in {time.time()-t0:.1f}s — "
              f"{sum(p.numel() for p in transformer.parameters())/1e9:.2f}B params bf16")
    else:
        # GGUF path — original code
        transformer_cfg = json.loads((transformer_snapshot / "transformer/config.json").read_text())

        print("[1/5] Building ErnieImageTransformer2DModel skeleton ...")
        t0 = time.time()
        transformer = ErnieImageTransformer2DModel(
            hidden_size=transformer_cfg["hidden_size"],
            num_attention_heads=transformer_cfg["num_attention_heads"],
            num_layers=transformer_cfg["num_layers"],
            ffn_hidden_size=transformer_cfg["ffn_hidden_size"],
            in_channels=transformer_cfg["in_channels"],
            out_channels=transformer_cfg["out_channels"],
            patch_size=transformer_cfg["patch_size"],
            text_in_dim=transformer_cfg["text_in_dim"],
            rope_theta=transformer_cfg["rope_theta"],
            rope_axes_dim=tuple(transformer_cfg["rope_axes_dim"]),
            eps=transformer_cfg["eps"],
            qk_layernorm=transformer_cfg["qk_layernorm"],
        )
        n_swapped = replace_linear_with_ggml(transformer)
        print(f"      skeleton built in {time.time()-t0:.1f}s — {n_swapped} Linear→GGMLLinear swaps")

        print(f"[2/5] Loading GGUF: {gguf_path}")
        t0 = time.time()
        info = describe_gguf(gguf_path)
        print(f"      arch={info['arch']} tensors={info['tensors']} size={info['mb']:.0f} MB")
        print(f"      qtypes={info['quant_histogram']}")
        sd = load_ernie_image_gguf(gguf_path)
        missing, unexpected = transformer.load_state_dict(sd, strict=False, assign=True)
        print(f"      state_dict loaded in {time.time()-t0:.1f}s — "
              f"missing={len(missing)} unexpected={len(unexpected)}")
        if missing:
            print(f"      first missing: {missing[:5]}")
        if unexpected:
            print(f"      first unexpected: {unexpected[:5]}")
        # device-only move for GGMLTensor-backed module tree
        transformer = transformer.to(device=device)
        # bf16-cast plain F32 params (biases, LayerNorm) so they match bf16
        # activations; GGMLTensors carry uint8 storage (p.dtype=torch.uint8)
        # so this filter naturally leaves them quantized.
        cast_count = 0
        for name, p in transformer.named_parameters():
            if p.dtype == torch.float32:
                p.data = p.data.to(torch.bfloat16)
                cast_count += 1
        print(f"      bf16-cast {cast_count} F32 params (biases/norms)")

    if te_gguf is not None:
        print(f"[3/5] Loading text_encoder (Mistral3Model) — language_model from GGUF ({te_gguf.name}) ...")
        t0 = time.time()
        cfg = Mistral3Config.from_pretrained(baidu_snapshot / "text_encoder")
        text_encoder = Mistral3Model(cfg)
        # Drop vision tower + projector — text-only conditioning never touches
        # them, and they'd waste ~840 MB of random-init bf16 weights.
        del text_encoder.vision_tower
        del text_encoder.multi_modal_projector
        # GGUF-load just the language_model (a MistralModel)
        n_swapped = replace_linear_with_ggml(text_encoder.language_model)
        sd = load_mistral3_lang_gguf(
            te_gguf,
            n_head=cfg.text_config.num_attention_heads,
            n_head_kv=cfg.text_config.num_key_value_heads,
        )
        missing, unexpected = text_encoder.language_model.load_state_dict(sd, strict=False, assign=True)
        # bf16-cast F32 norms in the language_model
        for n, p in text_encoder.language_model.named_parameters():
            if p.dtype == torch.float32:
                p.data = p.data.to(torch.bfloat16)
        text_encoder = text_encoder.to(device=device)
        print(f"      GGUF TE loaded in {time.time()-t0:.1f}s — "
              f"{n_swapped} Linear→GGMLLinear swaps, "
              f"missing={len(missing)} unexpected={len(unexpected)}")
        if missing[:3]: print(f"      first missing: {missing[:3]}")
    else:
        print("[3/5] Loading text_encoder (Mistral3Model) from Baidu snapshot bf16 ...")
        t0 = time.time()
        text_encoder = AutoModel.from_pretrained(
            baidu_snapshot / "text_encoder",
            torch_dtype=torch.bfloat16,
        ).to(device)
    # Baidu's tokenizer_config.json names `TokenizersBackend` (their paddle-side
    # wrapper class, not in transformers). Skip the class lookup and load the
    # tokenizer.json file directly — it's standard HF fast-tokenizer format.
    tok_cfg = json.loads((baidu_snapshot / "tokenizer/tokenizer_config.json").read_text())
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=str(baidu_snapshot / "tokenizer/tokenizer.json"),
        bos_token=tok_cfg.get("bos_token"),
        eos_token=tok_cfg.get("eos_token"),
        unk_token=tok_cfg.get("unk_token"),
        pad_token=tok_cfg.get("pad_token"),
        model_max_length=tok_cfg.get("model_max_length", 2048),
    )
    print(f"      text encoder loaded in {time.time()-t0:.1f}s — "
          f"class={type(text_encoder).__name__}")

    print("[4/5] Loading VAE + scheduler from Baidu snapshot ...")
    t0 = time.time()
    vae = AutoencoderKLFlux2.from_pretrained(
        baidu_snapshot / "vae", torch_dtype=torch.bfloat16,
    ).to(device)
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(
        baidu_snapshot / "scheduler"
    )
    print(f"      vae + scheduler loaded in {time.time()-t0:.1f}s")

    print("[5/5] Assembling ErnieImagePipeline ...")
    pipe = ErnieImagePipeline(
        transformer=transformer, vae=vae,
        text_encoder=text_encoder, tokenizer=tokenizer,
        scheduler=scheduler,
        pe=None, pe_tokenizer=None,  # use_pe=False path — Ministral3 not in transformers 4.57
    )
    return pipe


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gguf", required=True, type=Path, help="ERNIE DiT GGUF")
    p.add_argument("--te-gguf", type=Path, default=None,
                   help="Optional Mistral3 text-encoder GGUF. If omitted, loads bf16 from Baidu snapshot.")
    p.add_argument("--baidu-snapshot", type=Path, default=None)
    p.add_argument("--prompt", default="A photograph of a cat sitting on a windowsill at golden hour, warm light, bokeh background")
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--cfg", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("/tmp/ernie_eval.png"))
    p.add_argument("--device", default="cuda")
    p.add_argument("--cpu-offload", action="store_true",
                   help="enable_model_cpu_offload — sequentially page TE/DiT/VAE to GPU, peak ≈ max single component")
    p.add_argument("--te-offload", action="store_true",
                   help="Manually offload TE to CPU after encode_prompt — TE only runs once per gen so this is free at the cost of 1 PCIe transfer")
    args = p.parse_args()

    baidu = args.baidu_snapshot or _find_baidu_snapshot()
    print(f"Baidu snapshot: {baidu}")

    torch.cuda.reset_peak_memory_stats()
    torch.cuda.empty_cache()
    vram_pre = torch.cuda.memory_allocated()
    print(f"VRAM pre-load: {_bytes_gb(vram_pre):.2f} GB")

    t_load_0 = time.time()
    pipe = build_pipeline(args.gguf, baidu,
                           args.device if not args.cpu_offload else "cpu",
                           te_gguf=args.te_gguf)
    if args.cpu_offload:
        # accelerate hooks page each component to GPU on its forward, then back.
        # Peak VRAM ≈ max(TE, DiT, VAE) instead of sum. Adds ~1-2s PCIe per gen.
        pipe.enable_model_cpu_offload()
        print("      enable_model_cpu_offload() — components pinned on CPU, paged to GPU on use")
    t_load = time.time() - t_load_0
    vram_loaded = torch.cuda.memory_allocated()
    vram_peak_load = torch.cuda.max_memory_allocated()
    print(f"\nLoad took {t_load:.1f}s  |  VRAM resident {_bytes_gb(vram_loaded):.2f} GB  "
          f"|  peak during load {_bytes_gb(vram_peak_load):.2f} GB\n")

    # Per-step timing hook
    step_times: list[float] = []
    def on_step(p, step_index, timestep, cb_kwargs):
        torch.cuda.synchronize()
        now = time.time()
        step_times.append(now)
        return cb_kwargs

    if args.te_offload and not args.cpu_offload:
        # Wrap encode_prompt to offload TE → CPU AFTER each call. Don't
        # pre-position on CPU — that'd cause _execution_device to return cpu,
        # routing input_ids to CPU while DiT lives on CUDA. Leave TE on the
        # build-time device (CUDA), let encode run, then page out.
        orig_encode = pipe.encode_prompt
        def _encode_then_offload(prompt, device, num_images_per_prompt=1):
            # Ensure TE is on CUDA for this encode (covers gen #2, #3, …)
            pipe.text_encoder.to(args.device)
            out = orig_encode(prompt, device, num_images_per_prompt)
            pipe.text_encoder.to("cpu")
            torch.cuda.empty_cache()
            return out
        pipe.encode_prompt = _encode_then_offload
        print("      TE → CPU after each encode_prompt; CUDA only for the encode itself")

    torch.cuda.reset_peak_memory_stats()
    print(f"Generating: {args.width}x{args.height} steps={args.steps} cfg={args.cfg}")
    print(f"Prompt: {args.prompt!r}")
    t_gen_0 = time.time()
    gen = torch.Generator(device=args.device).manual_seed(args.seed)
    image = pipe(
        prompt=args.prompt,
        height=args.height, width=args.width,
        num_inference_steps=args.steps,
        guidance_scale=args.cfg,
        use_pe=False,  # Ministral3 unavailable
        generator=gen,
        callback_on_step_end=on_step,
    ).images[0]
    torch.cuda.synchronize()
    t_gen = time.time() - t_gen_0
    vram_peak_gen = torch.cuda.max_memory_allocated()

    image.save(args.out)
    print(f"\n=== RESULT ===")
    print(f"Total gen time:        {t_gen:.2f}s")
    if len(step_times) >= 2:
        deltas = [step_times[i] - step_times[i-1] for i in range(1, len(step_times))]
        print(f"Per-step ms (×{len(deltas)}):  " + ", ".join(f"{d*1000:.0f}" for d in deltas))
        print(f"Mean step:             {sum(deltas)/len(deltas)*1000:.0f} ms")
    print(f"Peak VRAM during gen:  {_bytes_gb(vram_peak_gen):.2f} GB")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
