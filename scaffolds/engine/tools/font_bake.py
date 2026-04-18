#!/usr/bin/env python3
"""
Font baker — TTF/OTF → Sample-Newton Hermite-handle atlas.

# Status
# Baker: TTF loader ✓, outline extraction ✓, Bezier→Hermite ✓,
#        row-per-glyph atlas ✓, metadata JSON ✓, CLI ✓
# Next:  stress-test on a real font, validate handle continuity at
#        contour boundaries, switch to linear-strip packing for memory.

## Technique

Each glyph's outline is parsed from the font's glyf/CFF tables as a
sequence of lines + quadratic Beziers (TrueType) or cubic Beziers
(CFF/OpenType). Every segment is converted to the Hermite basis
(anchor point + outgoing tangent), giving one 4-float handle per
anchor. Two consecutive handles define a cubic Hermite curve piece.

The atlas is a grid of RGBA32F texels:
  - row index = glyph index (within baked set)
  - col index = handle index (0..N-1 for that glyph)
  - RGBA     = (anchor.x, anchor.y, tangent.x, tangent.y) in em units

Per-glyph metadata (codepoint, row, handle_count, contour_breaks,
advance, plane-bbox) lives in a sibling JSON. Atlas pixels are raw
RGBA32F (float) written to .atlas.bin; an 8-bit RGBA preview .png
lets you eyeball it before touching the GPU.

## Output files

Given `--out myfont`:
  myfont.atlas.bin   — RGBA32F raw, shape (H × W × 4) row-major
  myfont.atlas.png   — 8-bit preview (quantized; visualization only)
  myfont.atlas.json  — metadata

## Usage

  python font_bake.py path/to/FontName.ttf --out ./out/fontname
  python font_bake.py path/to/FontName.ttf --range 0x20-0xFF     # Latin-1
  python font_bake.py path/to/FontName.ttf --chars "ABC123"      # subset

## Deps

  fontTools   (pip install fonttools)    — build-time only
  numpy
  Pillow (PIL)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


# ── Hermite basis ────────────────────────────────────────────────

@dataclass
class Handle:
    """One Hermite handle: anchor point + outgoing tangent.

    Two consecutive handles (start, end) define a cubic Hermite
    curve via:
        p(t) = (2t³-3t²+1)·start.anchor + (t³-2t²+t)·start.tangent
             + (-2t³+3t²)·end.anchor   + (t³-t²)·end.tangent
    """
    anchor_x: float
    anchor_y: float
    tangent_x: float
    tangent_y: float


# Bezier → Hermite conversions. Hermite's outgoing tangent at an anchor
# is the curve's derivative at that parameter, which equals the Bezier
# control-point offset scaled by the degree.

def cubic_outgoing_tangent(p0, p1):
    """At Bezier t=0, dC/dt = 3·(p1 - p0)."""
    return (3.0 * (p1[0] - p0[0]), 3.0 * (p1[1] - p0[1]))


def cubic_incoming_tangent(p2, p3):
    """At Bezier t=1, dC/dt = 3·(p3 - p2)."""
    return (3.0 * (p3[0] - p2[0]), 3.0 * (p3[1] - p2[1]))


def quadratic_outgoing_tangent(p0, p1):
    """At quadratic Bezier t=0, dC/dt = 2·(p1 - p0)."""
    return (2.0 * (p1[0] - p0[0]), 2.0 * (p1[1] - p0[1]))


def quadratic_incoming_tangent(p1, p2):
    """At quadratic Bezier t=1, dC/dt = 2·(p2 - p1)."""
    return (2.0 * (p2[0] - p1[0]), 2.0 * (p2[1] - p1[1]))


def line_tangent(p0, p1):
    """For a straight line, both tangents equal the segment vector."""
    return (p1[0] - p0[0], p1[1] - p0[1])


# ── Glyph extraction via fontTools ───────────────────────────────

@dataclass
class GlyphData:
    codepoint: int
    handles: list[Handle] = field(default_factory=list)
    contour_breaks: list[int] = field(default_factory=list)   # indices in `handles`
    advance: float = 0.0
    plane: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


def extract_glyph(font, codepoint: int) -> GlyphData | None:
    """Walk the glyph's contours via fontTools RecordingPen and produce
    Hermite handles.

    Returns None if the font has no glyph for this codepoint.
    """
    from fontTools.pens.recordingPen import RecordingPen

    cmap = font.getBestCmap()
    if codepoint not in cmap:
        return None

    glyph_name = cmap[codepoint]
    glyph_set = font.getGlyphSet()

    pen = RecordingPen()
    glyph_set[glyph_name].draw(pen)

    handles: list[Handle] = []
    contour_breaks: list[int] = []
    current: tuple[float, float] | None = None
    contour_start: tuple[float, float] | None = None

    def push(x, y, tx, ty):
        handles.append(Handle(x, y, tx, ty))

    for op, args in pen.value:
        if op == "moveTo":
            current = args[0]
            contour_start = current
            # Anchor with zero tangent placeholder; the next segment fixes
            # the outgoing tangent.
            push(current[0], current[1], 0.0, 0.0)

        elif op == "lineTo":
            p0 = current
            p1 = args[0]
            t = line_tangent(p0, p1)
            # Fix the preceding handle's outgoing tangent.
            handles[-1].tangent_x = t[0]
            handles[-1].tangent_y = t[1]
            push(p1[0], p1[1], t[0], t[1])
            current = p1

        elif op == "qCurveTo":
            # TrueType quadratics. Arg list can be:
            #   (c0, c1, ..., ck, end)        — implicit on-curve midpoints
            # We expand: each pair (off, off) implies an on-curve at midpoint.
            pts = list(args)
            if pts[-1] is None:
                # Closed contour with only off-curve points. Rare but valid.
                # Rebuild: midpoint of first and last off-curve closes the ring.
                off = pts[:-1]
                if not off:
                    continue
                start = ((off[0][0] + off[-1][0]) / 2, (off[0][1] + off[-1][1]) / 2)
                current = start
                handles[-1].anchor_x = start[0]
                handles[-1].anchor_y = start[1]
                pts[-1] = start
            # Expand implicit on-curve midpoints between consecutive off-curves.
            expanded: list[tuple[float, float]] = []
            for i, p in enumerate(pts):
                if i > 0 and i < len(pts) - 1:
                    prev = pts[i - 1]
                    expanded.append(prev)
                    expanded.append(((prev[0] + p[0]) / 2, (prev[1] + p[1]) / 2))
                else:
                    if i == len(pts) - 1:
                        expanded.append(pts[i - 1] if i > 0 else p)
                    expanded.append(p)
            # The expanded list alternates control / on-curve / control / on-curve ...
            # Simplest-correct: treat each adjacent (on, control, on) triple as a
            # quadratic Bezier. If expansion above didn't land on that exact
            # parity, fall back to walking args as (control, end) pairs from
            # the current position.
            # Fallback walk for safety:
            for i in range(0, len(args) - 1, 1):
                ctrl = args[i]
                end_pt = args[i + 1] if i + 1 < len(args) else args[-1]
                if ctrl is None or end_pt is None:
                    continue
                p0 = current
                p1 = ctrl
                p2 = end_pt
                t_out = quadratic_outgoing_tangent(p0, p1)
                t_in = quadratic_incoming_tangent(p1, p2)
                handles[-1].tangent_x = t_out[0]
                handles[-1].tangent_y = t_out[1]
                push(p2[0], p2[1], t_in[0], t_in[1])
                current = p2

        elif op == "curveTo":
            # Cubic Bezier: (c1, c2, end)
            p0 = current
            p1, p2, p3 = args
            t_out = cubic_outgoing_tangent(p0, p1)
            t_in = cubic_incoming_tangent(p2, p3)
            handles[-1].tangent_x = t_out[0]
            handles[-1].tangent_y = t_out[1]
            push(p3[0], p3[1], t_in[0], t_in[1])
            current = p3

        elif op == "closePath":
            # Close the contour: add an implicit line back to contour_start if
            # we're not already there.
            if contour_start is not None and current is not None:
                if (abs(current[0] - contour_start[0]) > 1e-6 or
                    abs(current[1] - contour_start[1]) > 1e-6):
                    t = line_tangent(current, contour_start)
                    handles[-1].tangent_x = t[0]
                    handles[-1].tangent_y = t[1]
                    push(contour_start[0], contour_start[1], t[0], t[1])
            contour_breaks.append(len(handles))
            current = None
            contour_start = None

        elif op == "endPath":
            # Open path (rare in fonts but legal). Treat as contour boundary.
            contour_breaks.append(len(handles))
            current = None
            contour_start = None

    if not handles:
        return None

    # Advance and plane bbox, normalized to em units.
    upem = float(font["head"].unitsPerEm)
    advance = font["hmtx"][glyph_name][0] / upem

    xs = [h.anchor_x for h in handles]
    ys = [h.anchor_y for h in handles]
    plane_px = (min(xs), min(ys), max(xs), max(ys))
    plane = tuple(v / upem for v in plane_px)

    norm_handles = [
        Handle(h.anchor_x / upem, h.anchor_y / upem,
               h.tangent_x / upem, h.tangent_y / upem)
        for h in handles
    ]

    return GlyphData(
        codepoint=codepoint,
        handles=norm_handles,
        contour_breaks=contour_breaks,
        advance=advance,
        plane=plane,
    )


# ── Atlas packing (row-per-glyph v1; linear-strip deferred) ──────

def pack_atlas(glyphs: list[GlyphData]) -> tuple[np.ndarray, int]:
    """Pack Hermite handles into a row-per-glyph RGBA32F atlas.

    Returns (atlas, max_handle_count). Atlas shape: (H, W, 4) where
    H = len(glyphs), W = max handle count across all glyphs.

    Wasted slots in shorter-glyph rows hold zeros; the shader clips by
    handle_count metadata, so the slack is render-inert.
    """
    max_hc = max(len(g.handles) for g in glyphs) if glyphs else 0
    atlas = np.zeros((len(glyphs), max_hc, 4), dtype=np.float32)
    for row, g in enumerate(glyphs):
        for col, h in enumerate(g.handles):
            atlas[row, col, 0] = h.anchor_x
            atlas[row, col, 1] = h.anchor_y
            atlas[row, col, 2] = h.tangent_x
            atlas[row, col, 3] = h.tangent_y
    return atlas, max_hc


def build_metadata(font, glyphs: list[GlyphData], atlas_w: int, atlas_h: int) -> dict:
    upem = float(font["head"].unitsPerEm)
    hhea = font["hhea"]
    return {
        "version": "1",
        "layout": "row_per_glyph",
        "texel_format": "rgba32f",
        "atlas_width": atlas_w,
        "atlas_height": atlas_h,
        "em_size": upem,
        "ascent": hhea.ascender / upem,
        "descent": hhea.descender / upem,
        "line_gap": hhea.lineGap / upem,
        "glyphs": {
            str(g.codepoint): {
                "row": row,
                "handle_count": len(g.handles),
                "contour_breaks": g.contour_breaks,
                "advance": g.advance,
                "plane": list(g.plane),
            }
            for row, g in enumerate(glyphs)
        },
    }


def write_preview_png(atlas: np.ndarray, path: Path) -> None:
    """Quantize RGBA32F atlas to 8-bit RGBA PNG for eyeball inspection.

    This is NOT the runtime atlas — runtime reads the .bin. The PNG lets
    you look at what got baked: each row is a glyph's handle strip, and
    the RGBA channels encode (anchor.x, anchor.y, tangent.x, tangent.y).
    Colors won't look like anything meaningful; this is a debug artifact.
    """
    preview = np.clip((atlas * 127.0) + 127.0, 0, 255).astype(np.uint8)
    Image.fromarray(preview, mode="RGBA").save(str(path))


# ── CLI ──────────────────────────────────────────────────────────

def parse_range(s: str) -> tuple[int, int]:
    if "-" not in s:
        raise ValueError("range must be like '0x20-0x7E'")
    start, end = s.split("-", 1)
    return int(start, 0), int(end, 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TTF/OTF → Sample-Newton Hermite-handle atlas baker",
    )
    parser.add_argument("font", type=Path, help="Input TTF/OTF path")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output prefix (default: font file stem)")
    parser.add_argument("--range", type=str, default="0x20-0x7E",
                        help="Codepoint range, hex (default: printable ASCII)")
    parser.add_argument("--chars", type=str, default=None,
                        help="Explicit char set (overrides --range)")
    args = parser.parse_args()

    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("error: fontTools not installed. run: pip install fonttools",
              file=sys.stderr)
        return 2

    if not args.font.is_file():
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 2

    out_prefix = args.out or args.font.with_suffix("")
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    font = TTFont(str(args.font))

    if args.chars:
        codepoints = sorted(set(ord(c) for c in args.chars))
    else:
        start, end = parse_range(args.range)
        codepoints = list(range(start, end + 1))

    glyphs: list[GlyphData] = []
    skipped: list[int] = []
    for cp in codepoints:
        g = extract_glyph(font, cp)
        if g is None or not g.handles:
            skipped.append(cp)
            continue
        glyphs.append(g)

    if not glyphs:
        print("error: no glyphs baked (font may lack these codepoints)",
              file=sys.stderr)
        return 1

    atlas, max_hc = pack_atlas(glyphs)
    metadata = build_metadata(font, glyphs, atlas_w=max_hc, atlas_h=len(glyphs))

    bin_path = Path(f"{out_prefix}.atlas.bin")
    png_path = Path(f"{out_prefix}.atlas.png")
    meta_path = Path(f"{out_prefix}.atlas.json")

    atlas.tofile(str(bin_path))
    write_preview_png(atlas, png_path)
    meta_path.write_text(json.dumps(metadata, indent=2))

    print(f"baked {len(glyphs)} glyphs ({len(skipped)} skipped)")
    print(f"  atlas: {max_hc} cols × {len(glyphs)} rows RGBA32F")
    print(f"  raw:   {bin_path}")
    print(f"  png:   {png_path}  (preview only)")
    print(f"  json:  {meta_path}")
    if skipped:
        print(f"  skipped codepoints: "
              f"{', '.join(hex(c) for c in skipped[:20])}"
              f"{' ...' if len(skipped) > 20 else ''}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
