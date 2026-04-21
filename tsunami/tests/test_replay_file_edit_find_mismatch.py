"""Replay regression for pain_file_edit_find_mismatch (severity 2).

Anchors the 'closest actual line' hint added to file_edit's
'Text not found' error in tsunami/tools/filesystem.py. The drone
often misses a file_edit find-string by a single character class
(underscore vs hyphen, quote style, trailing punctuation). The
existing full-file preview gives the drone what it needs but
requires it to scan 40 lines. Naming the closest actual line
explicitly converges faster.

Trace source: 2 sessions 2026-04-20 (1776732622 crystal-saga,
1776737362 ninja-grove). Both recovered on the second attempt; the
hint aims to collapse them into one attempt.

Fixture: tsunami/tests/replays/file_edit_find_mismatch.jsonl
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import FileEdit


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "file_edit_find_mismatch.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class FakeConfig:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir


@pytest.fixture
def tmp_workspace():
    root = tempfile.mkdtemp(prefix="kelp_edit_mismatch_")
    workspace = Path(root) / "workspace"
    workspace.mkdir()
    return workspace


class TestFileEditMismatchHintReplay:
    @pytest.fixture
    def cases(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "mismatch_case"]

    def test_fixture_well_formed(self, cases):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "file_edit_find_mismatch"
        assert len(cases) >= 4, \
            "fixture must cover hint-positive + hint-negative + defensive cases"

    def test_every_case_matches_expect(self, cases, tmp_workspace):
        tool = FileEdit(FakeConfig(str(tmp_workspace)))
        for case in cases:
            # Materialize the file under a fresh project so each case is isolated.
            slug = case["desc"][:20].replace(" ", "_").replace("/", "_")
            proj = tmp_workspace / "deliverables" / f"p_{slug}"
            proj.mkdir(parents=True, exist_ok=True)
            target = proj / "config.json"
            target.write_text(case["file_content"])

            result = _run(tool.execute(
                path=str(target),
                old_content=case["old_text"],
                new_content="REPLACED",
            ))

            # Every mismatch case should return is_error with the baseline
            # "Text not found" prefix regardless of whether the hint fires.
            assert result.is_error, (
                f"case {case['desc']!r}: expected mismatch error, got success"
            )
            assert "Text not found" in result.content
            assert "Current file:" in result.content

            if case["expect_hint"]:
                assert "Closest actual line:" in result.content, (
                    f"case {case['desc']!r}: expected hint; got: "
                    f"{result.content[:400]!r}"
                )
                assert case["expect_hint_contains_line"] in result.content, (
                    f"case {case['desc']!r}: hint missing expected token "
                    f"{case['expect_hint_contains_line']!r}"
                )
            else:
                assert "Closest actual line:" not in result.content, (
                    f"case {case['desc']!r}: unexpected hint in content: "
                    f"{result.content[:400]!r}"
                )


class TestHintInvariants:
    """Boundary properties of the hint logic — small, direct cases."""

    def setup_method(self):
        self.root = tempfile.mkdtemp(prefix="kelp_hint_")
        self.ws = Path(self.root) / "workspace"
        self.ws.mkdir()
        self.tool = FileEdit(FakeConfig(str(self.ws)))

    def _make_file(self, content: str) -> Path:
        proj = self.ws / "deliverables" / "p"
        proj.mkdir(parents=True, exist_ok=True)
        target = proj / "f.json"
        target.write_text(content)
        return target

    def test_hint_is_omitted_when_exact_token_already_present(self):
        """Defensive: if the find-string's first line exactly equals a
        real line, don't surface the hint (that'd be noise — the mismatch
        is elsewhere in a multi-line old_text)."""
        target = self._make_file("line1\nline2\nline3\n")
        # Match line1 exactly on its own, but bundle it with a phantom
        # second line to force an overall mismatch.
        result = _run(self.tool.execute(
            path=str(target),
            old_content="line1\nPHANTOM_SECOND_LINE",
            new_content="REPLACED",
        ))
        assert result.is_error
        # First line of old_text is "line1", an exact match. Matches[0]
        # would equal first_old_line; the helper suppresses the hint.
        assert "Closest actual line:" not in result.content

    def test_hint_fires_on_realistic_json_key_drift(self):
        target = self._make_file(
            '{\n'
            '  "character_id": "ninja",\n'
            '  "move_speed": 5\n'
            '}\n'
        )
        result = _run(self.tool.execute(
            path=str(target),
            old_content='"character-id": "ninja",',
            new_content='"character-id": "shadow-ninja",',
        ))
        assert result.is_error
        assert "Closest actual line:" in result.content
        assert "character_id" in result.content

    def test_hint_omitted_when_file_is_empty(self):
        target = self._make_file("")
        result = _run(self.tool.execute(
            path=str(target),
            old_content="anything",
            new_content="REPLACED",
        ))
        assert result.is_error
        # Empty file: no candidate lines → no hint possible.
        assert "Closest actual line:" not in result.content
