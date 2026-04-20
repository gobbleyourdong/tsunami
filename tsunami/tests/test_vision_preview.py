"""Tests for tsunami.vision_preview — the composed-prompt preview tool.

Covers: baseline-only mode, rubric-on default, style injection, scaffold
routing (landing gets art_direction + web_polish; gamedev only web_polish),
and CLI surface via main()."""

from tsunami.vision_preview import compose, main


class TestCompose:
    def test_baseline_without_rubric(self):
        out = compose(scaffold="landing", with_rubric=False)
        assert "You are a visual QA reviewer" in out
        assert "RUBRIC —" not in out

    def test_landing_gets_both_rubrics(self):
        out = compose(scaffold="landing", with_rubric=True)
        assert "RUBRIC — Web Polish" in out
        assert "RUBRIC — Art Direction" in out

    def test_gamedev_only_web_polish(self):
        out = compose(scaffold="gamedev", with_rubric=True)
        assert "RUBRIC — Web Polish" in out
        assert "RUBRIC — Art Direction" not in out

    def test_style_hint_injected(self):
        out = compose(scaffold="landing", style_name="editorial_dark", with_rubric=False)
        assert "editorial_dark" in out
        assert "Style doctrine in play" in out

    def test_rubric_adds_substantial_chars(self):
        """Turning rubric on should roughly quadruple the prompt for landing."""
        bare = compose(scaffold="landing", with_rubric=False)
        full = compose(scaffold="landing", with_rubric=True)
        assert len(full) > len(bare) * 2

    def test_no_scaffold_still_returns_baseline(self):
        out = compose(scaffold=None, with_rubric=True)
        assert "You are a visual QA reviewer" in out


class TestMainCLI:
    def test_default_invocation_returns_zero(self, capsys):
        rc = main(["--scaffold", "landing"])
        assert rc == 0
        captured = capsys.readouterr().out
        assert "visual QA reviewer" in captured
        assert "RUBRIC" in captured

    def test_no_rubric_flag_strips_rubric_section(self, capsys):
        rc = main(["--scaffold", "landing", "--no-rubric"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "RUBRIC" not in out

    def test_count_mode_prints_metadata_only(self, capsys):
        rc = main(["--scaffold", "landing", "--count"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "composed_chars=" in out
        assert "scaffold=landing" in out
        # Count line shouldn't dump the whole prompt.
        assert "RUBRIC" not in out
        assert "You are a visual QA reviewer" not in out
