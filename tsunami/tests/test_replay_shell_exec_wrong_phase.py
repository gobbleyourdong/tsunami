"""Replay regression for pain_shell_exec_wrong_phase (severity 3).

Two coupled fixes under test:
  1. `tsunami/phase_machine.py::context_note` no longer tells
     scaffold-first gamedev drones to run `shell_exec with 'npx vite
     build'`. The scaffold ships playable; the terminal action is
     `message_result`.
  2. `tsunami/agent.py` dispatch-reject branch emits a tailored error
     for shell_exec-in-wrong-phase that names the real next step
     (message_result for scaffold-first, "build runs automatically"
     for plain WRITE).

Trace source: 3 sessions 2026-04-20 (1776733458 silent-blade,
1776735631, 1776737362 ninja-grove). Clearest example is 1776737362:
phase_machine nudge fires at iter 23 saying "Run: shell_exec with
'npx vite build'", drone obeys at iter 25, dispatch rejects with
"Tool 'shell_exec' is not available in this phase. Available: [...]".
The orchestrator and the schema filter disagreed; drone was caught
in the middle.

Fixture: tsunami/tests/replays/shell_exec_wrong_phase.jsonl
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tsunami.phase_machine import PhaseMachine, Phase


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "shell_exec_wrong_phase.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestPhaseMachineNudgeReplay:
    """Replay each nudge_case from the fixture against the real
    phase_machine.context_note implementation."""

    @pytest.fixture
    def cases(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "nudge_case"]

    def test_fixture_well_formed(self):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        cases = [e for e in events if e["kind"] == "nudge_case"]
        assert meta["slug"] == "shell_exec_wrong_phase"
        assert len(cases) >= 3, \
            "fixture must cover scaffold-first, plain WRITE, and legacy gamedev"

    def test_every_case_matches_expect(self, cases, tmp_path: Path):
        for case in cases:
            # Build a project dir that matches the case's signal.
            proj = tmp_path / f"proj_{case['desc'].replace(' ', '_').replace(',', '')[:40]}"
            proj.mkdir(parents=True, exist_ok=True)
            if case["project_has_data_dir"]:
                data_dir = proj / "data"
                data_dir.mkdir()
                (data_dir / "enemies.json").write_text("[]")

            pm = PhaseMachine()
            pm.phase = Phase[case["phase"]]
            pm.files_written = case["files_written"]
            pm.iters_in_phase = case["iters_in_phase"]
            pm.project_path = str(proj)

            note = pm.context_note(scaffold_kind=case["scaffold_kind"])

            if case.get("expect_none"):
                assert note is None, (
                    f"case {case['desc']!r}: expected no nudge, "
                    f"got {note!r}"
                )
                continue

            assert note is not None, (
                f"case {case['desc']!r}: expected a nudge, got None"
            )
            for fragment in case.get("expect_contains", []):
                assert fragment in note, (
                    f"case {case['desc']!r}: nudge missing {fragment!r}.\n"
                    f"Got: {note!r}"
                )
            for fragment in case.get("expect_not_contains", []):
                assert fragment not in note, (
                    f"case {case['desc']!r}: nudge contains forbidden "
                    f"{fragment!r}.\nGot: {note!r}"
                )


class TestScaffoldFirstDeliverNudge:
    """Focused test on the scaffold-first branch — it must point at
    message_result, not shell_exec, and must NOT mention vite build."""

    def test_nudge_avoids_shell_exec_suggestion(self, tmp_path: Path):
        proj = tmp_path / "ninja-grove"
        (proj / "data").mkdir(parents=True)
        (proj / "data" / "tools.json").write_text("[]")
        pm = PhaseMachine()
        pm.phase = Phase.WRITE
        pm.files_written = 3
        pm.iters_in_phase = 8
        pm.project_path = str(proj)

        note = pm.context_note(scaffold_kind="gamedev")
        assert note is not None
        assert "shell_exec" not in note, (
            f"scaffold-first nudge must not mention shell_exec; got: {note!r}"
        )
        assert "vite build" not in note
        assert "message_result" in note


class TestDispatchRejectSource:
    """Source-level checks that agent.py's dispatch reject carries the
    shell_exec-specific branch. Full behavioral boot of Agent would
    need a model + registry — overkill for a regression anchor."""

    def test_agent_has_shell_exec_reject_branch(self):
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        assert 'elif tool_call.name == "shell_exec":' in src, (
            "agent.py dispatch reject no longer has a shell_exec branch. "
            "Restore the tailored reject so wrong-phase shell_exec calls "
            "point the drone at the right next action."
        )
        assert "scaffold-first gamedev project" in src, (
            "agent.py shell_exec reject no longer distinguishes scaffold-"
            "first gamedev from plain WRITE. The generic message doesn't "
            "explain that scaffold-first ships playable — reinstate the "
            "predicate branch."
        )
        assert "build runs automatically after file_write" in src, (
            "agent.py shell_exec reject for non-scaffold WRITE no longer "
            "names the auto-build. The generic sorted(allowed_names) dump "
            "doesn't give the drone enough signal to stop retrying "
            "shell_exec."
        )
