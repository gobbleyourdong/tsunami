"""Replay regression for pain_file_read_path_guessing (severity 3).

Anchors `_suggest_similar_paths` in tsunami/tools/filesystem.py and the
two not-found branches in FileRead / FileEdit that surface its output
in their error messages.

Trace source: 6 sessions 2026-04-20 (1776728985, 1776729573, 1776730505,
1776733458, 1776733868, 1776738158) — 12 "File not found" errors. The
drone guesses multiple prefix variants of the same logical path
(data/foo.json, workspace/deliverables/<p>/data/foo.json, deliverables/
<p>/data/foo.json) and burns an iteration per miss. The suggested-
paths helper gives the drone one structural nudge — the actual path —
instead of N rejections that each look the same.

Fixture: tsunami/tests/replays/file_read_path_guessing.jsonl
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import FileRead, _suggest_similar_paths


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "file_read_path_guessing.jsonl"
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
def replay_env():
    root = tempfile.mkdtemp(prefix="kelp_path_guess_")
    workspace = Path(root) / "workspace"
    workspace.mkdir()
    events = _load_replay(REPLAY_PATH)
    scaffold = next(e for e in events if e["kind"] == "scaffold")
    _materialize(workspace, scaffold)
    cases = [e for e in events if e["kind"] == "suggest_case"]
    meta = next(e for e in events if e["kind"] == "meta")
    yield {"meta": meta, "workspace": workspace, "cases": cases}


class TestSuggestSimilarPathsReplay:
    def test_fixture_well_formed(self, replay_env):
        assert replay_env["meta"]["slug"] == "file_read_path_guessing"
        assert len(replay_env["cases"]) >= 4, \
            "fixture must cover exact-match, fuzzy-typo, wrong-prefix, no-match"

    def test_every_case_matches_expect(self, replay_env):
        ws = str(replay_env["workspace"])
        for case in replay_env["cases"]:
            suggestions = _suggest_similar_paths(case["requested"], ws, limit=3)
            if "expect_count" in case:
                assert len(suggestions) == case["expect_count"], (
                    f"case {case['desc']!r}: expected "
                    f"{case['expect_count']} suggestions, got {suggestions!r}"
                )
            if "expect_contains" in case:
                for needle in case["expect_contains"]:
                    assert any(needle in s for s in suggestions), (
                        f"case {case['desc']!r}: no suggestion contains "
                        f"{needle!r}. Got: {suggestions!r}"
                    )


class TestSuggestHelperBoundaries:
    def setup_method(self):
        self.root = tempfile.mkdtemp(prefix="kelp_suggest_")
        self.ws = Path(self.root) / "workspace"
        self.ws.mkdir()

    def _touch(self, rel: str, content: str = "") -> Path:
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def test_empty_workspace_returns_empty(self):
        assert _suggest_similar_paths("foo.json", str(self.ws)) == []

    def test_nonexistent_workspace_returns_empty(self):
        assert _suggest_similar_paths(
            "foo.json", str(self.ws / "does-not-exist"),
        ) == []

    def test_empty_requested_returns_empty(self):
        self._touch("deliverables/x/a.json", "[]")
        assert _suggest_similar_paths("", str(self.ws)) == []
        assert _suggest_similar_paths("   ", str(self.ws)) == []

    def test_limit_respected(self):
        for i in range(10):
            self._touch(f"deliverables/proj/data/file_{i}.json", "[]")
        suggestions = _suggest_similar_paths(
            "file_3.json", str(self.ws), limit=3,
        )
        assert len(suggestions) <= 3

    def test_node_modules_pruned(self):
        """node_modules is a noisy dir that would drown useful matches
        under gamedev scaffolds that vendor @engine etc. The helper must
        not surface node_modules files as suggestions."""
        self._touch("deliverables/proj/node_modules/pkg/tracks.json", "[]")
        self._touch("deliverables/proj/data/tracks.json", "[]")
        suggestions = _suggest_similar_paths(
            "tracks.json", str(self.ws), limit=3,
        )
        assert any("data/tracks.json" in s for s in suggestions)
        assert not any("node_modules" in s for s in suggestions), \
            f"node_modules leaked into suggestions: {suggestions!r}"

    def test_git_dir_pruned(self):
        """Internal dirs like .git should never surface as suggestions."""
        self._touch("deliverables/proj/.git/objects/abc", "")
        self._touch("deliverables/proj/src/main.ts", "x")
        suggestions = _suggest_similar_paths(
            "objects/abc", str(self.ws), limit=3,
        )
        assert not any(".git" in s for s in suggestions)

    def test_case_insensitive_basename_match(self):
        self._touch("deliverables/proj/data/Tracks.json", "[]")
        suggestions = _suggest_similar_paths(
            "data/tracks.json", str(self.ws), limit=3,
        )
        assert any("Tracks.json" in s for s in suggestions)

    def test_workspace_without_deliverables_still_scans(self):
        """If deliverables/ doesn't exist yet (fresh session), fall back
        to scanning the whole workspace."""
        self._touch("loose/file_a.json", "[]")
        suggestions = _suggest_similar_paths(
            "file_a.json", str(self.ws), limit=3,
        )
        assert any("file_a.json" in s for s in suggestions)


class TestFileReadNotFoundSurfacesSuggestions:
    """End-to-end: FileRead.execute with a path the resolver can't find
    must include the suggestion bullet list in its error content."""

    def setup_method(self):
        self.root = tempfile.mkdtemp(prefix="kelp_fr_notfound_")
        self.ws = Path(self.root) / "workspace"
        self.ws.mkdir()
        proj = self.ws / "deliverables" / "neon-drift"
        (proj / "data").mkdir(parents=True)
        (proj / "package.json").write_text(
            json.dumps({"name": "gamedev-racing-scaffold", "version": "0.0.1"})
        )
        (proj / "data" / "tracks.json").write_text("[]")
        (proj / "data" / "cars.json").write_text("[]")
        self.tool = FileRead(FakeConfig(str(self.ws)))

    def test_typo_path_gets_suggestion(self):
        # "tracs.json" typo — fuzzy basename match should surface tracks.json.
        result = _run(self.tool.execute(
            path="workspace/deliverables/neon-drift/data/tracs.json",
        ))
        assert result.is_error
        assert "File not found" in result.content
        assert "Did you mean" in result.content
        assert "tracks.json" in result.content

    def test_wrong_prefix_gets_suggestion(self):
        # Missing workspace/ prefix, missing deliverables/ hop, bare 'data/'.
        # Resolver fails to find it; suggester should offer the canonical path.
        result = _run(self.tool.execute(path="assets/raw/tracks.json"))
        assert result.is_error
        assert "File not found" in result.content
        assert "tracks.json" in result.content

    def test_no_match_falls_back_to_bare_error(self):
        """When nothing resembles the request, don't tack on an empty
        'Did you mean' block — just the original error."""
        result = _run(self.tool.execute(path="totally_bogus_xyzabc.txt"))
        assert result.is_error
        assert "File not found" in result.content
        # Bare error: no 'Did you mean' header when no suggestions.
        assert "Did you mean" not in result.content

    def test_existing_file_unaffected(self):
        # Add a non-data/ file so the scaffold-first-block from Round 1
        # (which blocks reads on data/*.json in gamedev-*-scaffold
        # projects) doesn't mask this test. We want to confirm the
        # suggestion plumbing doesn't inject itself into successful
        # reads — any existing readable file suffices.
        src_dir = self.ws / "deliverables" / "neon-drift" / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "README.md").write_text("# neon-drift")
        result = _run(self.tool.execute(
            path="workspace/deliverables/neon-drift/src/README.md",
        ))
        assert not result.is_error
        assert "Did you mean" not in result.content
