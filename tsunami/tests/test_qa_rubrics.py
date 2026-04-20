"""Tests for tsunami/qa_rubrics.py — the standalone loader that exposes
undertow_scaffolds/{web_polish,art_direction}.md rubrics for vision_gate
to embed in the VLM system prompt.

Guarantees under test:
  - web_polish is universal (applies_to = ["*"]) — fires for any scaffold
  - art_direction is gated by scaffold name per frontmatter
  - missing files / malformed frontmatter don't raise — return ""
  - output is bounded by max_chars with a truncation marker
  - rubric bodies are trimmed to the ## Questions section (token budget)
"""

import pytest

from tsunami.qa_rubrics import load_polish_rubric, _parse_frontmatter, _applies


class TestFrontmatterParser:
    def test_missing_frontmatter_returns_empty_meta(self):
        meta, body = _parse_frontmatter("## Questions\n1. foo")
        assert meta == {}
        assert "## Questions" in body

    def test_simple_scalar_keys(self):
        text = "---\nname: Web Polish\nphase: polish\n---\n\nbody"
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "Web Polish"
        assert meta["phase"] == "polish"
        assert body.strip() == "body"

    def test_list_key(self):
        text = '---\napplies_to: [landing, dashboard]\n---\nbody'
        meta, _ = _parse_frontmatter(text)
        assert meta["applies_to"] == ["landing", "dashboard"]

    def test_universal_list(self):
        text = '---\napplies_to: ["*"]\n---\nbody'
        meta, _ = _parse_frontmatter(text)
        assert meta["applies_to"] == ["*"]


class TestAppliesRouter:
    def test_no_frontmatter_is_universal(self):
        assert _applies({}, "landing") is True
        assert _applies({}, None) is True

    def test_star_matches_anything(self):
        meta = {"applies_to": ["*"]}
        assert _applies(meta, "landing") is True
        assert _applies(meta, None) is True

    def test_exact_match(self):
        meta = {"applies_to": ["landing", "dashboard"]}
        assert _applies(meta, "landing") is True
        assert _applies(meta, "dashboard") is True
        assert _applies(meta, "gamedev") is False

    def test_no_scaffold_fails_specific_list(self):
        """If a rubric lists specific scaffolds, callers without one skip it."""
        meta = {"applies_to": ["landing"]}
        assert _applies(meta, None) is False


class TestLoadPolishRubric:
    def test_universal_scaffold_includes_web_polish(self):
        out = load_polish_rubric(scaffold_name="dashboard")
        assert "RUBRIC — Web Polish" in out
        # art_direction also applies to dashboard per frontmatter.
        assert "RUBRIC — Art Direction" in out

    def test_gamedev_gets_only_web_polish(self):
        """gamedev isn't in art_direction's applies_to, so only web_polish runs."""
        out = load_polish_rubric(scaffold_name="gamedev")
        assert "RUBRIC — Web Polish" in out
        assert "RUBRIC — Art Direction" not in out

    def test_no_scaffold_still_gets_web_polish(self):
        """web_polish's applies_to ["*"] means callers without a scaffold
        still get the universal rubric."""
        out = load_polish_rubric(scaffold_name=None)
        assert "RUBRIC — Web Polish" in out
        # art_direction lists specific scaffolds, so it skips with None.
        assert "RUBRIC — Art Direction" not in out

    def test_output_contains_checklist_section(self):
        out = load_polish_rubric(scaffold_name="landing")
        assert "## Questions" in out
        assert "PASS criteria" in out or "FAIL criteria" in out

    def test_max_chars_truncates(self):
        out = load_polish_rubric(scaffold_name="landing", max_chars=400)
        assert len(out) <= 400
        assert out.endswith("[rubric block truncated]")

    def test_bogus_scaffold_falls_back_to_web_polish(self):
        """An unknown scaffold name still picks up the universal rubric."""
        out = load_polish_rubric(scaffold_name="nonexistent-scaffold-xyz")
        assert "RUBRIC — Web Polish" in out

    def test_empty_extras_no_error(self):
        out = load_polish_rubric(scaffold_name="landing", extra_names=())
        assert "RUBRIC — Web Polish" in out

    def test_unknown_extra_is_skipped(self):
        """Asking for a rubric file that doesn't exist silently drops it."""
        out = load_polish_rubric(scaffold_name="landing", extra_names=("does-not-exist",))
        assert "RUBRIC — Web Polish" in out
        assert "does-not-exist" not in out.lower()

    def test_intro_sentence_present(self):
        out = load_polish_rubric(scaffold_name="landing")
        assert out.startswith("Additional QA rubrics")

    def test_output_is_string(self):
        out = load_polish_rubric(scaffold_name="landing")
        assert isinstance(out, str)
        assert len(out) > 0


class TestSafety:
    def test_never_raises_on_missing_dir(self, monkeypatch):
        """If _SCAFFOLD_DIR is temporarily nuked, loader returns ''."""
        from tsunami import qa_rubrics as q
        monkeypatch.setattr(q, "_SCAFFOLD_DIR", q._SCAFFOLD_DIR.parent / "nonexistent_qa_dir")
        out = q.load_polish_rubric(scaffold_name="landing")
        assert out == ""
