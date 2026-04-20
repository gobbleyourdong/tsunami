"""gamedev delivery gate — catalog-composition + game-definition validation.

The gamedev scaffold delivers via `public/game_definition.json` (emitted
by the `emit_design` tool; the engine at scaffolds/engine/ consumes it
at boot). It does NOT deliver via src/App.tsx.

This probe catches the 80% of what breaks a gamedev delivery at load:

  1. No game_definition.json        — wave forgot to emit_design
  2. No scenes / entities / mechanics — the JSON is empty/malformed
  3. Mechanics referencing unknown `type` values — catalog drift
  4. Zero catalog mechanics used    — wave re-implemented primitives
  5. Single-scene output when multi-scene expected (probe heuristic;
     advisory only — some prompts legitimately want one scene)

Run after `npm run build`. Points at `<project>/public/game_definition.json`.
Complements the F-B1 src/-scan probe in scripts/overnight/probe.py
(which scans TSX/TS for MechanicType imports) — BOTH paths fire for
gamedev because some prompts mix catalog JSON + React overlays, but
this probe is the canonical one for gamedev deliveries.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ._probe_common import result, skip

log = logging.getLogger("tsunami.core.gamedev_probe")


# MechanicType names known to the catalog — READ FROM SCHEMA.TS at
# import time via tsunami.engine_catalog. Single source of truth:
# when schema.ts gains a new MechanicType literal, this set updates
# automatically without hand-editing the probe.
from ..engine_catalog import KNOWN_MECHANIC_TYPES as _KNOWN_MECHANICS


async def gamedev_probe(project_dir: Path, task_text: str = "") -> dict:
    """Inspect a gamedev deliverable. Async signature matches the other
    probes in core/dispatch.py; no I/O actually awaits today but
    leaving it async keeps the dispatcher uniform.

    Returns the canonical {passed, issues, raw} shape.
    """
    del task_text  # reserved for keyword-aware rubric routing (F-A4)
    pdir = Path(project_dir)
    game_def = pdir / "public" / "game_definition.json"
    if not game_def.is_file():
        # Fallback: some builds emit at project root; check there too.
        alt = pdir / "game_definition.json"
        if alt.is_file():
            game_def = alt
        else:
            return result(
                passed=False,
                issues=(
                    "NO game_definition.json — gamedev scaffold requires "
                    "the wave to call emit_design(). Without this file, "
                    "the engine has nothing to run. Likely failure modes: "
                    "the wave wrote src/App.tsx instead (wrong pattern), "
                    "or never reached the emit_design tool call."
                ),
                raw="missing: public/game_definition.json",
            )

    try:
        body = json.loads(game_def.read_text())
    except json.JSONDecodeError as e:
        return result(
            passed=False,
            issues=f"game_definition.json is not valid JSON: {e}",
            raw=f"parse error at {game_def}",
        )

    issues: list[str] = []

    # Structural requirements. The compiled game_definition.json from
    # emit_design has:
    #   scenes: Record<string, Scene>   (object, keyed by scene name)
    #   scene.entities: Archetype[]     (array inside each scene)
    #   mechanics: MechanicInstance[]   (top-level array)
    # The raw DesignScript input uses Records for entities/mechanics too.
    # Handle BOTH shapes — probe runs on compiled OR raw design.
    scenes_raw = body.get("scenes")
    mechanics_raw = body.get("mechanics")
    # Schema-canonical shape (post-Fix #17a) uses `archetypes` at root;
    # older plan taught `entities` (list). Read both and union — if
    # either is populated, the delivery has entity structure. Gap #18
    # (2026-04-20): probe used to read `entities` only, so a schema-
    # canonical delivery would be flagged "no entities" falsely.
    entities_raw = body.get("entities")
    archetypes_raw = body.get("archetypes")

    # Normalize scenes: dict[str, Scene] → list[Scene] OR already-list.
    if isinstance(scenes_raw, dict):
        scenes = list(scenes_raw.values())
    elif isinstance(scenes_raw, list):
        scenes = scenes_raw
    else:
        scenes = []

    # Normalize mechanics: dict[str, Mechanic] → list[Mechanic] OR list.
    if isinstance(mechanics_raw, dict):
        mechanics = list(mechanics_raw.values())
    elif isinstance(mechanics_raw, list):
        mechanics = mechanics_raw
    else:
        mechanics = []

    # Normalize entities + archetypes into a single entity list for the
    # "player-exists" check. Schema-canonical designs use `archetypes`
    # (dict); older plan-era designs use `entities` (list); compiled
    # designs may carry entities nested under `scenes[*].entities`.
    entities: list = []
    # archetypes: dict[id, Archetype] OR list[Archetype] (Round L iter 7 drift)
    if isinstance(archetypes_raw, dict):
        entities.extend(archetypes_raw.values())
    elif isinstance(archetypes_raw, list):
        entities.extend(archetypes_raw)
    # entities: top-level list or dict
    if isinstance(entities_raw, dict):
        entities.extend(entities_raw.values())
    elif isinstance(entities_raw, list):
        entities.extend(entities_raw)
    # If still empty, walk scenes[*].entities (compiled form)
    if not entities:
        for scene in scenes:
            if isinstance(scene, dict):
                scene_ents = scene.get("entities")
                if isinstance(scene_ents, list):
                    entities.extend(scene_ents)
                elif isinstance(scene_ents, dict):
                    entities.extend(scene_ents.values())

    if len(scenes) == 0:
        issues.append(
            "no scenes — gamedev delivery needs at least a main scene"
        )
    if len(mechanics) == 0:
        issues.append(
            "mechanics is empty — no catalog composition happened. "
            "Wave re-implemented primitives instead of importing them."
        )
    if len(entities) == 0:
        issues.append(
            "no entities — gamedev delivery needs at least a player "
            "entity (top-level `entities` or `scenes.<name>.entities`)"
        )

    # Catalog validity: every mechanic.type must be a known MechanicType.
    unknown_mechanics = []
    catalog_count = 0
    for m in mechanics if isinstance(mechanics, list) else []:
        if not isinstance(m, dict):
            continue
        mtype = m.get("type", "")
        if mtype and mtype in _KNOWN_MECHANICS:
            catalog_count += 1
        elif mtype:
            unknown_mechanics.append(mtype)

    if unknown_mechanics:
        # First 5 to keep the issues string compact.
        preview = ", ".join(unknown_mechanics[:5])
        more = f" (+{len(unknown_mechanics)-5} more)" if len(unknown_mechanics) > 5 else ""
        issues.append(
            f"{len(unknown_mechanics)} mechanic(s) with unknown type: "
            f"{preview}{more}. Either the catalog needs these (propose "
            f"via catalog_proposals.md), or the wave invented them. "
            f"Valid MechanicType entries: see @engine/design/catalog."
        )

    # If we have a mechanics array but zero of them resolved to the
    # catalog, that's the "wave invented everything" failure mode.
    if isinstance(mechanics, list) and mechanics and catalog_count == 0:
        issues.append(
            "0 of {} mechanics matched the catalog — wave is not "
            "composing from @engine/design/catalog. Did the system "
            "prompt reach the wave? Was the genre directive injected?"
            .format(len(mechanics))
        )

    # Build a summary raw string — the morning consolidator reads this.
    raw_summary = (
        f"game_definition.json: scenes={len(scenes) if isinstance(scenes, list) else '?'}, "
        f"entities={len(entities) if isinstance(entities, list) else '?'}, "
        f"mechanics={len(mechanics) if isinstance(mechanics, list) else '?'}, "
        f"catalog_mechanics={catalog_count}, "
        f"unknown_mechanics={len(unknown_mechanics)}"
    )

    if issues:
        return result(passed=False, issues="; ".join(issues), raw=raw_summary)
    return result(passed=True, raw=raw_summary)


__all__ = ["gamedev_probe"]
