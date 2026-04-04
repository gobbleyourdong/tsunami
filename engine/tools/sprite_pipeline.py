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

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "webgpu-game" / "public" / "sprites"

# ── Model Management ──────────────────────────────────────────────

_pipe = None

def get_pipeline():
    """Lazy-load SD Turbo pipeline (keeps GPU memory free until needed)."""
    global _pipe
    if _pipe is not None:
        return _pipe

    import torch
    from diffusers import AutoPipelineForText2Image

    print("[sprite] Loading SD Turbo...")
    _pipe = AutoPipelineForText2Image.from_pretrained(
        "stabilityai/sd-turbo",
        torch_dtype=torch.float16,
        variant="fp16",
    )
    _pipe = _pipe.to("cuda")
    print("[sprite] SD Turbo ready on GPU")
    return _pipe


# ── Generation ────────────────────────────────────────────────────

STYLE_PREFIXES = {
    "character": "single pixel art game character sprite, one character only, clean silhouette, "
                 "centered, full body head to feet, solid white background, no ground, no shadow, "
                 "no other characters, no props on ground, sharp pixels, 16-bit style, ",
    "object":    "single pixel art game item sprite, one item only, centered, clean edges, "
                 "solid white background, no shadow, no other objects, sharp pixels, 16-bit style, ",
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
    steps: int = 4,
    guidance: float = 0.0,  # SD Turbo uses guidance_scale=0
    seed: int = -1,
) -> Image.Image:
    """Generate a single image with SD Turbo."""
    import torch

    pipe = get_pipeline()

    # Prepend style prefix
    styled_prompt = STYLE_PREFIXES.get(category, "") + prompt

    generator = None
    if seed >= 0:
        generator = torch.Generator(device="cuda").manual_seed(seed)

    t0 = time.time()
    result = pipe(
        prompt=styled_prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=steps,
        guidance_scale=guidance,
        width=width,
        height=height,
        generator=generator,
    )
    elapsed = time.time() - t0
    print(f"[sprite] Generated in {elapsed:.2f}s ({steps} steps)")

    return result.images[0]


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

def remove_background(img: Image.Image, method: str = "threshold", threshold: int = 30) -> Image.Image:
    """Remove background — threshold (for solid bg) or chroma (for green screen)."""
    arr = np.array(img.convert("RGBA"))

    if method == "chroma":
        # Remove green (#00FF00 ± tolerance)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        mask = (g > 200) & (r < 100) & (b < 100)
        arr[mask, 3] = 0
    elif method == "threshold":
        # Remove near-white or most common bg color
        rgb = arr[:,:,:3]
        # Find most common edge color (likely background)
        edges = np.concatenate([rgb[0,:], rgb[-1,:], rgb[:,0], rgb[:,-1]])
        bg_color = np.median(edges, axis=0).astype(np.uint8)
        dist = np.sqrt(np.sum((rgb.astype(float) - bg_color.astype(float))**2, axis=2))
        mask = dist < threshold
        arr[mask, 3] = 0
    elif method == "corners":
        # Sample corners, remove similar colors
        h, w = arr.shape[:2]
        corners = [arr[0,0,:3], arr[0,w-1,:3], arr[h-1,0,:3], arr[h-1,w-1,:3]]
        bg_color = np.median(corners, axis=0).astype(float)
        rgb = arr[:,:,:3].astype(float)
        dist = np.sqrt(np.sum((rgb - bg_color)**2, axis=2))
        arr[dist < 40, 3] = 0

    return Image.fromarray(arr)


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


def pixel_snap(img: Image.Image, target_size: tuple[int, int] = (64, 64)) -> Image.Image:
    """Downscale to target pixel art size using nearest-neighbor."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    return img.resize(target_size, Image.Resampling.NEAREST)


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

    # 2. Remove backgrounds (skip for textures — they fill the frame)
    if category == "texture":
        print("[2/5] Skipping bg removal (texture mode)")
        transparent = [img.convert("RGBA") for img in images]
    else:
        print("[2/5] Removing backgrounds...")
        transparent = []
        for img in images:
            t = remove_background(img, method=bg_method, threshold=30)
            transparent.append(t)

    # 3. Trim + normalize (skip trim for textures)
    if category == "texture":
        print("[3/5] Skipping trim (texture mode)")
        normalized = transparent
    else:
        print("[3/5] Trimming + normalizing...")
        trimmed = [trim_transparent(t) for t in transparent]
        normalized = [normalize_height(t, target_size[1]) for t in trimmed]

    # 4. Pixel snap + quantize
    print("[4/5] Pixel snapping + palette quantization...")
    final = []
    for img in normalized:
        snapped = pixel_snap(img, target_size)
        quantized = quantize_palette(snapped, n_colors)
        final.append(quantized)

    # Save individual sprites
    sprite_dir = out / name
    sprite_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(final):
        img.save(sprite_dir / f"{name}_{i}.png")
    print(f"[4/5] Saved {len(final)} sprites to {sprite_dir}")

    # 5. Assemble spritesheet
    print("[5/5] Assembling spritesheet...")
    sheet, metadata = assemble_spritesheet(final, columns=len(final))
    sheet.save(sprite_dir / f"{name}_sheet.png")

    metadata["prompt"] = prompt
    metadata["category"] = category
    metadata["name"] = name
    metadata["target_size"] = list(target_size)
    metadata["palette_colors"] = n_colors

    with open(sprite_dir / f"{name}_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"[5/5] Spritesheet: {sprite_dir / f'{name}_sheet.png'}")
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
    parser = argparse.ArgumentParser(description="Sprite generation pipeline")
    parser.add_argument("category", choices=["character", "object", "texture", "batch"],
                        help="Asset category or 'batch' for JSON file")
    parser.add_argument("prompt", help="Text prompt or batch JSON file path")
    parser.add_argument("--name", default="sprite", help="Output name prefix")
    parser.add_argument("--variations", "-n", type=int, default=4)
    parser.add_argument("--size", type=int, default=64, help="Target sprite size (square)")
    parser.add_argument("--colors", type=int, default=16, help="Palette color count")
    parser.add_argument("--steps", type=int, default=4, help="Diffusion steps (1-4)")
    parser.add_argument("--gen-size", type=int, default=512, help="Generation resolution")
    parser.add_argument("--bg", choices=["corners", "threshold", "chroma"], default="corners")
    args = parser.parse_args()

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
