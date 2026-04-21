"""Replay regression for the hoisted scaffold-first gate (sev 5,
Round 11). Closes three live-verified exfil paths (FileEdit,
SummarizeFile, MatchGrep) + five sev-4 predicate bypasses
(case-insensitive suffix, nested subdirs, non-JSON, etc).

Sources:
  pain_scaffold_first_gate_three_bypasses (sev 5)
  pain_scaffold_first_file_edit_leak (sev 5)
  pain_scaffold_first_summarize_leak (sev 5)
  pain_scaffold_first_match_grep_leak (sev 4)
  pain_scaffold_first_gate_fail_open_paths (sev 4)

All filed by Current (counter-propagating auditor) on 2026-04-20
after Round 1's hard gate (9b7b085) was confirmed to close one
door while four stayed open.

Fixture: tsunami/tests/replays/scaffold_first_gate_hoist.jsonl
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import (
    FileRead, FileEdit, FileAppend,
    is_scaffold_first_inlined,
)
from tsunami.tools.discovery import SummarizeFile, MatchGrep


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "scaffold_first_gate_hoist.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class FakeConfig:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir


def _materialize(workspace: Path, scaffold: dict) -> Path:
    project = workspace / "deliverables" / scaffold["project"]
    project.mkdir(parents=True, exist_ok=True)
    (project / "package.json").write_text(json.dumps(scaffold["package_json"]))
    for rel, content in scaffold.get("files", {}).items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return project


@pytest.fixture
def env():
    root = tempfile.mkdtemp(prefix="kelp_gate_hoist_")
    ws = Path(root) / "workspace"
    ws.mkdir()
    events = _load_replay(REPLAY_PATH)
    scaffold = next(e for e in events if e["kind"] == "scaffold")
    project = _materialize(ws, scaffold)
    meta = next(e for e in events if e["kind"] == "meta")
    return {
        "meta": meta,
        "scaffold": scaffold,
        "project": project,
        "ws": ws,
        "predicate_cases": [e for e in events if e["kind"] == "predicate_case"],
        "gate_cases": [e for e in events if e["kind"] == "gate_case"],
    }


class TestPredicateReplay:
    def test_fixture_well_formed(self, env):
        assert env["meta"]["severity"] == 5
        assert len(env["predicate_cases"]) >= 6, \
            "need enough cases to cover canonical+nested+case-insens+negatives"
        assert len(env["gate_cases"]) >= 8, \
            "need gate_cases for file_read, file_edit, file_append, summarize_file"

    def test_every_predicate_case_matches_expect(self, env):
        for case in env["predicate_cases"]:
            target = env["project"] / case["path"]
            got = is_scaffold_first_inlined(target)
            assert got == case["expect_inlined"], (
                f"case {case['desc']!r}: predicate returned {got}, "
                f"fixture expected {case['expect_inlined']}"
            )


class TestGateHoistedAcrossReaders:
    def _mk_rel_path(self, project: Path, rel: str, ws: Path) -> str:
        """Resolver-compatible path. Use `workspace/deliverables/<proj>/<rel>`
        since the resolver strips the `workspace/` prefix."""
        return f"workspace/deliverables/{project.name}/{rel}"

    def test_file_read_blocks_canonical_and_nested(self, env):
        tool = FileRead(FakeConfig(str(env["ws"])))
        for case in env["gate_cases"]:
            if case["tool"] != "file_read":
                continue
            path_arg = self._mk_rel_path(env["project"], case["path"], env["ws"])
            result = _run(tool.execute(path=path_arg))
            if case["expect_blocked"]:
                assert result.is_error, f"file_read on {case['path']} should block"
                assert "BLOCKED" in result.content
            else:
                # Non-blocked cases: must succeed (README.md in data/ is not JSON)
                assert not result.is_error, (
                    f"file_read on {case['path']} should pass; "
                    f"got: {result.content[:200]!r}"
                )

    def test_file_edit_blocks_on_inlined(self, env):
        tool = FileEdit(FakeConfig(str(env["ws"])))
        for case in env["gate_cases"]:
            if case["tool"] != "file_edit":
                continue
            path_arg = self._mk_rel_path(env["project"], case["path"], env["ws"])
            result = _run(tool.execute(
                path=path_arg,
                old_content="anything",
                new_content="replaced",
            ))
            if case["expect_blocked"]:
                assert result.is_error
                assert "BLOCKED" in result.content
                # Critical: the block reason must NOT contain the full file
                # content. The whole point is exfil prevention.
                assert "frost-goomba" not in result.content, (
                    "FileEdit block message LEAKED inlined content; "
                    "0-match preview bypass is still open"
                )

    def test_file_append_blocks_on_inlined(self, env):
        tool = FileAppend(FakeConfig(str(env["ws"])))
        for case in env["gate_cases"]:
            if case["tool"] != "file_append":
                continue
            path_arg = self._mk_rel_path(env["project"], case["path"], env["ws"])
            result = _run(tool.execute(path=path_arg, content=",{\"id\":\"x\"}"))
            if case["expect_blocked"]:
                assert result.is_error
                assert "BLOCKED" in result.content

    def test_summarize_file_blocks_on_inlined(self, env):
        tool = SummarizeFile(FakeConfig(str(env["ws"])))
        for case in env["gate_cases"]:
            if case["tool"] != "summarize_file":
                continue
            path_arg = self._mk_rel_path(env["project"], case["path"], env["ws"])
            result = _run(tool.execute(path=path_arg))
            if case["expect_blocked"]:
                assert result.is_error, (
                    f"summarize_file should block on {case['path']}; "
                    f"got content: {result.content[:200]!r}"
                )
                assert "BLOCKED" in result.content
                # Critical: summarize's head+tail must NOT leak through
                assert "frost-goomba" not in result.content

    def test_match_grep_skips_inlined_files(self, env):
        """match_grep fallback path (Python scan): pattern should not
        return any lines from scaffold-first inlined files. Legitimate
        matches elsewhere still work.

        We search for content that EXISTS inside data/enemies.json and
        doesn't exist elsewhere ('frost-goomba'). A leak would surface
        as a `:<line>:` hit. The 'No matches' reply still echoes the
        pattern — that's the pattern, not the file content — so we
        check the structure of the response, not the raw token.
        """
        tool = MatchGrep(FakeConfig(str(env["ws"])))
        result = _run(tool.execute(
            pattern="frost-goomba",
            directory=f"workspace/deliverables/{env['project'].name}",
        ))
        # A hit line looks like `<rel>:<lineno>:<content>`. If the gate
        # leaks, we'd see `enemies.json:1:[{"id":"frost-goomba"...`.
        assert "enemies.json:" not in result.content, (
            f"match_grep leaked inlined file hit: {result.content[:200]!r}"
        )
        # Search for content in src/main.ts — should still find it
        result = _run(tool.execute(
            pattern="boot",
            directory=f"workspace/deliverables/{env['project'].name}",
        ))
        assert "main.ts" in result.content, \
            "match_grep should still find legitimate matches outside data/"


class TestExfilBypassClassesClosed:
    """Targeted assertions on the five sev-4 bypass variants from
    pain_scaffold_first_gate_fail_open_paths."""

    def setup_method(self):
        self.root = tempfile.mkdtemp(prefix="kelp_bypass_")
        self.ws = Path(self.root) / "workspace"
        self.ws.mkdir()
        proj = self.ws / "deliverables" / "bypass-proj"
        (proj / "data" / "nested").mkdir(parents=True)
        (proj / "src" / "scenes").mkdir(parents=True)
        (proj / "package.json").write_text(
            json.dumps({"name": "bypass-proj", "version": "0.0.1"})
        )
        (proj / "data" / "enemies.json").write_text("[{\"id\":\"alpha\"}]")
        (proj / "data" / "Enemies.JSON").write_text("[{\"id\":\"upper\"}]")
        (proj / "data" / "nested" / "deep.json").write_text("[{\"id\":\"deep\"}]")
        (proj / "data" / "archive.json.bak").write_text("[{\"id\":\"old\"}]")
        self.proj = proj
        self.tool = FileRead(FakeConfig(str(self.ws)))

    def _read(self, rel: str):
        return _run(self.tool.execute(
            path=f"workspace/deliverables/bypass-proj/{rel}",
        ))

    def test_case_insensitive_suffix_blocked(self):
        """Round 1 gate checked suffix == '.json' case-sensitively —
        data/Enemies.JSON passed through. Now blocked."""
        result = self._read("data/Enemies.JSON")
        assert result.is_error, f"case-JSON bypass not closed: {result.content!r}"
        assert "BLOCKED" in result.content

    def test_nested_subdir_blocked(self):
        """Round 1 gate checked parent.name == 'data' — nested data/
        subdirs bypassed. Now blocked via relative_to check."""
        result = self._read("data/nested/deep.json")
        assert result.is_error
        assert "BLOCKED" in result.content

    def test_json_bak_suffix_not_inlined(self):
        """.json.bak is NOT inlined — suffix property is '.bak'. The
        drone shouldn't be blocked from reading backup files. Validates
        the gate's precision, not just its reach."""
        result = self._read("data/archive.json.bak")
        assert not result.is_error, (
            f".json.bak should pass — it's not inlined. Got: "
            f"{result.content[:200]!r}"
        )

    def test_missing_scenes_dir_fails_open_legacy(self):
        """Without src/scenes, the filesystem-signal branch of
        is_scaffold_first_gamedev returns False. With the legacy name
        marker also absent (package.json name is 'bypass-proj' not
        'gamedev-*-scaffold'), the predicate fails open — drone can
        read data/*.json. Documents the gate's boundary."""
        import shutil
        shutil.rmtree(self.proj / "src" / "scenes")
        result = self._read("data/enemies.json")
        # With both signals failing, the predicate returns False and
        # the read proceeds. This test is a boundary marker, not a
        # regression — documents that the gate relies on a detectable
        # scaffold-first signal.
        assert not result.is_error
