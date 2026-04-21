"""Replay regression for scaffold_first_predicate_layout_signal (sev 5
finding from kelp-round-10 mining audit).

Anchors the layout-signal branch of `is_scaffold_first_gamedev`. The
original implementation keyed on package.json name matching
`gamedev-*-scaffold`, but project_init_gamedev.py:266 rewrites the
name to the user's project slug on provisioning, so the predicate
never fired on real deliverables. This test pins the new dual-signal
behavior: filesystem layout (data/*.json + src/scenes/) OR legacy
package.json name — either alone is sufficient.

This test is a fix-for-the-fix. Rounds 1, 2, and 6 all keyed on this
predicate; without it working, all three fixes were dead code on
provisioned deliverables.

Fixture: tsunami/tests/replays/scaffold_first_predicate_layout_signal.jsonl
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tsunami.tools.filesystem import is_scaffold_first_gamedev


REPLAY_PATH = (
    Path(__file__).parent / "replays"
    / "scaffold_first_predicate_layout_signal.jsonl"
)


def _load_replay(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _materialize(root: Path, case: dict) -> Path:
    project = root / case["project"]
    project.mkdir(parents=True, exist_ok=True)
    (project / "package.json").write_text(json.dumps(case["package_json"]))
    for rel, content in case.get("files", {}).items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return project


class TestScaffoldFirstPredicateLayoutSignal:
    @pytest.fixture
    def cases(self):
        events = _load_replay(REPLAY_PATH)
        return [e for e in events if e["kind"] == "predicate_case"]

    def test_fixture_well_formed(self, cases):
        events = _load_replay(REPLAY_PATH)
        meta = next(e for e in events if e["kind"] == "meta")
        assert meta["slug"] == "scaffold_first_predicate_layout_signal"
        assert meta["severity"] == 5
        assert len(cases) >= 4, (
            "fixture must cover provisioned-deliverable positive, source-"
            "template positive, and at least two negative cases"
        )

    def test_every_case_matches_expect(self, cases, tmp_path: Path):
        for case in cases:
            project_dir = _materialize(tmp_path / "a", case)
            got = is_scaffold_first_gamedev(project_dir)
            assert got == case["expect_scaffold_first"], (
                f"case {case['desc']!r}: predicate returned {got}, "
                f"fixture expected {case['expect_scaffold_first']}"
            )
            # Reset tmp_path sandbox for next case so materialize doesn't
            # collide on identical project names across cases.
            import shutil
            shutil.rmtree(tmp_path / "a", ignore_errors=True)


class TestDualSignalInvariants:
    """Direct cases confirming each signal works in isolation AND the
    two signals compose (either alone is sufficient)."""

    def test_signal_1_alone_fires(self, tmp_path: Path):
        """Filesystem layout without the package-name marker — the
        canonical provisioned-deliverable case."""
        proj = tmp_path / "crystal-saga"
        (proj / "data").mkdir(parents=True)
        (proj / "data" / "party.json").write_text("[]")
        (proj / "src" / "scenes").mkdir(parents=True)
        (proj / "package.json").write_text(
            json.dumps({"name": "crystal-saga", "version": "0.0.1"})
        )
        assert is_scaffold_first_gamedev(proj) is True

    def test_signal_2_alone_fires(self, tmp_path: Path):
        """Package-name marker without the filesystem layout — the
        source-template case (scaffolds/gamedev/*/package.json)."""
        proj = tmp_path / "platformer"
        proj.mkdir()
        (proj / "package.json").write_text(
            json.dumps({"name": "gamedev-platformer-scaffold"})
        )
        assert is_scaffold_first_gamedev(proj) is True

    def test_neither_signal_returns_false(self, tmp_path: Path):
        """A plain web-app that happens to have a package.json."""
        proj = tmp_path / "web-app"
        proj.mkdir()
        (proj / "package.json").write_text(json.dumps({"name": "web-app"}))
        (proj / "src").mkdir()
        (proj / "src" / "App.tsx").write_text("// ...")
        assert is_scaffold_first_gamedev(proj) is False

    def test_signal_1_requires_both_data_and_scenes(self, tmp_path: Path):
        """data/*.json alone isn't unique (web apps have data too).
        src/scenes/ alone isn't unique (may be leftover scaffolding).
        Both together = the scaffold-first gamedev signature."""
        for missing in ("scenes", "data-json"):
            proj = tmp_path / f"partial_{missing}"
            proj.mkdir()
            (proj / "package.json").write_text(json.dumps({"name": "x"}))
            if missing != "scenes":
                (proj / "src" / "scenes").mkdir(parents=True)
            if missing != "data-json":
                (proj / "data").mkdir()
                (proj / "data" / "x.json").write_text("[]")
            assert is_scaffold_first_gamedev(proj) is False, (
                f"partial scaffold (missing {missing}) should not match"
            )

    def test_fails_closed_on_missing_project_dir(self, tmp_path: Path):
        assert is_scaffold_first_gamedev(tmp_path / "does-not-exist") is False

    def test_fails_closed_on_missing_package_json(self, tmp_path: Path):
        """Without a package.json AND without the filesystem signature,
        the predicate must return False — no guessing."""
        proj = tmp_path / "no-pkg"
        proj.mkdir()
        assert is_scaffold_first_gamedev(proj) is False

    def test_signal_1_beats_missing_package_json(self, tmp_path: Path):
        """If the layout signal is present, we don't need package.json
        at all — the structure speaks for itself. Some deliverables
        might be mid-provisioning and lack package.json briefly."""
        proj = tmp_path / "layout-only"
        (proj / "data").mkdir(parents=True)
        (proj / "data" / "x.json").write_text("[]")
        (proj / "src" / "scenes").mkdir(parents=True)
        # No package.json.
        assert is_scaffold_first_gamedev(proj) is True


class TestMiningFindingDocumented:
    """Capture the mining finding in a test so a future refactor that
    reverts to the name-only predicate fails loud with a pointer at
    the root cause."""

    def test_filesystem_signal_branch_present(self):
        """The layout-signal branch must remain in the helper. Without
        it, the predicate reverts to the dead-on-real-deliverables
        behavior kelp-round-10 discovered."""
        src = (Path(__file__).parent.parent / "tools" / "filesystem.py").read_text()
        assert 'data_dir = project_dir / "data"' in src
        assert 'scenes_dir = project_dir / "src" / "scenes"' in src
        assert "data_dir.is_dir()" in src

    def test_docstring_flags_the_rename(self):
        """The docstring must explain why Signal 2 alone is insufficient
        — project_init_gamedev rewrites the name. Without the context,
        a future author might 'simplify' back to the broken version."""
        src = (Path(__file__).parent.parent / "tools" / "filesystem.py").read_text()
        # The docstring's key observation:
        assert "project_init_gamedev.py:266" in src or "rewrites" in src, (
            "is_scaffold_first_gamedev docstring must flag the rename "
            "at project_init_gamedev so future authors don't 'simplify' "
            "back to the name-only check."
        )
