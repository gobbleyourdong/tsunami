"""gamedev scaffold delivery probe (new flow).

Validates the data-driven gamedev scaffold where the deliverable is the
customized scaffold project itself, not a single ``public/game_definition.json``.
The wave edits ``data/*.json`` (entities, items, mechanics, rooms/levels,
etc.), touches ``src/scenes/*.ts`` to wire a new mechanic, and lets
``vite build`` emit ``dist/``.

Sibling of :mod:`tsunami.core.gamedev_probe` (which handles the legacy
``public/game_definition.json`` shape). :func:`gamedev_probe_dispatch`
routes between the two based on what's on disk.

Checks:
  1. ``package.json`` present and declares the engine dep
  2. ``data/*.json`` glob non-empty and every file parses
  3. At least one ``data/*.json`` differs from its scaffold seed (proof
     the wave actually customized the project, not just ran the
     scaffold and shipped)
  4. ``src/scenes/*.ts`` references at least one mechanic from the
     engine catalog (or ``@engine/mechanics`` import at the top of the
     file)
  5. Advisory: ``dist/index.html`` exists when ``vite build`` ran
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ._probe_common import result, skip

log = logging.getLogger("tsunami.core.gamedev_scaffold_probe")


# Repo seed dirs live at scaffolds/gamedev/<kind>/. Resolved from this
# module's file path so the probe works regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_DIR_ROOT = _REPO_ROOT / "scaffolds" / "gamedev"

# Regex to detect mechanic references in scene TypeScript. Both the
# import form and direct string-literal form count.
_MECH_IMPORT_RE = re.compile(
    r"""from\s+['"]@?engine/(?:design/)?mechanics['"]""",
)
_MECH_STRING_RE = re.compile(
    r"""['"]type['"]\s*:\s*['"]([A-Z][A-Za-z0-9_]+)['"]""",
)


def _detect_scaffold_kind(project_dir: Path) -> str | None:
    """Extract the scaffold kind (action_adventure / custom / fighting /
    cross) from the project's package.json name. Returns None if the
    name doesn't match the ``gamedev-<kind>-scaffold`` convention."""
    pkg_path = project_dir / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    name = pkg.get("name", "")
    # Expected pattern: gamedev-<kind>-scaffold (kind may contain underscores)
    m = re.match(r"gamedev-([a-z0-9_-]+)-scaffold$", name)
    if m:
        kind = m.group(1).replace("-", "_")
        if (_SEED_DIR_ROOT / kind).is_dir():
            return kind
    return None


def _data_files_differ_from_seed(project_dir: Path, kind: str) -> tuple[int, list[str]]:
    """Count how many ``data/*.json`` files in the project differ from
    their seed counterparts. Returns ``(count, changed_filenames)``.
    Missing seed → count as changed (wave added a new data file)."""
    project_data = project_dir / "data"
    seed_data = _SEED_DIR_ROOT / kind / "data"
    if not project_data.is_dir():
        return 0, []
    changed: list[str] = []
    for pfile in sorted(project_data.glob("*.json")):
        sfile = seed_data / pfile.name
        if not sfile.is_file():
            changed.append(pfile.name)
            continue
        try:
            if pfile.read_bytes() != sfile.read_bytes():
                changed.append(pfile.name)
        except OSError:
            # Unreadable → assume different (safer for the customization
            # signal — we'd rather over-count than mark a wave as
            # shipping-seed when it isn't).
            changed.append(pfile.name)
    return len(changed), changed


def _scenes_reference_mechanics(project_dir: Path) -> tuple[bool, list[str]]:
    """Scan ``src/scenes/*.ts`` for engine/mechanics imports or
    MechanicType string refs. Returns ``(found_any, examples)``."""
    scenes_dir = project_dir / "src" / "scenes"
    if not scenes_dir.is_dir():
        return False, []
    examples: list[str] = []
    found = False
    for ts in scenes_dir.glob("*.ts"):
        try:
            text = ts.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _MECH_IMPORT_RE.search(text):
            found = True
            examples.append(f"{ts.name}: imports @engine/mechanics")
            continue
        for m in _MECH_STRING_RE.finditer(text):
            found = True
            examples.append(f"{ts.name}: references type={m.group(1)!r}")
            break
    return found, examples[:5]


async def gamedev_scaffold_probe(project_dir: Path, task_text: str = "") -> dict:
    """Inspect a data-driven gamedev scaffold deliverable.

    Async signature matches the other probes in ``core/dispatch.py``
    for uniformity. Returns the canonical ``{passed, issues, raw}``
    shape from ``_probe_common.result``.
    """
    del task_text  # reserved for future rubric routing
    pdir = Path(project_dir)

    pkg_path = pdir / "package.json"
    if not pkg_path.is_file():
        return result(
            passed=False,
            issues=(
                "NO package.json — gamedev scaffold requires a Vite "
                "project at the root. Wave either didn't run the "
                "scaffold init or delivered to the wrong directory."
            ),
            raw=f"missing: {pkg_path}",
        )

    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return result(
            passed=False,
            issues=f"package.json is not valid JSON: {e}",
            raw=f"parse error at {pkg_path}",
        )

    deps = {**(pkg.get("dependencies") or {}),
            **(pkg.get("devDependencies") or {})}
    if "engine" not in deps:
        return result(
            passed=False,
            issues=(
                "package.json doesn't reference the engine — gamedev "
                "scaffolds need a local engine dep "
                "(\"engine\": \"file:../../engine\" in the seed)."
            ),
            raw=f"deps={sorted(deps)[:8]}",
        )

    data_dir = pdir / "data"
    data_files = sorted(data_dir.glob("*.json")) if data_dir.is_dir() else []
    if not data_files:
        return result(
            passed=False,
            issues=(
                "no data/*.json files — the scaffold's entity / item / "
                "mechanic / room payload is missing. The wave deleted "
                "them or delivered an unscaffolded project."
            ),
            raw=f"data_dir={data_dir}",
        )

    # Each data file must parse.
    parse_failures: list[str] = []
    for f in data_files:
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            parse_failures.append(f"{f.name}: {str(e)[:60]}")

    issues: list[str] = []
    if parse_failures:
        preview = "; ".join(parse_failures[:3])
        issues.append(f"data/*.json parse errors: {preview}")

    # Customization check — did the wave edit the seed at all?
    kind = _detect_scaffold_kind(pdir)
    customization_count = 0
    changed_files: list[str] = []
    if kind is not None:
        customization_count, changed_files = _data_files_differ_from_seed(pdir, kind)
        if customization_count == 0:
            issues.append(
                f"data/*.json is identical to the {kind!r} seed — wave "
                "launched the scaffold but shipped it verbatim. No real "
                "customization happened."
            )

    # Scene wiring — at least one scene file should touch a mechanic.
    scenes_ok, scene_examples = _scenes_reference_mechanics(pdir)
    if not scenes_ok:
        issues.append(
            "no src/scenes/*.ts references any engine mechanic — the "
            "scaffold's scenes weren't wired to composed behavior. "
            "Check for @engine/mechanics imports or \"type\": \"<Name>\" refs."
        )

    dist_html = pdir / "dist" / "index.html"
    build_ran = dist_html.is_file()

    raw_summary = (
        f"gamedev-scaffold: kind={kind or '?'}, "
        f"data_files={len(data_files)}, "
        f"customized={customization_count}/{len(data_files)}, "
        f"scenes_wired={scenes_ok}, "
        f"build={'ran' if build_ran else 'no-dist'}"
    )

    if issues:
        return result(passed=False, issues="; ".join(issues), raw=raw_summary)
    return result(passed=True, raw=raw_summary)


async def gamedev_probe_dispatch(project_dir: Path, task_text: str = "") -> dict:
    """Route between the new scaffold probe and the legacy
    game_definition probe based on what's on disk.

    Rule: if the project has both a ``package.json`` and a ``data/``
    dir with ``*.json`` files, it's a scaffold-flow delivery and goes
    to :func:`gamedev_scaffold_probe`. Otherwise fall back to the
    legacy :func:`gamedev_probe` which reads
    ``public/game_definition.json``.
    """
    pdir = Path(project_dir)
    if not pdir.is_dir():
        return skip(f"no project dir: {pdir}")

    has_pkg = (pdir / "package.json").is_file()
    data_dir = pdir / "data"
    has_data = data_dir.is_dir() and any(data_dir.glob("*.json"))

    if has_pkg and has_data:
        return await gamedev_scaffold_probe(pdir, task_text)

    # Legacy path — delegate to the original probe.
    from .gamedev_probe import gamedev_probe
    return await gamedev_probe(pdir, task_text)


__all__ = [
    "gamedev_scaffold_probe",
    "gamedev_probe_dispatch",
]
