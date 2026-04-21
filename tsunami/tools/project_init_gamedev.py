"""project_init_gamedev — provision from the gamedev genre-scaffold library.

Parallels tools/project_init.py, but targets scaffolds/gamedev/<genre>/
instead of scaffolds/<web_scaffold>/. Genre scaffolds ship playable
(scenes + data + prewired mechanics from @engine/mechanics); the drone's
job is to edit data/*.json and src/scenes/*.ts — NOT to emit a design
from scratch.

Flow:
  1. Resolve `genre` → scaffold directory under scaffolds/gamedev/
  2. Copy to workspace/deliverables/<name>/
  3. Rewrite tsconfig @engine paths + package.json engine dep to
     work from the deliverables depth (one level up, not two or three)
  4. Symlink workspace/deliverables/engine → scaffolds/engine/ so
     the copied paths resolve.
  5. npm install; serve_project; return file-list + customization hints.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tools.project_init_gamedev")

# Scaffold root. `scaffolds/gamedev/` holds the genre library.
SCAFFOLDS_DIR = Path(__file__).parent.parent.parent / "scaffolds"
GAMEDEV_DIR = SCAFFOLDS_DIR / "gamedev"
ENGINE_DIR = SCAFFOLDS_DIR / "engine"


# Genre alias → on-disk scaffold path (relative to scaffolds/gamedev/).
# Keeps genre naming flexible while the disk layout can be renamed
# without breaking the drone-facing API.
_GENRE_MAP: dict[str, str] = {
    # Canonical
    "custom":            "custom",
    "action_adventure":  "action_adventure",
    "fighting":          "fighting",
    "jrpg":              "jrpg",
    "platformer":        "platformer",
    "fps":               "fps",
    "stealth":           "stealth",
    "racing":            "racing",
    "magic_hoops":       "cross/magic_hoops",
    "ninja_garden":      "cross/ninja_garden",
    "rhythm_fighter":    "cross/rhythm_fighter",
    "action_rpg_atb":    "cross/action_rpg_atb",
    "metroid_runs":      "cross/metroid_runs",
    "bullet_hell_rpg":   "cross/bullet_hell_rpg",
    "puzzle_platformer_roguelite": "cross/puzzle_platformer_roguelite",
    # Common spellings + hyphen variants
    "action-adventure":  "action_adventure",
    "adventure":         "action_adventure",
    "fighter":           "fighting",
    "brawler":           "fighting",
    "rpg":               "jrpg",
    "jrpg-classic":      "jrpg",
    "final-fantasy":     "jrpg",
    "dragon-quest":      "jrpg",
    "platform":          "platformer",
    "mario":             "platformer",
    "super-mario":       "platformer",
    "megaman":           "platformer",
    "celeste":           "platformer",
    "shooter":           "fps",
    "first-person":      "fps",
    "first-person-shooter": "fps",
    "doom":              "fps",
    "quake":             "fps",
    "half-life":         "fps",
    "sneak":             "stealth",
    "infiltration":      "stealth",
    "metal-gear":        "stealth",
    "thief":             "stealth",
    "splinter-cell":     "stealth",
    "race":              "racing",
    "kart":              "racing",
    "kart_racer":        "racing",
    "mario-kart":        "racing",
    "outrun":            "racing",
    "out-run":           "racing",
    "gran-turismo":      "racing",
    "ninja-garden":      "cross/ninja_garden",
    "terraria":          "cross/ninja_garden",
    "ninja-gaiden":      "cross/ninja_garden",
    "shinobi":           "cross/ninja_garden",
    "sandbox-action":    "cross/ninja_garden",
    "rhythm-fighter":    "cross/rhythm_fighter",
    "rhythm-fighting":   "cross/rhythm_fighter",
    "beat-fighter":      "cross/rhythm_fighter",
    "parappa-fighter":   "cross/rhythm_fighter",
    "action-rpg":        "cross/action_rpg_atb",
    "action-rpg-atb":    "cross/action_rpg_atb",
    "zelda-ff":          "cross/action_rpg_atb",
    "metroid-runs":      "cross/metroid_runs",
    "metroidvania-roguelike": "cross/metroid_runs",
    "spelunky-metroid":  "cross/metroid_runs",
    "dead-cells":        "cross/metroid_runs",
    "bullet-hell-rpg":   "cross/bullet_hell_rpg",
    "bullet-hell":       "cross/bullet_hell_rpg",
    "shmup-rpg":         "cross/bullet_hell_rpg",
    "touhou-like":       "cross/bullet_hell_rpg",
    "cave-shmup":        "cross/bullet_hell_rpg",
    "puzzle-platformer-roguelite": "cross/puzzle_platformer_roguelite",
    "puzzle-platformer": "cross/puzzle_platformer_roguelite",
    "catherine-like":    "cross/puzzle_platformer_roguelite",
    "celeste-roguelite": "cross/puzzle_platformer_roguelite",
    "into-the-platformer": "cross/puzzle_platformer_roguelite",
    "cross":             "cross/magic_hoops",
    "cross-genre":       "cross/magic_hoops",
    "canary":            "cross/magic_hoops",
    # Universal fallback
    "generic":           "custom",
    "":                  "custom",
}


def _resolve_genre(genre: str) -> str:
    """Return the on-disk path fragment (e.g. 'fighting' or
    'cross/magic_hoops') for a genre alias, or empty string if unknown."""
    return _GENRE_MAP.get(genre.strip().lower().replace(" ", "_"), "")


def _rewrite_engine_paths(project_dir: Path) -> None:
    """After copy, rewrite tsconfig paths + package.json engine dep so
    `@engine/*` and the `engine` npm dep resolve to the sibling symlink
    (deliverables/engine → scaffolds/engine/), regardless of how deep
    the source scaffold was nested under scaffolds/gamedev/.

    - `../../engine` (fighting/action_adventure/custom depth) → `../engine`
    - `../../../engine` (cross/magic_hoops depth) → `../engine`
    - `../../../../engine` (defensive: even deeper future nesting) → `../engine`
    """
    for rel in ("tsconfig.json", "package.json", "vite.config.ts"):
        f = project_dir / rel
        if not f.exists():
            continue
        text = f.read_text()
        # Collapse every 2/3/4-level relative engine reference to one level up.
        # Order matters: longer patterns first so a 4-level match isn't partially
        # rewritten into a still-wrong 2-level path.
        for pattern in ("../../../../engine", "../../../engine", "../../engine"):
            text = text.replace(pattern, "../engine")
        f.write_text(text)


def _list_customization_files(project_dir: Path) -> list[str]:
    """Return the data/*.json + src/scenes/*.ts files a drone should
    customize first. Skips README, tests, build config — those aren't
    the user-meaningful edit surface."""
    out: list[str] = []
    data_dir = project_dir / "data"
    if data_dir.is_dir():
        out.extend(sorted(f"data/{f.name}" for f in data_dir.glob("*.json")))
    scenes_dir = project_dir / "src" / "scenes"
    if scenes_dir.is_dir():
        out.extend(sorted(f"src/scenes/{f.name}" for f in scenes_dir.glob("*.ts")))
    main = project_dir / "src" / "main.ts"
    if main.exists():
        out.append("src/main.ts")
    return out


class ProjectInitGamedev(BaseTool):
    name = "project_init_gamedev"
    description = (
        "Create a game project from a pre-built genre scaffold. "
        "The scaffold ships PLAYABLE (scenes + data + mechanics prewired "
        "from @engine/mechanics) — your job is to edit data/*.json "
        "(characters/rules/arena) and optionally src/scenes/*.ts. "
        "Do NOT emit a game_definition.json from scratch. "
        "Available genres: 'custom' (universal base), 'action_adventure' "
        "(Zelda/Metroid lineage), 'fighting' (SF2/MK2/Tekken lineage), "
        "'jrpg' (FF4/DQ3/Chrono Trigger lineage, ATB combat), "
        "'platformer' (SMB/Mega Man 2/Celeste lineage), "
        "'fps' (Doom/Quake/Half-Life lineage, hitscan+projectile weapons), "
        "'stealth' (MGS/Thief/Splinter Cell lineage, VisionCone detection), "
        "'racing' (Out Run/Mario Kart/Gran Turismo lineage, checkpoint-based scoring), "
        "'magic_hoops' (cross-genre canary #1: sports+fighting+RPG), "
        "'ninja_garden' (cross-genre canary #2: sandbox+action+stealth, Terraria × Ninja Gaiden × Shinobi), "
        "'rhythm_fighter' (cross-genre canary #3: fighting+rhythm, SF2 × PaRappa × Gitaroo Man). "
        "Installs deps and starts the dev server."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name (lowercase, no spaces). Created in workspace/deliverables/",
                },
                "genre": {
                    "type": "string",
                    "description": (
                        "Genre scaffold to copy. One of: custom, "
                        "action_adventure, fighting, jrpg, platformer, fps, stealth, racing, magic_hoops, ninja_garden, rhythm_fighter."
                    ),
                },
            },
            "required": ["name", "genre"],
        }

    async def execute(self, name: str, genre: str = "custom", **kw) -> ToolResult:
        ws = Path(self.config.workspace_dir)
        project_dir = ws / "deliverables" / name

        if (project_dir / "package.json").exists():
            import time
            suffix = str(int(time.time()))[-4:]
            name = f"{name}-{suffix}"
            project_dir = ws / "deliverables" / name
            log.info(f"Gamedev project name collision — using '{name}'")

        from .filesystem import register_session_project
        register_session_project(name)

        rel = _resolve_genre(genre)
        if not rel:
            avail = sorted({v for v in _GENRE_MAP.values()})
            return ToolResult(
                f"Unknown genre {genre!r}. Available: "
                f"custom, action_adventure, fighting, jrpg, platformer, fps, stealth, racing, magic_hoops, ninja_garden, rhythm_fighter. "
                f"(Scaffolds on disk: {avail})",
                is_error=True,
            )

        scaffold_src = GAMEDEV_DIR / rel
        if not scaffold_src.is_dir():
            return ToolResult(
                f"Scaffold dir missing: {scaffold_src}. "
                f"Check scaffolds/gamedev/ layout.",
                is_error=True,
            )

        try:
            shutil.copytree(
                scaffold_src, project_dir,
                ignore=shutil.ignore_patterns(
                    "node_modules", "dist", ".vite", "package-lock.json",
                ),
            )
            log.info(f"Copied gamedev scaffold '{genre}' (→{rel}) → {project_dir}")

            _rewrite_engine_paths(project_dir)

            # Engine symlink as sibling of deliverable — tsconfig's
            # `../engine/src/*` path resolves here.
            engine_link = project_dir.parent / "engine"
            if ENGINE_DIR.is_dir() and not engine_link.exists():
                try:
                    engine_link.symlink_to(ENGINE_DIR.resolve())
                    log.info(f"Symlinked {engine_link} → {ENGINE_DIR.resolve()}")
                except OSError as exc:
                    log.warning(f"engine symlink failed: {exc}")

            pkg_path = project_dir / "package.json"
            if pkg_path.exists():
                pkg = json.loads(pkg_path.read_text())
                pkg["name"] = name
                pkg_path.write_text(json.dumps(pkg, indent=2))

            # npm install (best-effort — if it fails we still return the
            # scaffold paths so the drone can act on it).
            install_err = ""
            try:
                result = subprocess.run(
                    ["npm", "install"],
                    cwd=str(project_dir),
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode != 0:
                    install_err = result.stderr[:300]
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                install_err = str(exc)[:300]

            try:
                from ..serve import serve_project
                url = serve_project(str(project_dir))
            except Exception:
                url = ""

            customize = _list_customization_files(project_dir)
            customize_block = ""
            if customize:
                customize_block = (
                    "\n\nPrimary edit surface (edit these, not the scaffolding):\n  "
                    + "\n  ".join(customize)
                )

            err_suffix = f"\n(npm install issues: {install_err})" if install_err else ""

            return ToolResult(
                f"Gamedev project '{name}' ready (genre: {genre} → {rel}) at {project_dir}\n"
                f"Dev server: {url or 'run npx vite'}\n\n"
                f"Scaffold ships playable. Customize data/*.json for content "
                f"(characters, rules, arena, items/spells) and src/scenes/*.ts "
                f"for scene composition. All mechanics come from '@engine/mechanics' "
                f"— do NOT write new mechanic types, reuse the registered catalog."
                f"{customize_block}"
                f"{err_suffix}"
            )

        except Exception as e:
            return ToolResult(f"project_init_gamedev failed: {e}", is_error=True)
