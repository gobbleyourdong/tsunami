"""ERNIE-base + Qwen-chain orchestrator.

Given a nudge payload from `scaffolds/.claude/nudges/<essence>/<anim>.json`,
this module:

  1. Fires ERNIE `/v1/images/generate` with payload.base_prompt → frame_0
  2. If `needs_animation`: fires Qwen-Image-Edit `/v1/images/animate`
     with frame_0 as input + payload.nudges → frames 1..N-1
  3. Assembles the N-frame strip via sprite_sheet_asm.assemble_strip
  4. Emits an output manifest with frame paths + timing

Static sprites (needs_animation: false) skip step 2 — ERNIE output is
the deliverable.

No ERNIE/Qwen calls when run with `--dry-run` — only prints the plan.
When servers are up: `--apply` writes actual sprites to
`<workflow_out>/<essence>/<anim_name>/`.

Usage as a module:
    from base_plus_chain import run_payload
    result = run_payload(payload_dict, out_dir=Path('./out'), dry_run=True)

Usage as a CLI:
    python3 base_plus_chain.py path/to/nudge.json --dry-run
    python3 base_plus_chain.py path/to/nudge.json --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Deferred imports — requests is only needed for actual fires
try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None

ERNIE_URL = os.environ.get("ERNIE_URL", "http://localhost:8092")
QWEN_EDIT_URL = os.environ.get("QWEN_EDIT_URL", "http://localhost:8094")


@dataclass
class RunResult:
    """Outcome of a single payload run."""
    payload_id: str
    disposition: str              # "static" | "animated" | "dry-run" | "error"
    base_path: Optional[Path]
    frame_paths: list[Path]
    manifest_path: Optional[Path]
    error: Optional[str]
    elapsed_s: float


def _seed_label_to_int(label: str) -> int:
    return int(hashlib.sha256(label.encode()).hexdigest()[:8], 16)


def _fire_ernie_base(
    base_prompt: str, seed_label: str,
    save_path: Path, model_kind: str = "Base",
    steps: int = 50, cfg: float = 4.0,
) -> dict:
    """Fire one ERNIE `/v1/images/generate` call. Raises on failure."""
    if requests is None:
        raise RuntimeError("requests not installed — can't fire ERNIE")
    body = {
        "prompt": base_prompt,
        "negative_prompt": "text, words, UI, HUD, 3D rendering, anti-aliasing, drop shadow",
        "height": 1024,
        "width": 1024,
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "seed": _seed_label_to_int(seed_label),
        "n": 1,
        "response_format": "save_path",
        "save_path": str(save_path.absolute()),
        "use_pe": False,
        "model_kind": model_kind,
    }
    r = requests.post(f"{ERNIE_URL}/v1/images/generate", json=body, timeout=600)
    r.raise_for_status()
    return r.json()


def _fire_qwen_animate(
    base_path: Path, nudges: list[dict], save_dir: Path,
    seed_label: str,
) -> dict:
    """Fire one Qwen-Image-Edit `/v1/images/animate` chain. Returns a
    response dict with frame save_paths. Raises on failure."""
    if requests is None:
        raise RuntimeError("requests not installed — can't fire Qwen")
    body = {
        "path": str(base_path.absolute()),
        "nudges": [
            {
                "delta": n["delta"],
                "strength": n.get("strength", 0.4),
                "num_inference_steps": 20,
                "guidance_scale": 4.0,
            }
            for n in nudges
        ],
        "negative_prompt": "text, UI, 3D rendering",
        "seed": _seed_label_to_int(seed_label + "_qwen"),
        "response_format": "save_path",
        "save_dir": str(save_dir.absolute()),
    }
    r = requests.post(f"{QWEN_EDIT_URL}/v1/images/animate", json=body, timeout=3600)
    r.raise_for_status()
    return r.json()


def run_payload(
    payload: dict, out_dir: Path,
    dry_run: bool = True,
) -> RunResult:
    """Orchestrate one nudge-payload run. Safe to call with dry_run=True
    at any time (no network I/O)."""
    t0 = time.time()
    payload_id = f"{payload['essence']}/{payload['animation_name']}"
    target_dir = out_dir / payload["essence"] / payload["animation_name"]

    base_path = target_dir / "frame_000.png"
    needs_anim = payload.get("needs_animation", False)
    nudges = payload.get("nudges", [])

    # Idempotent: if base exists AND all frames exist (or static), skip work.
    if base_path.exists() and (not needs_anim or _all_frames_exist(target_dir, len(nudges))):
        return RunResult(
            payload_id=payload_id,
            disposition="cached",
            base_path=base_path,
            frame_paths=_collect_frames(target_dir),
            manifest_path=target_dir / "manifest.json",
            error=None,
            elapsed_s=time.time() - t0,
        )

    if dry_run:
        plan_lines = [f"DRY-RUN plan for {payload_id}:"]
        plan_lines.append(f"  target dir:  {target_dir}")
        plan_lines.append(f"  base_prompt: {payload['base_prompt'][:120]}...")
        plan_lines.append(f"  seed_label:  {payload['base_seed_label']}")
        plan_lines.append(f"  ERNIE call → {base_path.name}")
        if needs_anim and nudges:
            plan_lines.append(f"  Qwen animate chain of {len(nudges)} nudges:")
            for i, n in enumerate(nudges):
                plan_lines.append(f"    nudge {i+1}: strength={n['strength']:.2f}  delta={n['delta'][:80]}")
        elif needs_anim and not nudges:
            plan_lines.append(f"  ⚠️  needs_animation=true but ZERO nudges parsed — skip Qwen, static only")
        else:
            plan_lines.append(f"  static sprite — no Qwen chain")
        for line in plan_lines:
            print(line)
        return RunResult(
            payload_id=payload_id,
            disposition="dry-run",
            base_path=base_path,
            frame_paths=[base_path] if not needs_anim else [],
            manifest_path=None,
            error=None,
            elapsed_s=time.time() - t0,
        )

    # Live run
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Step 1: ERNIE base
        print(f"[{payload_id}] firing ERNIE base ({payload['base_seed_label']})...")
        _fire_ernie_base(
            base_prompt=payload["base_prompt"],
            seed_label=payload["base_seed_label"],
            save_path=base_path,
        )
        if not base_path.exists():
            raise RuntimeError(f"ERNIE claimed success but {base_path} missing")
        print(f"  → {base_path.name}")
    except Exception as e:
        return RunResult(
            payload_id=payload_id, disposition="error", base_path=None,
            frame_paths=[], manifest_path=None, error=f"ERNIE: {e}",
            elapsed_s=time.time() - t0,
        )

    frames: list[Path] = [base_path]

    if needs_anim and nudges:
        try:
            print(f"[{payload_id}] firing Qwen chain ({len(nudges)} nudges)...")
            result = _fire_qwen_animate(
                base_path=base_path, nudges=nudges,
                save_dir=target_dir, seed_label=payload["base_seed_label"],
            )
            # Qwen saves frames as frame_000.png, frame_001.png, etc.
            # Our base is already frame_000; Qwen's frame_000 is the
            # first NUDGED frame. Rename to avoid collision.
            for i, f in enumerate(result.get("frames", [])):
                src = Path(f["save_path"])
                dst = target_dir / f"frame_{i+1:03d}.png"
                if src != dst:
                    src.rename(dst)
                frames.append(dst)
            print(f"  → {len(frames)} frames total")
        except Exception as e:
            return RunResult(
                payload_id=payload_id, disposition="error", base_path=base_path,
                frame_paths=frames, manifest_path=None, error=f"Qwen: {e}",
                elapsed_s=time.time() - t0,
            )

    # Write manifest
    manifest = {
        "payload_id": payload_id,
        "essence": payload["essence"],
        "animation_name": payload["animation_name"],
        "kind": payload["kind"],
        "sub_kind": payload.get("sub_kind"),
        "frame_count": len(frames),
        "frame_paths": [str(f) for f in frames],
        "source_progression_description": payload.get("source_progression_description"),
        "nudges_used": nudges,
        "base_prompt": payload["base_prompt"],
        "seed_label": payload["base_seed_label"],
        "elapsed_s": round(time.time() - t0, 2),
    }
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return RunResult(
        payload_id=payload_id,
        disposition="animated" if needs_anim and len(frames) > 1 else "static",
        base_path=base_path, frame_paths=frames,
        manifest_path=manifest_path, error=None,
        elapsed_s=time.time() - t0,
    )


def _all_frames_exist(target_dir: Path, nudge_count: int) -> bool:
    """True when base + N nudge frames all exist on disk."""
    for i in range(1 + nudge_count):
        if not (target_dir / f"frame_{i:03d}.png").is_file():
            return False
    return True


def _collect_frames(target_dir: Path) -> list[Path]:
    return sorted(target_dir.glob("frame_*.png"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("payload", type=Path, help="path to a nudge JSON")
    ap.add_argument("--out", type=Path, default=Path("./out/bpc"),
                    help="output directory (default: ./out/bpc)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="actually fire ERNIE + Qwen")
    g.add_argument("--dry-run", action="store_true", default=True,
                   help="print plan only (default)")
    args = ap.parse_args()

    if not args.payload.is_file():
        print(f"ERROR: {args.payload} not a file", file=sys.stderr)
        return 1
    payload = json.loads(args.payload.read_text())
    result = run_payload(payload, args.out, dry_run=not args.apply)
    print(f"\n=== RESULT ===")
    print(f"  payload_id:   {result.payload_id}")
    print(f"  disposition:  {result.disposition}")
    print(f"  frames:       {len(result.frame_paths)}")
    print(f"  elapsed_s:    {result.elapsed_s:.1f}")
    if result.error:
        print(f"  error:        {result.error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
