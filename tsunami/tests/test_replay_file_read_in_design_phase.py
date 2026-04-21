"""Replay regression for pain_file_read_in_design_phase (severity 5).

Anchors two coupled fixes:
  1. `tsunami.tools.filesystem.is_scaffold_first_gamedev(project_dir)` —
     predicate used by the data/*.json read gate AND by agent.py's
     design-phase schema allowlist.
  2. `tsunami/agent.py` design-phase schema block — file_read is dropped
     from the drone schema when the active project is scaffold-first
     gamedev, so the drone cannot emit a read that the tool layer would
     only block at execution time.

Trace sources: 7 sessions on 2026-04-20 (1776730055 / 1776730885 /
1776732400 / 1776733064 / 1776733868 / 1776734265 / 1776737048) all
exhibiting the same shape — 3-5 file_read calls on data/*.json,
src/scenes/*.ts, or scaffolds/engine/src/design/schema.ts before the
drone emits emit_design. Each wasted read is an iteration the drone
doesn't use to ship — one of the top contributors to the 93% task-
incomplete rate flagged by Coral's pain_high_abort_rate_today.

Fixture: tsunami/tests/replays/file_read_in_design_phase.jsonl
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import is_scaffold_first_gamedev


REPLAY_PATH = Path(__file__).parent / "replays" / "file_read_in_design_phase.jsonl"


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _materialize(workspace: Path, scaffold_event: dict) -> Path:
    project_dir = workspace / "deliverables" / scaffold_event["project"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "package.json").write_text(json.dumps(scaffold_event["package_json"]))
    for rel, content in scaffold_event.get("files", {}).items():
        t = project_dir / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(content)
    return project_dir


@pytest.fixture
def replay_env():
    root = tempfile.mkdtemp(prefix="kelp_design_phase_")
    workspace = Path(root) / "workspace"
    workspace.mkdir()
    events = _load_replay(REPLAY_PATH)
    meta = next(e for e in events if e["kind"] == "meta")
    project_dirs: dict[str, Path] = {}
    for e in events:
        if e["kind"] == "scaffold":
            project_dirs[e["project"]] = _materialize(workspace, e)
    assertions = [e for e in events if e["kind"] == "predicate_assert"]
    yield {"meta": meta, "project_dirs": project_dirs,
           "assertions": assertions, "workspace": workspace}


class TestIsScaffoldFirstGamedevPredicate:
    """The predicate itself — used by filesystem gate + agent schema block."""

    def test_replay_assertions_hold(self, replay_env):
        """Run every predicate_assert line from the replay fixture."""
        for assertion in replay_env["assertions"]:
            project = assertion["project"]
            project_dir = replay_env["project_dirs"][project]
            actual = is_scaffold_first_gamedev(project_dir)
            assert actual == assertion["expect_scaffold_first"], (
                f"project {project!r}: predicate returned {actual}, "
                f"fixture expected {assertion['expect_scaffold_first']}"
            )

    def test_nonexistent_dir_returns_false(self, tmp_path: Path):
        """The predicate must fail closed (False) on missing paths so the
        caller never gets a spurious True that locks the drone out."""
        assert is_scaffold_first_gamedev(tmp_path / "does-not-exist") is False

    def test_missing_package_json_returns_false(self, tmp_path: Path):
        proj = tmp_path / "no-pkg"
        proj.mkdir()
        assert is_scaffold_first_gamedev(proj) is False

    def test_malformed_package_json_returns_false(self, tmp_path: Path):
        """Fail-open on corrupt package.json — the drone should still be
        able to use file_read. Failing closed here would take down the
        entire design-phase schema on a stray brace."""
        proj = tmp_path / "busted-pkg"
        proj.mkdir()
        (proj / "package.json").write_text("{{{ not even remotely json")
        assert is_scaffold_first_gamedev(proj) is False

    def test_name_missing_affix_returns_false(self, tmp_path: Path):
        """Both affixes required — 'gamedev-' prefix AND '-scaffold' suffix."""
        for name in ("gamedev-platformer", "platformer-scaffold",
                     "gamedev-scaffold-mid", "random-name"):
            proj = tmp_path / name.replace("/", "_")
            proj.mkdir()
            (proj / "package.json").write_text(
                json.dumps({"name": name, "version": "0.0.1"}))
            assert is_scaffold_first_gamedev(proj) is False, \
                f"name {name!r} should not match the scaffold-first predicate"

    def test_true_for_canonical_scaffold_names(self, tmp_path: Path):
        """Canonical names from scaffolds/gamedev/*/package.json all match."""
        for name in ("gamedev-platformer-scaffold", "gamedev-jrpg-scaffold",
                     "gamedev-stealth-scaffold", "gamedev-racing-scaffold",
                     "gamedev-shooter-scaffold"):
            proj = tmp_path / name
            proj.mkdir()
            (proj / "package.json").write_text(
                json.dumps({"name": name, "version": "0.0.1"}))
            assert is_scaffold_first_gamedev(proj) is True, \
                f"canonical name {name!r} must match"

    def test_case_insensitive_match(self, tmp_path: Path):
        """Package names are conventionally lowercase but tolerate mixed."""
        proj = tmp_path / "mixed-case"
        proj.mkdir()
        (proj / "package.json").write_text(
            json.dumps({"name": "GameDev-Platformer-SCAFFOLD"}))
        assert is_scaffold_first_gamedev(proj) is True

    def test_missing_name_field_returns_false(self, tmp_path: Path):
        proj = tmp_path / "no-name"
        proj.mkdir()
        (proj / "package.json").write_text(json.dumps({"version": "0.0.1"}))
        assert is_scaffold_first_gamedev(proj) is False


class TestDesignPhaseSchemaBlockSource:
    """Source-level assertions on agent.py's design-phase file_read block.

    A full behavioral test of the schema-building path would need to
    boot the real Agent (model + registry + plan_manager) — overkill for
    a regression anchor. Instead we assert the source contains the
    predicate call inside the design-phase block, which is what
    actually makes the fix load-bearing. If a future refactor removes
    the guard (inverting the scaffold-first behavior), this test fails
    loud before the drone starts re-spiraling in prod.
    """

    def test_agent_imports_is_scaffold_first_gamedev(self):
        """The design-phase branch must call the predicate; without it,
        file_read goes back to being unconditionally opened."""
        agent_src = (Path(__file__).parent.parent / "agent.py").read_text()
        assert "is_scaffold_first_gamedev" in agent_src, (
            "tsunami/agent.py no longer references is_scaffold_first_gamedev — "
            "the design-phase file_read guard has been removed. "
            "Re-instate the guard before closing this regression."
        )
        assert "if not _scaffold_first:" in agent_src, (
            "tsunami/agent.py no longer guards the design-phase file_read "
            "addition on the scaffold-first predicate. The drone will now "
            "get file_read in every gamedev project and re-spiral on "
            "inlined data files. Re-instate the guard."
        )
