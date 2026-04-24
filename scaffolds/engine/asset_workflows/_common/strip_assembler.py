"""Post-processor: base_plus_chain output → canonical horizontal strip.

After `base_plus_chain.run_payload` writes `frame_000.png` ... `frame_00N.png`
+ `manifest.json`, this tool assembles them into a single N×1 strip PNG
ready for engine consumption via the existing sprite-loader.

The strip follows the conventions the engine's runtime loader expects:
  - Horizontal N×1, no gutter
  - Uniform cell_size = max(w) × max(h) across input frames
  - Smaller frames centered in their cell with transparent padding
  - Companion `<name>.manifest.json` records cell coords + frame labels

Usage:
    # single payload
    python3 strip_assembler.py path/to/bpc/1981_galaga/player_explosion/

    # batch over all bpc output dirs
    python3 strip_assembler.py ./out/bpc/ --recurse

    # dry-run prints plan only
    python3 strip_assembler.py ./out/bpc/ --recurse --dry-run

Idempotent: if `<name>.strip.png` exists + is newer than any
`frame_*.png`, skips the payload. Pass `--force` to re-assemble.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from sprite_sheet_asm import (
    assemble_strip, write_manifest,
)


def _payload_dir_is_ready(d: Path) -> bool:
    """A directory is ready for strip assembly when it has at least
    one `frame_*.png` + a `manifest.json` from base_plus_chain."""
    frames = list(d.glob("frame_*.png"))
    manifest = d / "manifest.json"
    return len(frames) >= 1 and manifest.is_file()


def _strip_is_current(d: Path, frames: list[Path]) -> bool:
    """True when <name>.strip.png exists + is newer than any frame_*.png."""
    strip = d / "strip.png"
    if not strip.is_file():
        return False
    strip_mtime = strip.stat().st_mtime
    return all(f.stat().st_mtime < strip_mtime for f in frames)


def assemble_one(payload_dir: Path, dry_run: bool = True, force: bool = False) -> str:
    """Assemble one payload's frames into a strip. Returns a disposition
    string: 'assembled' | 'cached' | 'skipped' | 'error:<msg>'."""
    if not _payload_dir_is_ready(payload_dir):
        return "skipped"  # no frames or no manifest

    frames = sorted(payload_dir.glob("frame_*.png"))
    if not frames:
        return "skipped"

    if not force and _strip_is_current(payload_dir, frames):
        return "cached"

    if dry_run:
        print(f"  would assemble {len(frames)} frames → {payload_dir / 'strip.png'}")
        return "dry-run"

    # Load the base_plus_chain manifest for labels
    bpc_manifest_path = payload_dir / "manifest.json"
    try:
        bpc_manifest = json.loads(bpc_manifest_path.read_text())
    except Exception:
        bpc_manifest = {}

    labels: list[str] = []
    for i, f in enumerate(frames):
        if i == 0:
            labels.append("base")
        else:
            # Use the nudge delta as the label (truncated)
            nudges = bpc_manifest.get("nudges_used", [])
            if i - 1 < len(nudges):
                labels.append(nudges[i - 1]["delta"][:40])
            else:
                labels.append(f"frame_{i:03d}")

    try:
        sheet, sheet_manifest = assemble_strip(frames, labels=labels)
    except Exception as e:
        return f"error:{e}"

    strip_path = payload_dir / "strip.png"
    sheet.save(strip_path)
    write_manifest(sheet_manifest, payload_dir / "strip.manifest.json")
    return "assembled"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", type=Path,
                    help="payload dir (single) OR parent (with --recurse)")
    ap.add_argument("--recurse", action="store_true",
                    help="treat target as parent of payload dirs, walk 2 levels")
    ap.add_argument("--dry-run", action="store_true", default=False)
    ap.add_argument("--force", action="store_true",
                    help="re-assemble even if strip.png is already current")
    args = ap.parse_args()

    if not args.target.is_dir():
        print(f"ERROR: {args.target} not a directory", file=sys.stderr)
        return 1

    # Discover payload dirs. `--recurse` walks 2 levels: out/<essence>/<anim>/
    if args.recurse:
        payload_dirs = []
        for essence_dir in sorted(args.target.iterdir()):
            if not essence_dir.is_dir():
                continue
            for anim_dir in sorted(essence_dir.iterdir()):
                if anim_dir.is_dir() and _payload_dir_is_ready(anim_dir):
                    payload_dirs.append(anim_dir)
    else:
        payload_dirs = [args.target] if _payload_dir_is_ready(args.target) else []

    if not payload_dirs:
        print(f"No ready payload dirs under {args.target}")
        print(f"  (a ready dir has ≥1 frame_*.png + manifest.json)")
        return 0

    print(f"Processing {len(payload_dirs)} payload dir(s)")
    t0 = time.time()
    dispositions: dict[str, int] = {}
    errors: list[tuple[Path, str]] = []
    for d in payload_dirs:
        rel = d.relative_to(args.target) if args.recurse else d.name
        print(f"[{rel}]", end=" ")
        d_str = assemble_one(d, dry_run=args.dry_run, force=args.force)
        dispositions[d_str] = dispositions.get(d_str, 0) + 1
        if d_str.startswith("error:"):
            errors.append((d, d_str[6:]))
            print("ERROR", d_str[6:])
        else:
            print(d_str)

    elapsed = time.time() - t0
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"\n=== {mode} — {elapsed:.1f}s ===")
    for d, n in sorted(dispositions.items()):
        print(f"  {d}: {n}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for p, e in errors[:5]:
            print(f"  {p}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
