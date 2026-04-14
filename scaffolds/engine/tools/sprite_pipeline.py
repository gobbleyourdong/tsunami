#!/usr/bin/env python3
"""
Sprite Pipeline — Generate game-ready pixel art sprites using SD Turbo + post-processing.

Pipeline:
  1. Generate: SD Turbo text-to-image (1-4 steps, sub-second)
  2. Background removal: chroma key or threshold
  3. Palette quantization: reduce to N colors
  4. Pixel snap: downscale to target size with nearest-neighbor
  5. Output: transparent PNG + spritesheet assembly

Usage:
  python sprite_pipeline.py character "pixel art knight with sword, side view"
  python sprite_pipeline.py object "pixel art health potion, red liquid"
  python sprite_pipeline.py texture "pixel art grass tile, seamless, top down"
  python sprite_pipeline.py batch characters.json  # batch from JSON definitions
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# pixel_extract lives in the tsunami tools package so the runtime's
# generate.py and this authoring pipeline share one implementation.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[3] / "tsunami" / "tools"))
from pixel_extract import extract_one  # noqa: E402

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "webgpu-game" / "public" / "sprites"

# ── Model Management ──────────────────────────────────────────────

MODEL_CONFIGS = {
    "z-image": {
        # Hits the tsunami server on :8090 — uses the Z-Image-Turbo weights
        # already loaded by serve_transformers.py, no second model load.
        # Sprite generation is an authoring-time activity and assumes the
        # tsunami server is running on a proper GPU box (the apps it produces
        # serve on-device; only authoring needs real hardware).
        "backend": "http",
        "endpoint": "http://localhost:8090/v1/images/generate",
        # Z-Image-Turbo official recipe: 9 steps + guidance 0.0.
        # Guidance > 0 on turbo models smooths edges.
        "steps": 9, "guidance": 0.0,
    },
}

_active_model = "z-image"
_pipe = None


def set_model(name: str) -> None:
    """Switch generation backend. Call before any generation."""
    global _active_model, _pipe
    if name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model '{name}'. Available: {', '.join(MODEL_CONFIGS.keys())}")
    if name != _active_model:
        _pipe = None
    _active_model = name
    print(f"[sprite] Model: {name}")


def get_pipeline():
    """No-op for the HTTP backend — generate_image() hits :8090 directly.
    Kept as a placeholder so future local-backend configs can slot in."""
    return None


def get_model_config() -> dict:
    return MODEL_CONFIGS[_active_model]


# ── Generation ────────────────────────────────────────────────────

STYLE_PREFIXES = {
    "character": "single pixel art game character sprite, one character only, clean silhouette, "
                 "centered, full body head to feet, solid magenta background, bright magenta #FF00FF background, "
                 "no ground, no shadow, no other characters, no props on ground, sharp pixels, 16-bit style, ",
    "object":    "single pixel art game item sprite, one item only, centered, clean edges, "
                 "solid magenta background, bright magenta #FF00FF background, "
                 "no shadow, no other objects, sharp pixels, 16-bit style, ",
    "texture":   "pixel art seamless tileable texture, top-down view, "
                 "game asset, repeating pattern, sharp pixels, 16-bit style, ",
}

NEGATIVE_PROMPT = (
    "blurry, soft, anti-aliased, gradient background, realistic, photo, "
    "3d render, text, watermark, signature, border, frame, cropped, "
    "low quality, noise, artifacts, multiple characters, group, crowd, "
    "multiple objects, collection, set, grid, sheet, collage"
)


def generate_image(
    prompt: str,
    category: str = "character",
    width: int = 512,
    height: int = 512,
    steps: int = -1,       # -1 = use model default
    guidance: float = -1,  # -1 = use model default
    seed: int = -1,
) -> Image.Image:
    """Generate a single image with the active model backend."""
    config = get_model_config()

    if steps < 0:
        steps = config["steps"]
    if guidance < 0:
        guidance = config["guidance"]

    styled_prompt = STYLE_PREFIXES.get(category, "") + prompt

    # HTTP backend: hit the tsunami server on :8090. Same Z-Image-Turbo
    # weights our generate_image tool uses, no second GPU-resident copy.
    if config.get("backend") == "http":
        import base64, io, httpx, random
        t0 = time.time()
        # Randomize seed if the caller didn't supply one — Z-Image-Turbo's
        # sampler is deterministic given a fixed seed, so batch generation
        # returns identical images without fresh randomness each call.
        actual_seed = seed if seed >= 0 else random.randint(0, 2**31 - 1)
        # Long timeout because the tsunami server may be busy with LLM
        # inference when a sprite request arrives; image generation itself
        # is fast (~3s) but queue wait can be minutes during active builds.
        with httpx.Client(timeout=600) as client:
            resp = client.post(config["endpoint"], json={
                "prompt": styled_prompt,
                "width": width, "height": height,
                "steps": steps, "guidance_scale": guidance,
                "seed": actual_seed,
            })
        elapsed = time.time() - t0
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP backend returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Z-Image server error: {data['error']}")
        b64 = data["data"][0]["b64_json"]
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        print(f"[sprite] Generated in {elapsed:.2f}s ({steps} steps, via {config['endpoint']})")
        return img

    raise RuntimeError(
        f"Model '{_active_model}' is not HTTP-backed but no local pipeline "
        f"is configured. Ensure the tsunami server is running on "
        f"http://localhost:8090 and the z-image backend is selected."
    )


def generate_variations(
    prompt: str,
    category: str = "character",
    count: int = 4,
    width: int = 512,
    height: int = 512,
    steps: int = 4,
) -> list[Image.Image]:
    """Generate multiple variations, return all."""
    images = []
    for i in range(count):
        seed = int(time.time() * 1000) % (2**32) + i * 7919
        img = generate_image(prompt, category, width, height, steps, seed=seed)
        images.append(img)
    return images


# ── Post-Processing ───────────────────────────────────────────────

def remove_background(img: Image.Image, method: str = "sigmatrade", threshold: int = 120) -> Image.Image:
    """Remove background — sigmatrade method (smooth alpha + decontamination + erosion).

    Ported from sigmatrade logo-gen pipeline. Generates against magenta (#FF00FF)
    then removes via color-distance keying with smooth alpha ramp and color
    decontamination on semi-transparent edge pixels.
    """
    from scipy.ndimage import binary_erosion, label as ndlabel
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    rgb = arr[:,:,:3].astype(np.float64)

    if method == "sigmatrade":
        # Sample bg color from edges (works for any bg color — magenta, white, green)
        edge_pixels = np.concatenate([rgb[0,:], rgb[-1,:], rgb[:,0], rgb[:,-1]]).reshape(-1, 3)
        bg_color = np.median(edge_pixels, axis=0)

        # Euclidean distance from bg
        dist = np.sqrt(np.sum((rgb - bg_color)**2, axis=2))

        # Smooth alpha ramp (not binary — gives anti-aliased edges)
        inner = threshold * 0.4
        alpha = np.clip((dist - inner) / (threshold - inner), 0.0, 1.0) * 255.0
        alpha = alpha.astype(np.uint8)

        # Color decontamination — remove bg tint from semi-transparent edge pixels
        alpha_f = alpha.astype(np.float64) / 255.0
        semitrans = (alpha_f > 0.01) & (alpha_f < 0.99)
        if semitrans.any():
            for c in range(3):
                ch = rgb[:,:,c].copy()
                bg_c = bg_color[c]
                fg = (ch[semitrans] - bg_c * (1.0 - alpha_f[semitrans])) / np.maximum(alpha_f[semitrans], 0.01)
                ch[semitrans] = np.clip(fg, 0, 255)
                rgb[:,:,c] = ch

        # Erode 1px to kill fringe
        binary_mask = alpha > 128
        eroded = binary_erosion(binary_mask, iterations=1)
        alpha[~eroded] = 0

        arr[:,:,:3] = rgb.astype(np.uint8)
        arr[:,:,3] = alpha

    elif method == "floodfill":
        # Flood-fill from edges (previous method, kept as fallback)
        edge_pixels = np.concatenate([rgb[0,:], rgb[-1,:], rgb[:,0], rgb[:,-1]])
        bg_color = np.median(edge_pixels, axis=0)
        dist = np.sqrt(np.sum((rgb - bg_color)**2, axis=2))
        bg_mask = dist < threshold

        labeled, n_labels = ndlabel(bg_mask)
        edge_labels = set()
        edge_labels.update(labeled[0,:].tolist())
        edge_labels.update(labeled[-1,:].tolist())
        edge_labels.update(labeled[:,0].tolist())
        edge_labels.update(labeled[:,-1].tolist())
        edge_labels.discard(0)

        flood_mask = np.isin(labeled, list(edge_labels))
        arr[flood_mask, 3] = 0
    else:
        edge_pixels = np.concatenate([rgb[0,:], rgb[-1,:], rgb[:,0], rgb[:,-1]])
        bg_color = np.median(edge_pixels, axis=0)
        dist = np.sqrt(np.sum((rgb - bg_color)**2, axis=2))
        arr[dist < threshold, 3] = 0

    return Image.fromarray(arr)


def center_crop_object(img: Image.Image, crop_ratio: float = 0.55) -> Image.Image:
    """Crop to center region — grabs the main centered object, discards edge clutter.
    Use for 'object' category where SD generates grids/collections but we want one item."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    margin_x = int(w * (1 - crop_ratio) / 2)
    margin_y = int(h * (1 - crop_ratio) / 2)
    return img.crop((margin_x, margin_y, w - margin_x, h - margin_y))


def quantize_palette(img: Image.Image, n_colors: int = 16) -> Image.Image:
    """Reduce to N colors using median cut quantization."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Separate alpha
    alpha = np.array(img)[:,:,3]

    # Quantize RGB only
    rgb = img.convert("RGB")
    quantized = rgb.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    result = quantized.convert("RGBA")

    # Restore alpha
    result_arr = np.array(result)
    result_arr[:,:,3] = alpha
    return Image.fromarray(result_arr)


def score_sprite(img: Image.Image, category: str = "character") -> tuple[float, dict]:
    """Score a sprite's quality. Returns (score 0-1, reasons dict).

    Checks:
    - Coverage: how much of the frame is filled (not too small, not cropped)
    - Centering: subject should be roughly centered
    - Opacity: enough opaque pixels (not mostly transparent)
    - Fragmentation: single solid blob, not scattered dots
    - Color diversity: enough distinct colors (not monochrome)
    """
    from scipy import ndimage

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    arr = np.array(img)
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3]
    opaque = alpha > 128
    total_px = h * w
    opaque_count = np.sum(opaque)

    reasons = {}
    scores = []

    # 1. Coverage: opaque area should be 15-85% of frame
    coverage = opaque_count / total_px
    if category == "texture":
        coverage_score = min(coverage / 0.9, 1.0)  # textures should fill the frame
    else:
        if coverage < 0.05:
            coverage_score = 0.0
        elif coverage < 0.15:
            coverage_score = coverage / 0.15
        elif coverage > 0.85:
            coverage_score = max(0, 1.0 - (coverage - 0.85) / 0.15)
        else:
            coverage_score = 1.0
    reasons["coverage"] = round(coverage, 3)
    scores.append(coverage_score)

    # 2. Centering: center of mass should be near frame center
    if opaque_count > 0 and category != "texture":
        com = ndimage.center_of_mass(opaque)
        cx_off = abs(com[1] / w - 0.5) * 2  # 0=centered, 1=edge
        cy_off = abs(com[0] / h - 0.5) * 2
        center_score = 1.0 - max(cx_off, cy_off)
        reasons["center_offset"] = round(max(cx_off, cy_off), 3)
    else:
        center_score = 1.0 if category == "texture" else 0.0
    scores.append(center_score)

    # 3. Fragmentation: how many disconnected blobs? Fewer is better.
    if opaque_count > 0 and category != "texture":
        labeled, n_labels = ndimage.label(opaque)
        frag_score = 1.0 / max(n_labels, 1)  # 1 blob = 1.0, 5 blobs = 0.2
        reasons["fragments"] = n_labels
    else:
        frag_score = 1.0
    scores.append(frag_score)

    # 4. Color diversity
    if opaque_count > 10:
        opaque_pixels = arr[opaque][:, :3]
        unique_colors = len(np.unique(opaque_pixels.reshape(-1, 3), axis=0))
        if category == "texture":
            diversity_score = min(unique_colors / 20, 1.0)
        else:
            diversity_score = min(unique_colors / 10, 1.0)
        reasons["unique_colors"] = unique_colors
    else:
        diversity_score = 0.0
    scores.append(diversity_score)

    final_score = sum(scores) / len(scores)
    reasons["final"] = round(final_score, 3)
    return final_score, reasons


def pixel_snap(img: Image.Image, target_size: tuple[int, int] = (64, 64)) -> Image.Image:
    """Downscale to target pixel art size using nearest-neighbor."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    return img.resize(target_size, Image.Resampling.NEAREST)


def isolate_largest_object(img: Image.Image) -> Image.Image:
    """Keep only the largest connected opaque region — discards extra characters/objects."""
    from scipy import ndimage

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    arr = np.array(img)
    alpha = arr[:,:,3]
    opaque = alpha > 128

    if not np.any(opaque):
        return img

    labeled, n_labels = ndimage.label(opaque)
    if n_labels <= 1:
        return img  # already single object

    # Find largest component
    sizes = ndimage.sum(opaque, labeled, range(1, n_labels + 1))
    largest_label = np.argmax(sizes) + 1

    # Zero out everything except largest
    mask = labeled != largest_label
    arr[mask, 3] = 0

    return Image.fromarray(arr)


def trim_transparent(img: Image.Image, padding: int = 1) -> Image.Image:
    """Crop to non-transparent bounding box with optional padding."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    arr = np.array(img)
    alpha = arr[:,:,3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)

    if not np.any(rows) or not np.any(cols):
        return img  # fully transparent

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    rmin = max(0, rmin - padding)
    rmax = min(arr.shape[0] - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(arr.shape[1] - 1, cmax + padding)

    return img.crop((cmin, rmin, cmax + 1, rmax + 1))


def normalize_height(img: Image.Image, target_height: int, anchor: str = "bottom") -> Image.Image:
    """Scale to target height preserving aspect ratio, anchor to bottom or center."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    if h == 0:
        return img
    scale = target_height / h
    new_w = max(1, int(w * scale))
    resized = img.resize((new_w, target_height), Image.Resampling.NEAREST)
    return resized


# ── Spritesheet Assembly ──────────────────────────────────────────

def assemble_spritesheet(
    frames: list[Image.Image],
    columns: int = 0,
    padding: int = 0,
) -> tuple[Image.Image, dict]:
    """Assemble frames into a spritesheet. Returns (image, metadata)."""
    if not frames:
        raise ValueError("No frames to assemble")

    # Auto columns: square-ish layout
    n = len(frames)
    if columns <= 0:
        columns = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / columns))

    # Find max frame size
    max_w = max(f.size[0] for f in frames)
    max_h = max(f.size[1] for f in frames)

    cell_w = max_w + padding * 2
    cell_h = max_h + padding * 2

    sheet = Image.new("RGBA", (columns * cell_w, rows * cell_h), (0, 0, 0, 0))

    frame_data = []
    for i, frame in enumerate(frames):
        col = i % columns
        row = i // columns
        x = col * cell_w + padding + (max_w - frame.size[0]) // 2
        y = row * cell_h + padding + (max_h - frame.size[1])  # bottom-aligned
        sheet.paste(frame, (x, y), frame)
        frame_data.append({
            "index": i,
            "x": col * cell_w, "y": row * cell_h,
            "width": cell_w, "height": cell_h,
        })

    metadata = {
        "frame_count": n,
        "columns": columns,
        "rows": rows,
        "frame_width": cell_w,
        "frame_height": cell_h,
        "sheet_width": columns * cell_w,
        "sheet_height": rows * cell_h,
        "frames": frame_data,
    }

    return sheet, metadata


# ── Full Pipeline ─────────────────────────────────────────────────

def run_pipeline(
    prompt: str,
    category: str = "character",
    name: str = "sprite",
    variations: int = 4,
    target_size: tuple[int, int] = (64, 64),
    n_colors: int = 16,
    bg_method: str = "corners",
    gen_size: int = 512,
    steps: int = 4,
    output_dir: Path | None = None,
) -> dict:
    """Run the full sprite generation pipeline."""
    out = output_dir or OUTPUT_DIR / category
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"[pipeline] {category}: {prompt}")
    print(f"[pipeline] Variations: {variations}, Target: {target_size}, Colors: {n_colors}")
    print(f"{'='*60}\n")

    # 1. Generate variations
    print("[1/5] Generating...")
    images = generate_variations(prompt, category, variations, gen_size, gen_size, steps)

    # Save raw generations
    raw_dir = out / name / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images):
        img.save(raw_dir / f"{name}_raw_{i}.png")
    print(f"[1/5] Saved {len(images)} raw images to {raw_dir}")

    # 2. Extract pixel-art sprite per variation. This does bg detection
    # (perceptual Lab), native-grid recovery, center-sampling, and
    # edge-adjacent fringe cleanup in one pass — replaces the old
    # center_crop / remove_background / isolate_largest / trim / snap chain.
    # Textures still skip the extractor (they fill the frame by design).
    print(f"[2/4] Extracting pixel art from {len(images)} variations...")
    final = []
    for i, img in enumerate(images):
        rgba = np.asarray(img.convert("RGBA"))
        if category == "texture":
            # For textures: no extraction, just hand the raw frame through.
            final.append(img.convert("RGBA"))
            print(f"  [{i}] texture {img.size} (passthrough)")
            continue
        result = extract_one(rgba)
        if result is None:
            print(f"  [{i}] extraction failed — skipping")
            continue
        sprite = Image.fromarray(result.rgba, mode="RGBA")
        final.append(sprite)
        print(
            f"  [{i}] {img.size} → {sprite.size}  "
            f"pixel_size=({result.pixel_size_x:.1f}, {result.pixel_size_y:.1f})"
        )

    if not final:
        raise RuntimeError(f"No sprites extracted from {len(images)} variations")

    # Score all sprites and rank
    print("[6/7] Scoring sprites...")
    scored = []
    for i, img in enumerate(final):
        score, reasons = score_sprite(img, category)
        scored.append((i, score, reasons, img))
        status = "GOOD" if score > 0.6 else "FAIR" if score > 0.35 else "POOR"
        print(f"  [{i}] {status} score={score:.3f}  coverage={reasons.get('coverage', '?')} "
              f"frags={reasons.get('fragments', '?')} colors={reasons.get('unique_colors', '?')}")

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    best_idx, best_score, _, best_img = scored[0]
    print(f"  Best: [{best_idx}] score={best_score:.3f}")

    # Save all sprites + mark best
    sprite_dir = out / name
    sprite_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(final):
        img.save(sprite_dir / f"{name}_{i}.png")
    best_img.save(sprite_dir / f"{name}_best.png")
    print(f"[6/7] Saved {len(final)} sprites + best to {sprite_dir}")

    # 7. Assemble spritesheet (best first, then rest by score)
    print("[7/7] Assembling spritesheet...")
    sorted_images = [s[3] for s in scored]
    sheet, metadata = assemble_spritesheet(sorted_images, columns=len(sorted_images))
    sheet.save(sprite_dir / f"{name}_sheet.png")

    metadata["prompt"] = prompt
    metadata["category"] = category
    metadata["name"] = name
    metadata["target_size"] = list(target_size)
    metadata["palette_colors"] = n_colors
    metadata["scores"] = [{"index": s[0], "score": round(s[1], 3), **s[2]} for s in scored]
    metadata["best_index"] = best_idx
    metadata["best_score"] = round(best_score, 3)

    with open(sprite_dir / f"{name}_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[6/6] Spritesheet: {sprite_dir / f'{name}_sheet.png'}")
    print(f"[pipeline] Done: {name}\n")

    return metadata


# ── Batch Processing ──────────────────────────────────────────────

def run_batch(batch_file: str):
    """Run pipeline from a JSON batch definition file."""
    with open(batch_file) as f:
        batch = json.load(f)

    results = []
    for item in batch:
        meta = run_pipeline(
            prompt=item["prompt"],
            category=item.get("category", "character"),
            name=item.get("name", "sprite"),
            variations=item.get("variations", 4),
            target_size=tuple(item.get("target_size", [64, 64])),
            n_colors=item.get("colors", 16),
        )
        results.append(meta)

    return results


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sprite generation pipeline — SD Turbo + post-processing",
        epilog="Models: " + ", ".join(MODEL_CONFIGS.keys()),
    )
    parser.add_argument("category", choices=["character", "object", "texture", "batch"],
                        help="Asset category or 'batch' for JSON file")
    parser.add_argument("prompt", help="Text prompt or batch JSON file path")
    parser.add_argument("--model", "-m", default="z-image", choices=list(MODEL_CONFIGS.keys()),
                        help="Generation model backend (default: z-image, via tsunami server on :8090)")
    parser.add_argument("--name", default="sprite", help="Output name prefix")
    parser.add_argument("--variations", "-n", type=int, default=4)
    parser.add_argument("--size", type=int, default=64, help="Target sprite size (square)")
    parser.add_argument("--colors", type=int, default=16, help="Palette color count")
    parser.add_argument("--steps", type=int, default=-1, help="Diffusion steps (-1 = model default)")
    parser.add_argument("--gen-size", type=int, default=512, help="Generation resolution")
    parser.add_argument("--bg", choices=["sigmatrade", "floodfill", "chroma"], default="sigmatrade")
    args = parser.parse_args()

    set_model(args.model)

    if args.category == "batch":
        run_batch(args.prompt)
    else:
        run_pipeline(
            prompt=args.prompt,
            category=args.category,
            name=args.name,
            variations=args.variations,
            target_size=(args.size, args.size),
            n_colors=args.colors,
            steps=args.steps,
            gen_size=args.gen_size,
            bg_method=args.bg,
        )


if __name__ == "__main__":
    main()
