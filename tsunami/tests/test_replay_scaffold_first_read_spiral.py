"""Replay regression for pain_scaffold_first_read_spiral (severity 4).

Anchors the scaffold-first gamedev file_read hard gate landed in 9b7b085.
The gate makes `_scaffold_first_block` return a block-reason whenever the
drone tries to file_read a data/*.json inside a gamedev-*-scaffold
project — the inlined content is already in the drone's system prompt.

Trace source: workspace/.history/session_1776736395.jsonl (ice-cavern,
Round J, 2026-04-20). Qwen3.6-35B called file_read on the same
data/enemies.json 5 times in a row while system_notes escalated from
"already in context" → "3 in a row" → "LOOP DETECTED" — all ignored.
Convention beats instruction (v5): the tool now returns is_error.

Fixture: tsunami/tests/replays/scaffold_first_read_spiral.jsonl
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import FileRead, _scaffold_first_block


REPLAY_PATH = Path(__file__).parent / "replays" / "scaffold_first_read_spiral.jsonl"


class FakeConfig:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _materialize_scaffold(workspace: Path, scaffold: dict) -> Path:
    """Lay down the project tree described by a {"kind": "scaffold", ...} line."""
    project_dir = workspace / "deliverables" / scaffold["project"]
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "package.json").write_text(json.dumps(scaffold["package_json"]))
    for rel, content in scaffold.get("files", {}).items():
        target = project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return project_dir


@pytest.fixture
def replay_env():
    """Materialize the replay's scaffold into a tmpdir with the canonical
    workspace layout the resolver expects (workspace_dir/.name == 'workspace').
    """
    root = tempfile.mkdtemp(prefix="kelp_replay_")
    workspace = Path(root) / "workspace"
    workspace.mkdir()
    events = _load_replay(REPLAY_PATH)
    meta = next(e for e in events if e["kind"] == "meta")
    scaffold = next(e for e in events if e["kind"] == "scaffold")
    _materialize_scaffold(workspace, scaffold)
    traces = [e for e in events if e["kind"] == "trace"]
    tool = FileRead(FakeConfig(str(workspace)))
    yield {"meta": meta, "scaffold": scaffold, "traces": traces,
           "workspace": workspace, "tool": tool}


class TestScaffoldFirstReadSpiralReplay:
    """Replay the ice-cavern read-spiral against the live tool surface.

    Each trace line from session_1776736395 must return is_error=True with
    the expected block-reason fragments. Without the gate (pre-9b7b085),
    these reads succeeded silently and the drone kept spiraling — that
    is exactly what we're anchoring against.
    """

    def test_replay_fixture_is_well_formed(self, replay_env):
        """Sanity: the replay file parses, has meta+scaffold+≥1 trace."""
        assert replay_env["meta"]["slug"] == "scaffold_first_read_spiral"
        assert replay_env["meta"]["fix_commit"] == "9b7b085"
        assert replay_env["scaffold"]["package_json"]["name"].startswith("gamedev-")
        assert replay_env["scaffold"]["package_json"]["name"].endswith("-scaffold")
        assert len(replay_env["traces"]) >= 4, \
            "replay must include multiple reads to reflect the actual spiral"

    def test_all_traced_reads_hit_the_gate(self, replay_env):
        """Every file_read in the recorded spiral must be blocked.

        Covers path-form variations the drone used across iters:
          - workspace/deliverables/<p>/data/enemies.json
          - ./workspace/deliverables/<p>/data/enemies.json
          - deliverables/<p>/data/enemies.json
          - file_path kwarg (Qwen-canonical) instead of path (training-canonical)
        """
        tool = replay_env["tool"]
        for trace in replay_env["traces"]:
            args = dict(trace["args"])
            expect = trace["expect"]
            result = _run(tool.execute(**args))
            assert result.is_error == expect["is_error"], (
                f"iter {trace['iter']} args={args}: "
                f"expected is_error={expect['is_error']}, got {result.is_error}. "
                f"content={result.content!r}"
            )
            for fragment in expect["contains"]:
                assert fragment in result.content, (
                    f"iter {trace['iter']}: block-reason missing {fragment!r}. "
                    f"Got: {result.content!r}"
                )

    def test_block_reason_instructs_next_action(self, replay_env):
        """The block reason must tell the drone what to do instead.

        The whole point of the structural fix is that the advisory
        "you already have it in context" didn't land — the hard-gate
        message has to be unambiguous: pivot to file_write.
        """
        tool = replay_env["tool"]
        trace = replay_env["traces"][0]
        result = _run(tool.execute(**trace["args"]))
        assert result.is_error
        content = result.content
        assert "file_write" in content, \
            "block reason must name file_write as the next action"
        assert "already inlined" in content or "in context" in content.lower(), \
            "block reason must explain WHY the read is blocked"
        assert "hard gate" in content.lower(), \
            "block reason must signal this is structural (not a nudge)"


class TestScaffoldFirstGateBoundaries:
    """Negative cases — the gate must NOT over-fire.

    Without these, a future refactor could tighten the gate until it
    blocks legitimate reads. The whole principle (v5 convention-beats-
    instruction) requires the structural rule be precise.
    """

    def setup_method(self):
        self.root = tempfile.mkdtemp(prefix="kelp_boundary_")
        self.workspace = Path(self.root) / "workspace"
        self.workspace.mkdir()
        self.tool = FileRead(FakeConfig(str(self.workspace)))

    def _make_project(self, name: str, pkg_name: str, files: dict[str, str]) -> Path:
        proj = self.workspace / "deliverables" / name
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "package.json").write_text(json.dumps({"name": pkg_name, "version": "0.0.1"}))
        for rel, content in files.items():
            t = proj / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(content)
        return proj

    def test_non_scaffold_package_name_reads_through(self):
        """A plain project (no gamedev-*-scaffold name) reads normally."""
        self._make_project("plain-app", "plain-app",
                           {"data/items.json": "[]"})
        result = _run(self.tool.execute(
            path="workspace/deliverables/plain-app/data/items.json"))
        assert not result.is_error, \
            f"non-scaffold project should read through; got: {result.content!r}"
        assert "[]" in result.content

    def test_non_data_json_reads_through(self):
        """A JSON outside data/ (e.g. src/config.json) is not inlined,
        so the gate must let it through."""
        self._make_project("ice-cavern", "gamedev-platformer-scaffold",
                           {"src/config.json": "{\"debug\": true}"})
        result = _run(self.tool.execute(
            path="workspace/deliverables/ice-cavern/src/config.json"))
        assert not result.is_error, \
            f"non-data/ JSON should read through; got: {result.content!r}"

    def test_non_json_in_data_reads_through(self):
        """data/README.md is not an inlined data file; gate must skip it."""
        self._make_project("ice-cavern", "gamedev-platformer-scaffold",
                           {"data/README.md": "# Data schemas"})
        result = _run(self.tool.execute(
            path="workspace/deliverables/ice-cavern/data/README.md"))
        assert not result.is_error
        assert "Data schemas" in result.content

    def test_data_json_outside_any_project_reads_through(self):
        """A data/*.json with no sibling package.json is not a scaffold."""
        loose = self.workspace / "data"
        loose.mkdir(parents=True)
        (loose / "stuff.json").write_text("[]")
        result = _run(self.tool.execute(path="workspace/data/stuff.json"))
        assert not result.is_error

    def test_scaffold_name_mismatch_reads_through(self):
        """Package name must START with 'gamedev-' AND END with '-scaffold'.
        A name missing either affix does not trip the gate."""
        for pkg_name in ("gamedev-platformer", "platformer-scaffold", "some-app"):
            proj_name = pkg_name.replace("/", "_")
            self._make_project(proj_name, pkg_name, {"data/x.json": "[]"})
            result = _run(self.tool.execute(
                path=f"workspace/deliverables/{proj_name}/data/x.json"))
            assert not result.is_error, \
                f"pkg name {pkg_name!r} should not trip the gate; got: {result.content!r}"


class TestScaffoldFirstBlockHelper:
    """Direct tests on _scaffold_first_block — keeps the helper's contract
    independent of FileRead.execute() plumbing.
    """

    def test_returns_none_for_non_existent_package(self, tmp_path: Path):
        data_dir = tmp_path / "foo" / "data"
        data_dir.mkdir(parents=True)
        target = data_dir / "enemies.json"
        target.write_text("[]")
        # No package.json → not a scaffold context → None.
        assert _scaffold_first_block(target) is None

    def test_returns_block_for_scaffold_data_json(self, tmp_path: Path):
        proj = tmp_path / "ice-cavern"
        (proj / "data").mkdir(parents=True)
        (proj / "package.json").write_text(
            json.dumps({"name": "gamedev-rpg-scaffold", "version": "0.0.1"}))
        target = proj / "data" / "enemies.json"
        target.write_text("[]")
        reason = _scaffold_first_block(target)
        assert reason is not None
        assert "BLOCKED" in reason
        assert "enemies.json" in reason

    def test_returns_none_for_mangled_package_json(self, tmp_path: Path):
        """If package.json is malformed, the gate must fail open (read through)
        rather than failing closed and locking the drone out of everything."""
        proj = tmp_path / "ice-cavern"
        (proj / "data").mkdir(parents=True)
        (proj / "package.json").write_text("{ not valid json")
        target = proj / "data" / "enemies.json"
        target.write_text("[]")
        assert _scaffold_first_block(target) is None
