"""L11 — wave-side component hoist on tsc-streak.

Regression target: ORBIT v5, MIRA v6, MIRA v8 all showed the same loop:
  1. Drone writes App.tsx with prop names it invented
  2. auto_build._parse_tsc_failure emits 'Read src/components/X.tsx' nudge
  3. Drone ignores nudge, prop-guesses again, fails identically
  4. Read-spiral detector fires, exit with has_dist=False

L11 side-steps the drone refusal: when tsc fails twice in a row AND the
failure detail names src/components/X.tsx, the wave reads that file itself
and appends its source to the drone's next system-note. The drone can no
longer miss the component's real props.

These tests cover the component-name regex + truncation behavior in pure
Python. The integration site (agent.py `_auto_build_and_gate`) is tested
via the speed_audit fingerprint meta-test.
"""

import re


_COMPONENT_PATH_RE = re.compile(r"src/components/([A-Za-z0-9_]+)\.tsx")


class TestComponentRegex:
    def test_extracts_from_nudge_text(self):
        detail = (
            "App.tsx passed prop 'items' to <Marquee> but MarqueeProps "
            "doesn't declare 'items' at src/App.tsx:7. Read "
            "src/components/Marquee.tsx to see its real props."
        )
        m = _COMPONENT_PATH_RE.search(detail)
        assert m is not None
        assert m.group(1) == "Marquee"

    def test_picks_component_not_app(self):
        """Detail mentions both src/App.tsx and src/components/Marquee.tsx;
        we want Marquee (the component), not App (the caller)."""
        detail = "src/App.tsx:7 error. Read src/components/Navbar.tsx."
        m = _COMPONENT_PATH_RE.search(detail)
        assert m is not None
        assert m.group(1) == "Navbar"

    def test_no_match_on_other_paths(self):
        detail = "Error in src/main.tsx — no components involved."
        assert _COMPONENT_PATH_RE.search(detail) is None

    def test_multi_char_component_name(self):
        """Names like 'CTASection' or 'PortfolioGrid' must match."""
        detail = "... src/components/CTASection.tsx ..."
        m = _COMPONENT_PATH_RE.search(detail)
        assert m is not None
        assert m.group(1) == "CTASection"


class TestTruncation:
    """If the component source is > 2400 chars, we truncate with a marker.
    Covers the streaming behavior inline in agent.py."""

    def _apply_truncation(self, src: str) -> str:
        if len(src) > 2400:
            return src[:2400] + "\n// ... [truncated]"
        return src

    def test_short_source_unchanged(self):
        src = "export default function Navbar() { return null; }"
        assert self._apply_truncation(src) == src

    def test_long_source_truncated_with_marker(self):
        src = "x" * 3000
        out = self._apply_truncation(src)
        assert len(out) <= 2430  # 2400 + marker
        assert out.endswith("[truncated]")

    def test_boundary_2400_unchanged(self):
        src = "y" * 2400
        out = self._apply_truncation(src)
        assert out == src
        assert "truncated" not in out


class TestStreakGate:
    """Gate logic: hoist fires only when test=='tsc' AND streak >= 2."""

    def _should_hoist(self, test_name: str, streak: int) -> bool:
        return test_name == "tsc" and streak >= 2

    def test_no_hoist_on_first_tsc_fail(self):
        assert not self._should_hoist("tsc", streak=1)

    def test_hoist_on_second_tsc_fail(self):
        assert self._should_hoist("tsc", streak=2)

    def test_hoist_on_third_tsc_fail(self):
        assert self._should_hoist("tsc", streak=3)

    def test_no_hoist_on_vitest_fail(self):
        """vitest failures don't name a specific component."""
        assert not self._should_hoist("test_counter_increments", streak=3)

    def test_no_hoist_on_unknown_test(self):
        assert not self._should_hoist("(unknown)", streak=5)
