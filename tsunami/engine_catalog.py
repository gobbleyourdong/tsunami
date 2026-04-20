"""Single source of truth for MechanicType literals.

Parses `scaffolds/engine/src/design/schema.ts` at import time and
exposes `KNOWN_MECHANIC_TYPES` — the set of valid `type` values the
engine's design compiler accepts.

Before this module, two places (`tests/test_genre_scaffolds.py` line
29 and `core/gamedev_probe.py` line 40) kept hand-maintained mirrors
of the same string-literal union. Drift was a real risk: schema.ts
added 6 JRPG placeholders 2026-04-20 and both mirrors had to be
updated by hand. Now both read from here.

F-A1 drift-report (`scripts/overnight/promote_to_catalog.py`) uses a
different parser on the same file — leaving that one intact because
it also reads promoted-mechanic rows from the essence corpus. This
module is a leaner read for the runtime probe + test paths.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_TS = _REPO_ROOT / "scaffolds" / "engine" / "src" / "design" / "schema.ts"


def _extract_mechanic_types(schema_text: str) -> frozenset[str]:
    """Pull the MechanicType union's string-literal members.

    Looks for `export type MechanicType =` and collects every
    `'<Identifier>'` until the next top-level declaration or EOF.
    Identifiers are CapitalizedCamelCase (\\b[A-Z][A-Za-z0-9_]+\\b).
    """
    m = re.search(
        r"export type MechanicType\s*=\s*\n((?:.*\n)*?)(?=^\S|\Z)",
        schema_text, re.MULTILINE,
    )
    if not m:
        return frozenset()
    block = m.group(1)
    names = re.findall(r"'([A-Z][A-Za-z0-9_]+)'", block)
    return frozenset(names)


def _load_known_mechanics() -> frozenset[str]:
    """Read schema.ts and parse — robust against missing file."""
    try:
        if _SCHEMA_TS.is_file():
            return _extract_mechanic_types(_SCHEMA_TS.read_text())
    except Exception:
        pass
    # Fallback: known-baseline set (v0 + v1 + v1.2 JRPG placeholders).
    # Keeps tests/probe functional if schema.ts is temporarily unreadable.
    return frozenset({
        "Difficulty", "HUD", "LoseOnZero", "WinOnCount", "WaveSpawner",
        "PickupLoop", "ScoreCombos", "CheckpointProgression", "LockAndKey",
        "StateMachineMechanic", "ComboAttacks", "BossPhases", "RhythmTrack",
        "LevelSequence", "RoomGraph", "ItemUse", "GatedTrigger",
        "TimedStateModifier", "AttackFrames", "Shop", "UtilityAI",
        "DialogTree", "HotspotMechanic", "InventoryCombine", "CameraFollow",
        "StatusStack", "EmbeddedMinigame", "EndingBranches", "VisionCone",
        "PuzzleObject", "ProceduralRoomChain", "BulletPattern", "RouteMap",
        "ChipMusic", "SfxLibrary", "RoleAssignment", "CrowdSimulation",
        "TimeReverseMechanic", "PhysicsModifier", "MinigamePool",
        "ATBCombat", "TurnBasedCombat", "PartyComposition",
        "LevelUpProgression", "WorldMapTravel", "EquipmentLoadout",
    })


# Computed once at import time. Cheap (one file read + regex).
KNOWN_MECHANIC_TYPES: frozenset[str] = _load_known_mechanics()


__all__ = ["KNOWN_MECHANIC_TYPES"]
