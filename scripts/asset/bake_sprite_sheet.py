"""Bake an entity state-graph → traditional sprite sheet + metadata JSON.

Commit 5 of the asset-state-graph campaign. This is the thing that
connects the YAML-authored graph (commits 2-4) to a live server
producing actual pixels via chain-edit animation (commit 1).

Pipeline:

  1. Load entity graph (strict mode — every animation/overlay ref must
     resolve to a real primitive YAML on disk).
  2. Topologically derive static state images (healthy_still → windy
     → on_fire → extinguished → ...), one /v1/images/edit call per
     derived state.
  3. For each transition with `animation`: run /v1/images/animate from
     the from_state's image, using the primitive's nudge list. Frames
     land on disk under <out>/transitions/<from>__<to>/frame_NNN.png.
  4. For each transition with `reverse_of`: copy the target transition's
     frames in reverse order. No inference call — reverse_of is a
     pure-authoring shortcut so the same primitive produces two chains.
  5. For each loop: same as step 3 but frames land under <out>/loops/<name>/.
  6. Compose one sheet.png — one row per (loop + transition), frames
     packed horizontally. All rows padded to the widest row.
  7. Write metadata.json mapping (row_index, col_index) → semantic info
     (which animation, frame idx, from_state, to_state, nudge delta).

The sigma invariant (sum-of-nudge-strengths bounded) is logged per
animation and emitted into the metadata so downstream tooling can flag
drift outliers without re-running inference.

Dry-run mode: prints the plan — "would call /edit 5x, /animate 5x,
reverse 1 from pristine→shattered" — without touching the server.
Critical for sanity-checking a new graph before burning minutes of
GPU time.

Usage:
  python scripts/asset/bake_sprite_sheet.py \\
      --entity scaffolds/engine/asset_library/entities/tree.yaml \\
      --out-dir /tmp/tree_bake \\
      --server http://127.0.0.1:8094

  # Or plan-only, no server call:
  python scripts/asset/bake_sprite_sheet.py --entity ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

# Make tsunami importable when running the script directly from repo root.
_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tsunami.animation.state_graph import (
    AnimationPrimitive,
    EntityGraph,
    LoopRef,
    Transition,
    load_entity_graph,
    load_primitive,
)

log = logging.getLogger("bake")


# ── Plan ────────────────────────────────────────────────────────────

class BakePlan:
    """Computed from an EntityGraph. Drives both dry-run and live bake.

    Attributes:
      graph: source entity graph
      animations_dir: where primitive YAMLs live
      derivation_order: state names in topological order (base first)
      primitives: cache of loaded primitive YAMLs, keyed by ref
      forward_transitions: transitions with animation=... (actual inference)
      reverse_transitions: transitions with reverse_of=... (no inference)
    """

    def __init__(self, graph: EntityGraph, animations_dir: Path):
        self.graph = graph
        self.animations_dir = animations_dir
        self.derivation_order: list[str] = self._topo_sort_states()
        self.primitives: dict[str, AnimationPrimitive] = {}
        self._load_primitives()
        self.forward_transitions: list[Transition] = [
            t for t in graph.transitions if t.animation
        ]
        self.reverse_transitions: list[Transition] = [
            t for t in graph.transitions if t.reverse_of
        ]

    def _topo_sort_states(self) -> list[str]:
        """Return state names such that every state appears after any
        state it derives from. Root comes first. The state graph's
        validator already rejected cycles, so a plain DFS suffices."""
        order: list[str] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            sdef = self.graph.states.get(name)
            if sdef is None:
                raise KeyError(f"unknown state {name!r}")
            if sdef.derive_from:
                visit(sdef.derive_from)
            visited.add(name)
            order.append(name)

        for name in self.graph.states:
            visit(name)
        return order

    def _load_primitives(self) -> None:
        refs: set[str] = set()
        for t in self.graph.transitions:
            if t.animation:
                refs.add(t.animation)
        for lref in self.graph.loops.values():
            refs.add(lref.animation)
        for ref in refs:
            stem = ref if ref.endswith(".yaml") else f"{ref}.yaml"
            path = self.animations_dir / stem
            self.primitives[ref] = load_primitive(path)

    def describe(self) -> str:
        """Human-readable plan summary (for --dry-run)."""
        lines = [
            f"entity: {self.graph.entity}",
            f"base: {self.graph.base}",
            f"states ({len(self.graph.states)} total, derivation order):",
        ]
        for name in self.derivation_order:
            sdef = self.graph.states[name]
            if sdef.is_root():
                lines.append(f"  - {name}  [ROOT]")
            else:
                lines.append(
                    f"  - {name}  ← derive_from({sdef.derive_from}) + prompt"
                )
        lines.append(
            f"forward transitions ({len(self.forward_transitions)}, "
            f"inference calls):"
        )
        for t in self.forward_transitions:
            prim = self.primitives[t.animation]
            lines.append(
                f"  - {t.identifier()} on={t.on} anim={t.animation} "
                f"({prim.frame_count} frames)"
            )
        lines.append(
            f"reverse transitions ({len(self.reverse_transitions)}, "
            f"copy-only):"
        )
        for t in self.reverse_transitions:
            lines.append(
                f"  - {t.identifier()} on={t.on} reverse_of={t.reverse_of}"
            )
        lines.append(f"loops ({len(self.graph.loops)}, inference calls):")
        for lname, lref in self.graph.loops.items():
            prim = self.primitives[lref.animation]
            lines.append(
                f"  - {lname}  state={lref.state} anim={lref.animation} "
                f"({prim.frame_count} frames)"
            )
        return "\n".join(lines)


# ── Server client (thin requests wrapper) ───────────────────────────

class BakeServer:
    """HTTP client for a live qwen_image_server. All calls are blocking —
    the bake is inherently serial (each frame depends on the previous).
    Failures raise so the bake halts at the first broken chain rather
    than producing a partial sprite sheet that looks valid but lies.

    `steps_override` and `cfg_override`, when set, replace the per-call
    num_inference_steps and guidance_scale values — useful for A/B quality
    experiments (e.g. 20 steps vs 40 at same seed). Defaults (None) leave
    each call's primitive-provided / endpoint-default values intact.
    """

    def __init__(self, base_url: str, timeout_s: int = 900,
                 steps_override: Optional[int] = None,
                 cfg_override: Optional[float] = None,
                 negative_prompt: str = " "):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.steps_override = steps_override
        self.cfg_override = cfg_override
        # Model card default is " " (single space) to engage CFG. Empty
        # string DISABLES CFG in the Qwen-Image-Edit pipe.
        self.negative_prompt = negative_prompt
        self._check_online()

    def _check_online(self) -> None:
        # Generous timeout — the server's async loop can be unresponsive
        # under GPU pressure from a prior in-flight request. Short 5s
        # timeout gave false negatives in back-to-back run tests.
        try:
            r = requests.get(f"{self.base_url}/healthz", timeout=180)
        except requests.RequestException as e:
            raise RuntimeError(
                f"bake server unreachable at {self.base_url}: {e}"
            ) from e
        if r.status_code != 200:
            raise RuntimeError(
                f"bake server at {self.base_url} returned {r.status_code} for /healthz"
            )
        health = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        # Verify the animate endpoint is present — catches the "ran a stale
        # server" failure mode cheaply.
        try:
            oapi = requests.get(f"{self.base_url}/openapi.json", timeout=180).json()
            if "/v1/images/animate" not in oapi.get("paths", {}):
                raise RuntimeError(
                    f"server at {self.base_url} has no /v1/images/animate — "
                    "running a pre-commit-1 qwen_image_server? Restart it."
                )
        except requests.RequestException:
            pass  # openapi optional; fail late if animate itself errors

        # Warn if a distillation LoRA ever slips into the registry again.
        # The non-distilled base is the verdict for Qwen-Image-Edit-2511 —
        # lightning/turbo variants produce visibly undercooked sprites
        # (see feedback_qwen_lightning_worse.md). Warn loudly so the
        # operator notices before burning a full bake on a regression.
        loras = [s.lower() for s in health.get("loaded_loras", [])]
        suspect = [l for l in loras if "lightning" in l or "turbo" in l]
        if suspect:
            log.warning(
                f"[bake] distillation LoRA detected: {suspect}. "
                "Non-distilled base is the verdict for this pipe "
                "(lightning trades too much quality for ~3× speed). "
                "Detach via POST /v1/admin/lora {\"name\": \"none\"} "
                "if this was unintended."
            )

    def edit(self, *, base_path: Path, prompt: str, save_path: Path,
             strength: float = 0.75, seed: Optional[int] = None,
             height: int = 1024, width: int = 1024) -> None:
        """Run one /v1/images/edit call, saving to save_path."""
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # Model-card defaults for Qwen-Image-Edit-2511 non-distilled:
        # 40 steps, true_cfg_scale=4.0. Overrides apply when caller sets
        # --steps/--cfg (e.g. for a distilled schedule).
        steps = self.steps_override if self.steps_override is not None else 40
        cfg = self.cfg_override if self.cfg_override is not None else 4.0
        payload = {
            "path": str(base_path),
            "prompt": prompt,
            "negative_prompt": self.negative_prompt,
            "strength": strength,
            "height": height,
            "width": width,
            "num_inference_steps": steps,
            "guidance_scale": cfg,
            "response_format": "save_path",
            "save_path": str(save_path),
        }
        if seed is not None:
            payload["seed"] = seed
        r = requests.post(
            f"{self.base_url}/v1/images/edit",
            json=payload, timeout=self.timeout_s,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"/v1/images/edit {save_path.name} failed "
                f"({r.status_code}): {r.text[:500]}"
            )

    def animate(self, *, base_path: Path, primitive: AnimationPrimitive,
                save_dir: Path,
                seed: Optional[int] = None) -> list[Path]:
        """Run one /v1/images/animate call, returning the saved frame paths
        in order."""
        save_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "path": str(base_path),
            "negative_prompt": self.negative_prompt,
            "nudges": [
                {
                    "delta": n.delta,
                    "strength": n.strength,
                    "guidance_scale": (self.cfg_override
                                       if self.cfg_override is not None
                                       else n.guidance_scale),
                    "num_inference_steps": (self.steps_override
                                            if self.steps_override is not None
                                            else n.num_inference_steps),
                }
                for n in primitive.nudges
            ],
            "response_format": "save_path",
            "save_dir": str(save_dir),
        }
        if seed is not None:
            payload["seed"] = seed
        r = requests.post(
            f"{self.base_url}/v1/images/animate",
            json=payload, timeout=self.timeout_s,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"/v1/images/animate {save_dir.name} failed "
                f"({r.status_code}): {r.text[:500]}"
            )
        body = r.json()
        return [Path(f["save_path"]) for f in body["frames"]]


# ── Bake steps ──────────────────────────────────────────────────────

def derive_states(plan: BakePlan, base_path: Path, out_dir: Path,
                  server: BakeServer,
                  base_resolution: int = 1024,
                  seed: Optional[int] = None) -> dict[str, Path]:
    """For each state, produce a static image on disk. Root state uses
    the entity base directly; derived states run one /edit call each,
    chained so `extinguished` derives from on_fire's baked image, not
    from base.

    Generation runs at `base_resolution` × `base_resolution` — full res,
    not the sprite's target pixel grid. Attachment-point precision
    (e.g. sword-to-hand alignment in an attack frame) requires rendering
    at full res first. Pixelization to the final sprite size is a
    separate, later pass — not baked in here so the canonical frames
    stay available for re-quantization at any target grid."""
    state_dir = out_dir / "states"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_images: dict[str, Path] = {}

    # Upscale the base to full generation resolution. Frames inherit this
    # size because QwenImageEditPlusPipeline preserves input dims when
    # height/width aren't explicitly overridden.
    full_res_base = state_dir / "__base_upscaled.png"
    src = Image.open(base_path).convert("RGBA")
    src.resize((base_resolution, base_resolution), Image.LANCZOS).save(full_res_base)
    log.info(
        f"[derive] base upscaled {src.size} → "
        f"{base_resolution}×{base_resolution} at {full_res_base}"
    )

    for name in plan.derivation_order:
        sdef = plan.graph.states[name]
        out_path = state_dir / f"{name}.png"
        if sdef.is_root():
            # The root state IS the base. Copy the upscaled canonical version.
            Image.open(full_res_base).save(out_path)
            log.info(f"[derive] {name}: root → copied upscaled base")
        else:
            parent_path = state_images[sdef.derive_from]
            log.info(
                f"[derive] {name}: editing from {sdef.derive_from} "
                f"prompt={sdef.prompt[:60]!r}"
            )
            t0 = time.time()
            server.edit(
                base_path=parent_path,
                prompt=sdef.prompt,
                save_path=out_path,
                height=base_resolution, width=base_resolution,
                seed=seed,
            )
            log.info(f"[derive] {name}: {time.time()-t0:.1f}s")
        state_images[name] = out_path
    return state_images


def bake_transitions(plan: BakePlan, state_images: dict[str, Path],
                     out_dir: Path, server: BakeServer,
                     seed: Optional[int] = None) -> dict[str, list[Path]]:
    """Run animate for every forward transition. Returns {identifier: [frames]}."""
    tdir = out_dir / "transitions"
    frames_by_id: dict[str, list[Path]] = {}
    for t in plan.forward_transitions:
        prim = plan.primitives[t.animation]
        save_dir = tdir / f"{t.from_state}__{t.to_state}"
        log.info(
            f"[transition] {t.identifier()}: animate {prim.frame_count} frames "
            f"(primitive={t.animation})"
        )
        t0 = time.time()
        frames = server.animate(
            base_path=state_images[t.from_state],
            primitive=prim,
            save_dir=save_dir,
            seed=seed,
        )
        log.info(
            f"[transition] {t.identifier()}: {len(frames)} frames in "
            f"{time.time()-t0:.1f}s"
        )
        frames_by_id[t.identifier()] = frames
    return frames_by_id


def apply_reverse_of(plan: BakePlan,
                     frames_by_id: dict[str, list[Path]],
                     out_dir: Path) -> dict[str, list[Path]]:
    """For each reverse_of transition, copy the target's frames in reverse
    order into the reverse transition's own directory. Returns the
    reverse transitions' frame lists."""
    tdir = out_dir / "transitions"
    reverse_by_id: dict[str, list[Path]] = {}
    for t in plan.reverse_transitions:
        if t.reverse_of not in frames_by_id:
            raise RuntimeError(
                f"reverse_of target {t.reverse_of!r} produced no frames — "
                "forward transition baking may have failed"
            )
        src_frames = frames_by_id[t.reverse_of]
        save_dir = tdir / f"{t.from_state}__{t.to_state}"
        save_dir.mkdir(parents=True, exist_ok=True)
        dst_frames: list[Path] = []
        # Copy frames in REVERSE order. Renumber sequentially so downstream
        # tooling doesn't need to know about reversal.
        for i, src in enumerate(reversed(src_frames)):
            dst = save_dir / f"frame_{i:03d}.png"
            Image.open(src).save(dst)
            dst_frames.append(dst)
        log.info(
            f"[reverse] {t.identifier()}: {len(dst_frames)} frames from "
            f"{t.reverse_of} reversed"
        )
        reverse_by_id[t.identifier()] = dst_frames
    return reverse_by_id


def bake_loops(plan: BakePlan, state_images: dict[str, Path],
               out_dir: Path, server: BakeServer,
               seed: Optional[int] = None) -> dict[str, list[Path]]:
    """Run animate for every loop."""
    ldir = out_dir / "loops"
    frames_by_name: dict[str, list[Path]] = {}
    for lname, lref in plan.graph.loops.items():
        prim = plan.primitives[lref.animation]
        save_dir = ldir / lname
        log.info(
            f"[loop] {lname}: animate {prim.frame_count} frames in state "
            f"{lref.state} (primitive={lref.animation})"
        )
        t0 = time.time()
        frames = server.animate(
            base_path=state_images[lref.state],
            primitive=prim,
            save_dir=save_dir,
            seed=seed,
        )
        log.info(
            f"[loop] {lname}: {len(frames)} frames in {time.time()-t0:.1f}s"
        )
        frames_by_name[lname] = frames
    return frames_by_name


# ── Sprite-sheet composition ────────────────────────────────────────

def compose_sprite_sheet(rows: list[tuple[str, list[Path]]],
                         out_path: Path) -> tuple[int, int]:
    """Stitch frames into one PNG. Each input row becomes one sheet row;
    frames pack horizontally. Rows pad to the maximum row width with a
    transparent fill so indexing by (row, col) stays clean.

    Returns (frame_width, frame_height) of a single cell (all frames
    assumed same dimensions — which they are, since animate preserves
    input size)."""
    if not rows:
        raise RuntimeError("cannot compose sprite sheet with zero rows")
    # Measure one frame.
    first_frame = None
    for _, frames in rows:
        if frames:
            first_frame = Image.open(frames[0])
            break
    if first_frame is None:
        raise RuntimeError("cannot compose sprite sheet: all rows empty")
    fw, fh = first_frame.size

    max_cols = max(len(frames) for _, frames in rows)
    sheet_w = fw * max_cols
    sheet_h = fh * len(rows)
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    for r_idx, (_, frames) in enumerate(rows):
        for c_idx, fpath in enumerate(frames):
            frame = Image.open(fpath).convert("RGBA")
            sheet.paste(frame, (c_idx * fw, r_idx * fh), frame)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    log.info(f"[sheet] {sheet_w}x{sheet_h} → {out_path} ({len(rows)} rows × {max_cols} cols)")
    return fw, fh


# ── Metadata emission ───────────────────────────────────────────────

def build_metadata(plan: BakePlan,
                   ordered_rows: list[tuple[str, list[Path]]],
                   frame_size: tuple[int, int],
                   transitions_by_id: dict[str, list[Path]],
                   reverse_by_id: dict[str, list[Path]],
                   loops_by_name: dict[str, list[Path]]) -> dict:
    """Build the sheet-level metadata JSON. Each row gets a descriptor
    saying which animation it belongs to + per-cell info."""
    fw, fh = frame_size
    rows_meta: list[dict] = []
    for r_idx, (row_name, frames) in enumerate(ordered_rows):
        # Figure out what kind of row this is.
        kind = None
        from_state = to_state = None
        primitive = None
        nudges: list[dict] = []
        σ = 0.0

        if row_name in loops_by_name:
            kind = "loop"
            lref: LoopRef = plan.graph.loops[row_name]
            from_state = to_state = lref.state
            primitive = lref.animation
            prim = plan.primitives[primitive]
            σ = round(sum(n.strength for n in prim.nudges), 3)
            nudges = [
                {"delta": n.delta, "strength": n.strength}
                for n in prim.nudges
            ]
        elif row_name in transitions_by_id or row_name in reverse_by_id:
            # Row name is a transition identifier.
            tr = next((t for t in plan.graph.transitions
                       if t.identifier() == row_name), None)
            if tr is None:
                raise KeyError(f"no transition matching row {row_name}")
            from_state = tr.from_state
            to_state = tr.to_state
            if tr.reverse_of:
                kind = "reverse_transition"
                primitive = f"reverse_of:{tr.reverse_of}"
                # Pull nudges from the source primitive (reversed).
                src = next((x for x in plan.graph.transitions
                            if x.identifier() == tr.reverse_of), None)
                if src and src.animation:
                    prim = plan.primitives[src.animation]
                    σ = round(sum(n.strength for n in prim.nudges), 3)
                    nudges = list(reversed([
                        {"delta": n.delta, "strength": n.strength}
                        for n in prim.nudges
                    ]))
            else:
                kind = "transition"
                primitive = tr.animation
                prim = plan.primitives[primitive]
                σ = round(sum(n.strength for n in prim.nudges), 3)
                nudges = [
                    {"delta": n.delta, "strength": n.strength}
                    for n in prim.nudges
                ]
        else:
            raise KeyError(f"unclassifiable row: {row_name}")

        rows_meta.append({
            "row_index": r_idx,
            "name": row_name,
            "kind": kind,
            "from_state": from_state,
            "to_state": to_state,
            "primitive": primitive,
            "frame_count": len(frames),
            "cells": [
                {"col_index": c, "x": c * fw, "y": r_idx * fh,
                 "w": fw, "h": fh, "delta": nudges[c]["delta"] if c < len(nudges) else None,
                 "strength": nudges[c]["strength"] if c < len(nudges) else None}
                for c in range(len(frames))
            ],
            "total_strength": σ,
        })

    return {
        "entity": plan.graph.entity,
        "base": plan.graph.base,
        "frame_size": {"w": fw, "h": fh},
        "rows": rows_meta,
        "generated_at": int(time.time()),
        # Frames are at FULL generation resolution, NOT pixelized. Any
        # downstream pixelization pass should emit its own metadata file
        # alongside the quantized sprite sheet so the canonical + the
        # pixelized versions stay paired.
        "pixelization": "none — canonical full-res; quantize as a separate pass",
    }


# ── CLI ─────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entity", required=True, type=Path,
                   help="path to entity YAML under scaffolds/.../entities/")
    p.add_argument("--animations-dir", type=Path, default=None,
                   help="path to primitive YAMLs dir "
                        "(default: siblings/animations/ next to --entity)")
    p.add_argument("--base-image", type=Path, default=None,
                   help="override the base image path resolved from "
                        "the YAML's `base` field")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="where to write state images, transition/loop frames, "
                        "sheet.png and metadata.json")
    p.add_argument("--server", default="http://127.0.0.1:8094",
                   help="qwen_image_server base URL")
    p.add_argument("--base-resolution", type=int, default=1024,
                   help="generation resolution in pixels (default 1024). "
                        "All state/transition/loop frames emit at this size. "
                        "Pixelization to the sprite grid is a SEPARATE pass — "
                        "never rotate or edit on a pre-pixelized image.")
    p.add_argument("--steps", type=int, default=None,
                   help="override num_inference_steps for every edit + animate "
                        "call (default: use primitive YAML value, 40 per model "
                        "card). Useful for A/B quality experiments at reduced "
                        "step counts.")
    p.add_argument("--cfg", type=float, default=None,
                   help="override true_cfg_scale for every call (default 4.0 "
                        "per model card).")
    p.add_argument("--negative-prompt", default=" ",
                   help="negative prompt for every edit + animate call. "
                        "Default ' ' (single space) per model card — empty "
                        "string DISABLES CFG in the pipe, which silently "
                        "undercooks output.")
    p.add_argument("--seed", type=int, default=None,
                   help="deterministic seed for all edit/animate calls")
    p.add_argument("--dry-run", action="store_true",
                   help="print the bake plan without calling the server")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    entity_path: Path = args.entity.resolve()
    animations_dir: Path = (args.animations_dir
                            or entity_path.parent.parent / "animations").resolve()
    graph = load_entity_graph(entity_path, animations_dir=animations_dir)
    plan = BakePlan(graph, animations_dir)

    print(plan.describe())
    if args.dry_run:
        print("\n(dry-run — no server calls made)")
        return 0

    out_dir: Path = (args.out_dir
                     or (_REPO / "out" / "bake" / graph.entity)).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    base_path: Path = (args.base_image or (_REPO / graph.base)).resolve()
    if not base_path.is_file():
        print(f"ERROR: base image not found at {base_path}", file=sys.stderr)
        return 2

    server = BakeServer(args.server,
                        steps_override=args.steps,
                        cfg_override=args.cfg,
                        negative_prompt=args.negative_prompt)
    log.info(
        f"[bake] entity={graph.entity} base={base_path} out={out_dir} "
        f"steps={args.steps or 'primitive-default'} "
        f"cfg={args.cfg if args.cfg is not None else 'primitive-default'} "
        f"neg={args.negative_prompt!r}"
    )

    t0 = time.time()
    state_images = derive_states(plan, base_path, out_dir, server,
                                 base_resolution=args.base_resolution,
                                 seed=args.seed)
    transitions_by_id = bake_transitions(plan, state_images, out_dir, server, seed=args.seed)
    reverse_by_id = apply_reverse_of(plan, transitions_by_id, out_dir)
    loops_by_name = bake_loops(plan, state_images, out_dir, server, seed=args.seed)
    log.info(f"[bake] all frames computed in {time.time()-t0:.1f}s")

    # Compose sheet: loops first (static-state variety), then transitions
    # (forward then reverse), so the sheet has a visually consistent
    # top-to-bottom ordering.
    ordered_rows: list[tuple[str, list[Path]]] = []
    for lname in plan.graph.loops:
        ordered_rows.append((lname, loops_by_name[lname]))
    for t in plan.forward_transitions:
        ordered_rows.append((t.identifier(), transitions_by_id[t.identifier()]))
    for t in plan.reverse_transitions:
        ordered_rows.append((t.identifier(), reverse_by_id[t.identifier()]))

    sheet_path = out_dir / "sheet.png"
    fw, fh = compose_sprite_sheet(ordered_rows, sheet_path)

    meta = build_metadata(plan, ordered_rows, (fw, fh),
                          transitions_by_id, reverse_by_id, loops_by_name)
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info(f"[bake] metadata → {meta_path}")
    log.info(f"[bake] done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
