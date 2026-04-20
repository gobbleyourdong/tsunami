"""Tests for tsc-error parsing in tsunami/auto_build.py.

Regression target: audit_run v4 on 2026-04-20 fell into a read-spiral
after auto-build failed 3x. Root cause: drone's App.tsx passed custom
props like `menuOpen` to <Navbar> when the scaffolded Navbar didn't
declare them. The generic 'BUILD FAILED — test (unknown)' message didn't
point the drone at the specific component, so it started reading every
component trying to guess. The new tsc parser extracts the prop name +
component type name and tells the drone exactly which file to read.
"""

from tsunami.auto_build import (
    _parse_tsc_failure,
    _TSC_LINE_RE,
    _TSC_MISSING_PROP_RE,
)


SAMPLE_AUDIT_RUN_V4 = """
> build
> tsc --noEmit && vite build

src/App.tsx(49,9): error TS2322: Type '{ menuOpen: boolean; setMenuOpen: Dispatch<SetStateAction<boolean>>; scrolled: boolean; }' is not assignable to type 'IntrinsicAttributes & NavbarProps'.
  Property 'menuOpen' does not exist on type 'IntrinsicAttributes & NavbarProps'.
src/App.tsx(53,8): error TS2741: Property 'title' is missing in type '{}' but required in type 'HeroProps'.
"""

SAMPLE_GENERIC_TS = """
> build
> tsc --noEmit

src/pages/Home.tsx(12,5): error TS2304: Cannot find name 'React'.
"""


class TestMissingPropParse:
    def test_extracts_prop_and_component(self):
        f = _parse_tsc_failure(SAMPLE_AUDIT_RUN_V4)
        assert f is not None
        assert f["test"] == "tsc"
        assert "menuOpen" in f["detail"]
        assert "Navbar" in f["detail"]

    def test_tells_drone_to_read_specific_component(self):
        f = _parse_tsc_failure(SAMPLE_AUDIT_RUN_V4)
        assert f is not None
        assert "src/components/Navbar.tsx" in f["detail"]

    def test_warns_against_read_spiral(self):
        """Key copy: 'Do NOT read every component'."""
        f = _parse_tsc_failure(SAMPLE_AUDIT_RUN_V4)
        assert f is not None
        assert "Do NOT read every component" in f["detail"]

    def test_file_location_included(self):
        f = _parse_tsc_failure(SAMPLE_AUDIT_RUN_V4)
        assert f is not None
        assert "App.tsx:49" in f["detail"] or "App.tsx:49," in f["detail"]


class TestGenericTscParse:
    def test_falls_back_on_non_prop_errors(self):
        """Non-prop errors (undefined name, syntax, etc.) get the generic
        line+code+message format — still more useful than '(unknown)'."""
        f = _parse_tsc_failure(SAMPLE_GENERIC_TS)
        assert f is not None
        assert f["test"] == "tsc"
        assert "TS2304" in f["detail"]
        assert "Home.tsx" in f["detail"]

    def test_clean_output_returns_none(self):
        assert _parse_tsc_failure("") is None
        assert _parse_tsc_failure("vite build\nbuilt in 500ms\n✓") is None


class TestRegexComponents:
    def test_line_regex_captures_position(self):
        m = _TSC_LINE_RE.search("src/App.tsx(49,9): error TS2322: msg")
        assert m is not None
        assert m.group("line") == "49"
        assert m.group("col") == "9"
        assert m.group("code") == "TS2322"

    def test_missing_prop_regex_captures_both(self):
        txt = "Property 'foo' does not exist on type 'IntrinsicAttributes & BarProps'."
        m = _TSC_MISSING_PROP_RE.search(txt)
        assert m is not None
        assert m.group("prop") == "foo"
        assert m.group("component") == "Bar"
