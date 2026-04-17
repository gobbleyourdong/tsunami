"""Implementations for the 17 v1.1 post-process ops.

Each function takes `(image_or_list, context)` and returns the
transformed image (or list, for splitters/collectors). Registered at
import via `register_op(name, fn)` — sprite_ops imports this module
for its side effects.

Ops fall into groups:
  - Ported from sprite_pipeline.py — pixel_extract, isolate_largest,
    trim_transparent, center_crop_object, quantize_palette,
    pixel_snap, normalize_height
  - Tileset — grid_cut, seamless_check, pack_spritesheet
  - Background — horizontal_tileable_fix
  - UI — flat_color_quantize
  - Effect — radial_alpha_cleanup, preserve_fragmentation,
    additive_blend_tag
  - Portrait — eye_center, head_only_crop
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from sprite_ops import PipelineContext, register_op

# pixel_extract is shared with tsunami/tools — import via the same
# path insert sprite_pipeline uses.
_TOOLS = Path(__file__).resolve().parents[3] / "tsunami" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
from pixel_extract import snap as _pixel_extract_snap  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# Ported ops (sprite_pipeline.py → per-op factoring)
# ═══════════════════════════════════════════════════════════════════

def op_pixel_extract(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    """Perceptual-Lab background removal + native-grid recovery +
    edge-fringe cleanup, via tsunami's shared pixel_extract.snap.
    Replaces the old multi-step bg-removal + quantize chain."""
    return _pixel_extract_snap(img)


def op_isolate_largest(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    from scipy import ndimage
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    opaque = arr[:, :, 3] > 128
    if not opaque.any():
        return img
    labeled, n = ndimage.label(opaque)
    if n <= 1:
        return img
    sizes = ndimage.sum(opaque, labeled, range(1, n + 1))
    largest = np.argmax(sizes) + 1
    arr[labeled != largest, 3] = 0
    return Image.fromarray(arr)


def op_trim_transparent(img: Image.Image, ctx: PipelineContext,
                        padding: int = 1) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any() or not cols.any():
        return img
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    rmin = max(0, rmin - padding)
    rmax = min(arr.shape[0] - 1, rmax + padding)
    cmin = max(0, cmin - padding)
    cmax = min(arr.shape[1] - 1, cmax + padding)
    return img.crop((cmin, rmin, cmax + 1, rmax + 1))


def op_center_crop_object(img: Image.Image, ctx: PipelineContext,
                          crop_ratio: float = 0.55) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    mx = int(w * (1 - crop_ratio) / 2)
    my = int(h * (1 - crop_ratio) / 2)
    return img.crop((mx, my, w - mx, h - my))


def op_quantize_palette(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    n = ctx.palette_colors or 16
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    rgb = img.convert("RGB")
    quantized = rgb.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    result = np.array(quantized.convert("RGBA"))
    result[:, :, 3] = alpha
    return Image.fromarray(result)


def op_pixel_snap(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    target = ctx.target_size or (64, 64)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img.resize(target, Image.Resampling.NEAREST)


def op_normalize_height(img: Image.Image, ctx: PipelineContext,
                        target_height: int | None = None) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    th = target_height or (ctx.target_size or (64, 64))[1]
    w, h = img.size
    if h == 0:
        return img
    scale = th / h
    new_w = max(1, int(w * scale))
    return img.resize((new_w, th), Image.Resampling.NEAREST)


# ═══════════════════════════════════════════════════════════════════
# Tileset ops
# ═══════════════════════════════════════════════════════════════════

def op_grid_cut(img: Image.Image, ctx: PipelineContext) -> list[Image.Image]:
    """Split a grid-layout tilesheet into N tiles. Uses
    metadata.tile_grid_w/h to know the grid shape. If the gen used a
    magenta gutter between tiles it's already been removed by earlier
    bg-cleanup ops; here we slice on geometric grid lines."""
    gw = int(ctx.metadata.get("tile_grid_w") or 4)
    gh = int(ctx.metadata.get("tile_grid_h") or 4)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    tw = w // gw
    th = h // gh
    tiles: list[Image.Image] = []
    for row in range(gh):
        for col in range(gw):
            x0, y0 = col * tw, row * th
            tiles.append(img.crop((x0, y0, x0 + tw, y0 + th)))
    # Stamp geometric info for pack_spritesheet.
    ctx.metadata_updates.setdefault("tile_width", tw)
    ctx.metadata_updates.setdefault("tile_height", th)
    ctx.metadata_updates.setdefault("columns", gw)
    ctx.metadata_updates.setdefault("rows", gh)
    return tiles


def op_seamless_check(
    tile: Image.Image, ctx: PipelineContext,
) -> Image.Image:
    """Annotate one tile with seamless_h / seamless_v booleans.
    Runs per-tile inside a splitter fan-out; results accumulate into
    ctx.metadata_updates['per_tile_seamless'] in call order. The tile
    image is returned unchanged — pack_spritesheet consumes the flags
    when it writes the atlas JSON."""
    arr = np.array(tile.convert("RGBA"))
    left = arr[:, 0, :3].astype(float)
    right = arr[:, -1, :3].astype(float)
    top = arr[0, :, :3].astype(float)
    bottom = arr[-1, :, :3].astype(float)
    # Threshold: mean channel distance < 12 counts as seamless —
    # the gen's palette quantize caps normal edge drift around this.
    h_dist = float(np.mean(np.abs(left - right)))
    v_dist = float(np.mean(np.abs(top - bottom)))
    ctx.metadata_updates.setdefault("per_tile_seamless", []).append({
        "seamless_h": h_dist < 12,
        "seamless_v": v_dist < 12,
        "h_edge_dist": round(h_dist, 2),
        "v_edge_dist": round(v_dist, 2),
    })
    return tile


def op_pack_spritesheet(
    tiles: list[Image.Image], ctx: PipelineContext,
) -> Image.Image:
    """Assemble tiles back into a single spritesheet image + write an
    atlas dict into ctx.atlas. Uses the grid shape stamped by grid_cut
    (cols × rows)."""
    if not tiles:
        raise ValueError("pack_spritesheet: empty tile list")
    cols = int(ctx.metadata_updates.get("columns")
               or ctx.metadata.get("tile_grid_w") or 4)
    rows = int(ctx.metadata_updates.get("rows")
               or ctx.metadata.get("tile_grid_h") or 4)
    tw = int(ctx.metadata_updates.get("tile_width") or tiles[0].size[0])
    th = int(ctx.metadata_updates.get("tile_height") or tiles[0].size[1])

    sheet = Image.new("RGBA", (tw * cols, th * rows), (0, 0, 0, 0))
    tile_entries: list[dict[str, Any]] = []
    per_tile = ctx.metadata_updates.get("per_tile_seamless") or [{}] * len(tiles)

    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        if tile.size != (tw, th):
            tile = tile.resize((tw, th), Image.Resampling.NEAREST)
        sheet.paste(tile, (c * tw, r * th))
        entry: dict[str, Any] = {
            "id": f"{ctx.asset_id or 'tile'}_{i:02d}",
            "x": c * tw, "y": r * th,
            "row": r, "col": c,
        }
        if i < len(per_tile):
            for k in ("seamless_h", "seamless_v"):
                if k in per_tile[i]:
                    entry[k] = per_tile[i][k]
        tile_entries.append(entry)

    ctx.atlas = {
        "schema_version": "1",
        "sheet": f"{ctx.asset_id or 'tileset'}_sheet.png",
        "tile_width": tw, "tile_height": th,
        "columns": cols, "rows": rows, "tile_count": len(tiles),
        "tiles": tile_entries,
    }
    ctx.metadata_updates["atlas_tile_count"] = len(tiles)
    return sheet


# ═══════════════════════════════════════════════════════════════════
# Background
# ═══════════════════════════════════════════════════════════════════

def op_horizontal_tileable_fix(
    img: Image.Image, ctx: PipelineContext,
    blend_px: int = 32,
) -> Image.Image:
    """Blend left + right edges so the background tiles horizontally
    without a visible seam. Cheap alpha-ramp crossfade between the
    first and last `blend_px` columns. No math magic; works well for
    soft/atmospheric backgrounds (sky, dunes, forests)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img).astype(float)
    h, w, _ = arr.shape
    if w <= 2 * blend_px:
        return img
    ramp = np.linspace(0.0, 1.0, blend_px).reshape(1, blend_px, 1)
    left = arr[:, :blend_px, :].copy()
    right = arr[:, -blend_px:, :].copy()
    blended = left * (1 - ramp) + right * ramp
    arr[:, :blend_px, :] = blended
    arr[:, -blend_px:, :] = blended
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


# ═══════════════════════════════════════════════════════════════════
# UI element
# ═══════════════════════════════════════════════════════════════════

def op_flat_color_quantize(
    img: Image.Image, ctx: PipelineContext,
    n_colors: int = 8,
) -> Image.Image:
    """UI elements benefit from aggressive palette reduction — flat
    color is the whole point. Uses FASTOCTREE which preserves solid
    regions better than MEDIANCUT for synthetic graphics."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    rgb = img.convert("RGB").quantize(
        colors=n_colors, method=Image.Quantize.FASTOCTREE,
    )
    result = np.array(rgb.convert("RGBA"))
    result[:, :, 3] = alpha
    return Image.fromarray(result)


# ═══════════════════════════════════════════════════════════════════
# Effect
# ═══════════════════════════════════════════════════════════════════

def op_radial_alpha_cleanup(
    img: Image.Image, ctx: PipelineContext,
) -> Image.Image:
    """Effect sprites (explosions, glows, bursts) should radial-falloff
    into transparency from center outward. Multiply existing alpha by a
    radial ramp so edges fade cleanly even if the gen left sharp
    boundaries."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img).astype(float)
    h, w, _ = arr.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    cy, cx = h / 2, w / 2
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    rmax = np.sqrt(cx ** 2 + cy ** 2)
    falloff = np.clip(1.0 - (r / rmax) ** 2, 0.0, 1.0)
    arr[:, :, 3] = arr[:, :, 3] * falloff
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def op_preserve_fragmentation(
    img: Image.Image, ctx: PipelineContext,
) -> Image.Image:
    """Effect sprites often WANT fragmentation — sparks, debris, dust.
    This is a no-op on the image itself but stamps a metadata flag so
    the scorer doesn't penalize fragmentation on this category. Kept
    as an explicit op for chain readability / future-proofing."""
    ctx.metadata_updates["preserve_fragmentation"] = True
    return img


def op_additive_blend_tag(
    img: Image.Image, ctx: PipelineContext,
) -> Image.Image:
    """Mark the sprite as additive-blend at runtime. Side-effect op:
    emits composite_mode into metadata; image untouched."""
    ctx.metadata_updates["composite_mode"] = "add"
    return img


# ═══════════════════════════════════════════════════════════════════
# Portrait
# ═══════════════════════════════════════════════════════════════════

def op_eye_center(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    """Center the portrait so the eye-line sits at ~40% from the top
    (classical portrait composition). We approximate the eye-line
    from the opaque region's bounding box — top third of the opaque
    area — and shift the image vertically to land at 0.4h."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    if not rows.any():
        return img
    opaque_rows = np.where(rows)[0]
    r_min, r_max = int(opaque_rows[0]), int(opaque_rows[-1])
    eye_line_approx = r_min + (r_max - r_min) // 3  # top-third heuristic
    target_y = int(h * 0.4)
    shift = target_y - eye_line_approx
    if shift == 0:
        return img
    shifted = np.zeros_like(arr)
    if shift > 0:
        shifted[shift:, :, :] = arr[: h - shift, :, :]
    else:
        shifted[: h + shift, :, :] = arr[-shift:, :, :]
    return Image.fromarray(shifted)


def op_head_only_crop(img: Image.Image, ctx: PipelineContext) -> Image.Image:
    """Crop to the top ~65% of the opaque bounding box — for portrait
    category, discarding torso/body so the sprite is head+shoulders."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any() or not cols.any():
        return img
    r_min, r_max = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
    c_min, c_max = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
    head_bottom = r_min + int((r_max - r_min) * 0.65)
    return img.crop((c_min, r_min, c_max + 1, head_bottom + 1))


# ═══════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════

register_op("pixel_extract",           op_pixel_extract)
register_op("isolate_largest",         op_isolate_largest)
register_op("trim_transparent",        op_trim_transparent)
register_op("center_crop_object",      op_center_crop_object)
register_op("quantize_palette",        op_quantize_palette)
register_op("pixel_snap",              op_pixel_snap)
register_op("normalize_height",        op_normalize_height)
register_op("grid_cut",                op_grid_cut)
register_op("seamless_check",          op_seamless_check)
register_op("pack_spritesheet",        op_pack_spritesheet)
register_op("horizontal_tileable_fix", op_horizontal_tileable_fix)
register_op("flat_color_quantize",     op_flat_color_quantize)
register_op("radial_alpha_cleanup",    op_radial_alpha_cleanup)
register_op("preserve_fragmentation",  op_preserve_fragmentation)
register_op("additive_blend_tag",      op_additive_blend_tag)
register_op("eye_center",              op_eye_center)
register_op("head_only_crop",          op_head_only_crop)
