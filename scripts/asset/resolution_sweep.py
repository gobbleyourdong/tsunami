"""Resolution sweep — find where Qwen-Image-Edit breaks down.

Run one /v1/images/edit call at each of a list of resolutions with
FIXED seed and FIXED prompt and FIXED base image. Each output gets
nearest-neighbor upscaled to the max resolution in the sweep so every
cell in the final grid is the same pixel size — you see the MODEL's
resolved detail at each res, not the display upsample.

The point: find the minimum resolution where the edit still produces
a coherent, attachment-quality image. Below that, perf speed becomes
a free lunch (256-res inference at ~16× fewer pixels ~=  several × faster).

Usage:
  python scripts/asset/resolution_sweep.py \\
      --base scaffolds/engine/asset_library/tree_static/baseline_oak_iso.png \\
      --prompt "engulfed in active orange flames, bark charring, thick smoke" \\
      --out /tmp/res_sweep_tree_ignite.png \\
      --seed 42

Outputs:
  <out>                            — composed grid PNG
  <out>.json                       — metadata (resolutions, timings, prompt)
  <out>.d/                         — raw frames at each resolution
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("ressweep")

_REPO = Path(__file__).resolve().parent.parent.parent


DEFAULT_RESOLUTIONS = [256, 384, 512, 640, 768, 896, 1024]


def _edit(server: str, base_path: Path, prompt: str, resolution: int,
          seed: int, save_path: Path, negative_prompt: str = "",
          steps: int = 30, cfg: float = 4.0,
          timeout_s: int = 900) -> float:
    """Call /v1/images/edit. Returns elapsed seconds."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "path": str(base_path),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "height": resolution,
        "width": resolution,
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "seed": seed,
        "response_format": "save_path",
        "save_path": str(save_path),
    }
    t0 = time.time()
    r = requests.post(f"{server.rstrip('/')}/v1/images/edit",
                      json=payload, timeout=timeout_s)
    if r.status_code != 200:
        raise RuntimeError(
            f"/v1/images/edit @ {resolution}px failed "
            f"({r.status_code}): {r.text[:500]}"
        )
    return time.time() - t0


def _compose_grid(frames: list[tuple[int, Path]],
                  target_cell: int,
                  out_path: Path,
                  label_height: int = 36) -> None:
    """Upscale every frame to `target_cell` × `target_cell` using NEAREST
    (so the model's actual resolved pixels remain visible), append a
    resolution label strip below each, compose a horizontal strip.

    If the sweep has >4 frames, wraps into a 2-row grid to keep the
    sheet viewable without horizontal scrolling."""
    cols = min(4, len(frames))
    rows = (len(frames) + cols - 1) // cols
    cell_w, cell_h = target_cell, target_cell + label_height
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (20, 20, 20, 255))
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    for idx, (res, fpath) in enumerate(frames):
        col = idx % cols
        row = idx // cols
        x, y = col * cell_w, row * cell_h
        im = Image.open(fpath).convert("RGBA")
        # Upscale with NEAREST — preserve the model's actual pixel grid
        # so visual degradation at low res is visible rather than blurred.
        up = im.resize((target_cell, target_cell), Image.NEAREST)
        sheet.paste(up, (x, y), up)

        # Label strip below
        label_y = y + target_cell
        draw = ImageDraw.Draw(sheet)
        draw.rectangle([x, label_y, x + cell_w, label_y + label_height],
                       fill=(40, 40, 40, 255))
        text = f"{res}×{res}"
        draw.text((x + 8, label_y + 6), text, fill=(255, 255, 255, 255), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    log.info(f"[sweep] grid → {out_path} ({sheet.size})")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True, type=Path,
                   help="base image path (feeds /v1/images/edit)")
    p.add_argument("--prompt", required=True,
                   help="edit prompt to apply at every resolution")
    p.add_argument("--negative-prompt", default="",
                   help="negative prompt (default empty — but without one, "
                        "Qwen-Image-Edit's true_cfg_scale is effectively "
                        "disabled; pass a short generic negative like "
                        "'blurry, low quality' to engage CFG)")
    p.add_argument("--seed", type=int, default=42,
                   help="fixed seed across the whole sweep")
    p.add_argument("--resolutions", type=int, nargs="+",
                   default=DEFAULT_RESOLUTIONS,
                   help=f"resolutions to sweep (default: {DEFAULT_RESOLUTIONS})")
    p.add_argument("--server", default="http://127.0.0.1:8094",
                   help="qwen_image_server base URL")
    p.add_argument("--steps", type=int, default=40,
                   help="num_inference_steps (default 40 per model card; "
                        "pass 8 only for lightning LoRA)")
    p.add_argument("--cfg", type=float, default=4.0,
                   help="true_cfg_scale (default 4.0 per model card; "
                        "pass 1.0 only for lightning LoRA)")
    p.add_argument("--out", type=Path, required=True,
                   help="output grid PNG path")
    p.add_argument("--cell-size", type=int, default=512,
                   help="grid cell pixel size (display; all frames upscale to "
                        "this size via NEAREST for fair comparison)")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    if not args.base.is_file():
        print(f"ERROR: base image not found: {args.base}", file=sys.stderr)
        return 2

    # Check server health up front — nothing is more painful than starting
    # a 20-minute sweep and finding the server died mid-way. Use a generous
    # timeout because the server's async _lock may be held by a long-running
    # edit call in flight from a prior client (healthz still responds but
    # behind the lock wait) — short 5s timeout gave false negatives in
    # back-to-back runs.
    try:
        r = requests.get(f"{args.server.rstrip('/')}/healthz", timeout=180)
        if r.status_code != 200 or not r.json().get("pipe_loaded"):
            print(f"ERROR: server at {args.server} not ready: {r.text}",
                  file=sys.stderr)
            return 3
    except requests.RequestException as e:
        print(f"ERROR: server at {args.server} unreachable: {e}",
              file=sys.stderr)
        return 3

    frames_dir = args.out.with_suffix(args.out.suffix + ".d")
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames: list[tuple[int, Path]] = []
    timings: list[dict] = []

    log.info(
        f"[sweep] base={args.base} prompt={args.prompt[:60]!r} seed={args.seed} "
        f"resolutions={args.resolutions}"
    )

    for res in args.resolutions:
        save_path = frames_dir / f"edit_{res:04d}.png"
        log.info(f"[sweep] {res}×{res} → running /edit …")
        try:
            elapsed = _edit(args.server, args.base, args.prompt, res,
                            args.seed, save_path,
                            negative_prompt=args.negative_prompt,
                            steps=args.steps, cfg=args.cfg)
        except Exception as e:
            log.error(f"[sweep] {res}×{res} FAILED: {e}")
            timings.append({"resolution": res, "status": "failed", "error": str(e)})
            continue
        frames.append((res, save_path))
        timings.append({
            "resolution": res, "status": "ok",
            "elapsed_s": round(elapsed, 2),
            "pixels": res * res,
            "s_per_megapixel": round(elapsed / ((res * res) / 1_000_000), 2),
        })
        log.info(
            f"[sweep] {res}×{res} done in {elapsed:.1f}s "
            f"({timings[-1]['s_per_megapixel']}s/MP)"
        )

    target = max(args.cell_size, max(res for res, _ in frames))
    _compose_grid(frames, target_cell=target, out_path=args.out)

    meta = {
        "base": str(args.base),
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "seed": args.seed,
        "resolutions": args.resolutions,
        "cell_size": target,
        "steps": args.steps,
        "cfg": args.cfg,
        "timings": timings,
        "generated_at": int(time.time()),
    }
    meta_path = args.out.with_suffix(args.out.suffix + ".json")
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info(f"[sweep] metadata → {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
