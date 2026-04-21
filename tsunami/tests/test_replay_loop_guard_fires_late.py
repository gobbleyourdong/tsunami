"""Replay regression for pain_loop_guard_fires_late (severity 2).

Anchors the tighter HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ=2 branch
in tsunami/loop_guard.py::check. For scaffold-first gamedev — where
file_read is structurally pointless (data/*.json, schema.ts,
catalog.ts, App.test.tsx all inlined in the system prompt) — two
identical file_read calls is already enough signal to intervene.
The generic HARD_LOOP_THRESHOLD=3 waits for a third identical call
and wastes an iteration in the interim.

Trace source: session 1776736395 (ice-cavern, Round J 2026-04-20).
Loop detection fired at iter 19, but the spiral started at iter 6.
With this patch, the drone gets one identical file_read; the second
trips the guard.

Fixture: tsunami/tests/replays/loop_guard_fires_late.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tsunami.loop_guard import (
    LoopGuard,
    HARD_LOOP_THRESHOLD,
    HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ,
)


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "loop_guard_fires_late.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _build_guard(scenario: dict) -> LoopGuard:
    """Build a LoopGuard primed with the scenario's call sequence.
    Mimics agent.py's setup: _scaffold_kind and _gamedev_mode are
    attributes on the instance (set by agent.py on each iter)."""
    lg = LoopGuard()
    lg._scaffold_kind = scenario["scaffold_kind"]
    lg._gamedev_mode = scenario["gamedev_mode"]
    for call in scenario["calls"]:
        lg.record(call["tool"], call["args"], made_progress=False)
    return lg


class TestLoopGuardScaffoldFirstReplay:
    @pytest.fixture
    def scenarios(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "scenario"]

    def test_fixture_well_formed(self):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        scenarios = [e for e in events if e["kind"] == "scenario"]
        assert meta["slug"] == "loop_guard_fires_late"
        assert len(scenarios) >= 6, (
            "fixture must cover positive case, under-threshold, other-modes, "
            "other-tools, streak-broken, and generic-threshold-fallback"
        )

    def test_threshold_constant_is_2(self):
        """Don't let a future edit drift the constant upward without
        tripping the test. The 2-threshold is the whole fix."""
        assert HARD_LOOP_THRESHOLD_SCAFFOLD_FIRST_READ == 2
        assert HARD_LOOP_THRESHOLD == 3, \
            "generic threshold is load-bearing for non-scaffold-first paths"

    def test_every_scenario_matches_expect(self, scenarios):
        for scenario in scenarios:
            lg = _build_guard(scenario)
            detection = lg.check(scaffold_kind=scenario["scaffold_kind"])
            assert detection.detected == scenario["expect_detected"], (
                f"scenario {scenario['desc']!r}: expected "
                f"detected={scenario['expect_detected']}, got "
                f"detected={detection.detected}. description="
                f"{detection.description!r}"
            )
            if scenario.get("expect_type"):
                assert detection.loop_type == scenario["expect_type"], (
                    f"scenario {scenario['desc']!r}: expected "
                    f"type={scenario['expect_type']}, got "
                    f"{detection.loop_type!r}"
                )
            for fragment in scenario.get("expect_description_contains", []):
                assert fragment in detection.description, (
                    f"scenario {scenario['desc']!r}: description missing "
                    f"{fragment!r}. Got: {detection.description!r}"
                )


class TestBoundaryCases:
    """Direct tests on the edge cases the replay doesn't make vivid."""

    def test_scaffold_first_without_gamedev_does_not_fire(self):
        """mode=scaffold_first only matters when scaffold_kind==gamedev.
        A 'scaffold_first' flag on a non-gamedev surface is nonsense —
        must not trip the tighter threshold."""
        lg = LoopGuard()
        lg._scaffold_kind = "react-app"
        lg._gamedev_mode = "scaffold_first"
        lg.record("file_read", {"path": "src/App.tsx"}, made_progress=False)
        lg.record("file_read", {"path": "src/App.tsx"}, made_progress=False)
        detection = lg.check(scaffold_kind="react-app")
        assert not detection.detected

    def test_different_paths_do_not_fire(self):
        """Two file_reads on DIFFERENT paths = different fingerprints =
        not an identical repeat. Drones legitimately read two different
        files in sequence."""
        lg = LoopGuard()
        lg._scaffold_kind = "gamedev"
        lg._gamedev_mode = "scaffold_first"
        lg.record("file_read", {"path": "data/enemies.json"}, made_progress=False)
        lg.record("file_read", {"path": "data/levels.json"}, made_progress=False)
        detection = lg.check(scaffold_kind="gamedev")
        assert not detection.detected

    def test_forced_action_routes_to_file_write(self):
        """The whole point of the intervention is to push the drone
        toward the next productive action. For scaffold-first gamedev,
        that's file_write on data/*.json."""
        lg = LoopGuard()
        lg._scaffold_kind = "gamedev"
        lg._gamedev_mode = "scaffold_first"
        lg.record("file_read", {"path": "data/x.json"}, made_progress=False)
        lg.record("file_read", {"path": "data/x.json"}, made_progress=False)
        detection = lg.check(scaffold_kind="gamedev")
        assert detection.detected
        # _suggest_break_action picks the right alternative for file_read.
        # The exact value depends on existing logic in loop_guard — we
        # assert it's non-empty and steers AWAY from file_read rather
        # than pinning the exact string.
        assert detection.forced_action, \
            f"forced_action should nudge the drone; got: {detection.forced_action!r}"
        assert detection.forced_action != "file_read"

    def test_missing_mode_attr_defaults_to_legacy(self):
        """If _gamedev_mode isn't set on the instance (fresh loop_guard
        before agent.py's first iter), the early branch must not fire
        spuriously — getattr default='legacy' keeps behavior generic."""
        lg = LoopGuard()
        lg._scaffold_kind = "gamedev"
        # _gamedev_mode intentionally not set
        lg.record("file_read", {"path": "x.json"}, made_progress=False)
        lg.record("file_read", {"path": "x.json"}, made_progress=False)
        detection = lg.check(scaffold_kind="gamedev")
        assert not detection.detected

    def test_generic_threshold_still_fires_outside_scaffold_first(self):
        """Non-scaffold-first paths still get the generic 3x threshold."""
        lg = LoopGuard()
        lg._scaffold_kind = "react-app"
        lg._gamedev_mode = "legacy"
        for _ in range(3):
            lg.record("file_read", {"path": "src/App.tsx"}, made_progress=False)
        detection = lg.check(scaffold_kind="react-app")
        assert detection.detected
        assert detection.loop_type == "hard"
