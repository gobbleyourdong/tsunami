"""Replay regression for pain_pre_scaffold_name_extraction (severity 2).

Anchors `tsunami.pre_scaffold_naming.derive_project_name` and the
agent.py delegation site. The name-extraction regex has a 3-commit
history of quiet drift (e056b66 → 4f8094a → d99baf5) — each tightening
fixed a specific failure mode without a test corpus to prove the
previous cases still worked. This fixture pins 20 prompts the helper
must handle so a future regex refactor can't silently reintroduce
the em-dash / parameter-detail / fallback bugs.

Fixture: tsunami/tests/replays/pre_scaffold_name_extraction.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tsunami.pre_scaffold_naming import derive_project_name


REPLAY_PATH = (
    Path(__file__).parent / "replays" / "pre_scaffold_name_extraction.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestPreScaffoldNameExtractionReplay:
    @pytest.fixture
    def cases(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "case"]

    def test_fixture_well_formed(self, cases):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "pre_scaffold_name_extraction"
        assert len(cases) >= 15, \
            "fixture must cover the regex's corpus: called/named/titled " \
            "keywords, em-dash/en-dash/hyphen/colon separators, single " \
            "token names, save_hint, fallback path, sanitization, truncation"

    def test_every_case_matches_expect(self, cases):
        for case in cases:
            got = derive_project_name(
                case["prompt"],
                save_hint=case.get("save_hint"),
            )
            assert got == case["expect"], (
                f"case {case['desc']!r}: expected {case['expect']!r}, "
                f"got {got!r}. prompt={case['prompt']!r}"
            )


class TestDeriveProjectNameInvariants:
    """Properties that should hold regardless of the specific regex."""

    def test_returns_nonempty_string_always(self):
        """No input should produce an empty slug — fallback is 'game'."""
        for prompt in ("", "   ", "???", "!!!", "Build .", "a b c"):
            got = derive_project_name(prompt)
            assert got, f"empty slug from prompt {prompt!r}"
            assert isinstance(got, str)

    def test_result_is_url_safe(self):
        """Every produced slug must be alphanumeric + [_-]. Sanitize is
        load-bearing because the slug becomes a directory name."""
        import re as _re
        prompts = [
            "Build a game called X",
            "Build a game called Crystal@Saga",
            "Build a 2D platformer called Lava Leap — 3 levels",
            "Build a game called héllo wörld",  # unicode → stripped
            "",
        ]
        for p in prompts:
            got = derive_project_name(p)
            assert _re.fullmatch(r"[a-z0-9_-]+", got), (
                f"slug {got!r} from prompt {p!r} has disallowed chars"
            )

    def test_slug_never_exceeds_40_chars(self):
        long_name = "A " * 50  # 100 chars of Capital tokens
        got = derive_project_name(f"Build a game called {long_name}")
        assert len(got) <= 40, f"slug too long: {got!r}"

    def test_save_hint_not_mutated(self):
        """save_hint is a trust-the-caller short-circuit — it returns
        verbatim. No lowercasing, no sanitization, no truncation. This
        keeps the pre-scaffold contract predictable for callers that
        have already resolved the slug."""
        assert derive_project_name("x", save_hint="MyCustom_Slug-42") \
            == "MyCustom_Slug-42"

    def test_idempotence_on_clean_slugs(self):
        """Running the helper on its own output should either return
        the same slug or reduce to 'game' (if the input was a pure
        fallback). Keeps the contract safe for pipelines that might
        re-derive a name from an already-derived name."""
        seeds = ["lava-leap", "ice-cavern", "crystal-saga", "x"]
        for s in seeds:
            derived = derive_project_name(f"Build a game called {s.title()}")
            # Now derive from the output, formatted as a prompt again.
            # We don't assert equality of every intermediate — only that
            # the pipeline remains URL-safe and non-empty.
            redone = derive_project_name(derived)
            assert redone
            assert all(c.isalnum() or c in "_-" for c in redone)


class TestAgentDelegationSource:
    """Source-level assertions that agent.py still delegates to the
    helper. A future inline re-implementation of the regex would
    defeat the whole point of having a test corpus."""

    def test_agent_imports_helper(self):
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        assert "from .pre_scaffold_naming import derive_project_name" in src, (
            "agent.py no longer imports derive_project_name from "
            "pre_scaffold_naming. The name-extraction regex has been "
            "re-inlined — re-instate the delegation so the test "
            "corpus at test_replay_pre_scaffold_name_extraction.py "
            "stays load-bearing."
        )

    def test_old_inline_regex_is_gone(self):
        """The original inline regex in _pre_scaffold has been removed.
        A revert would regrow the drift history."""
        src = (Path(__file__).parent.parent / "agent.py").read_text()
        # The old inline block had this literal regex. If it reappears,
        # derive_project_name's corpus isn't actually gating what runs.
        assert (
            "(?:called|named|titled)\\s+([A-Z][A-Za-z0-9]*"
            not in src
        ), (
            "The inline 'called|named|titled' regex is back in agent.py. "
            "The helper is meant to be the single source of truth."
        )
