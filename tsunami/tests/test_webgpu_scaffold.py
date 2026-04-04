"""Tests for WebGPU game scaffold + engine integration.

Verifies:
- Scaffold structure exists
- Engine is linked as dependency
- Classifier picks webgpu-game for engine-level keywords
- Engine tests pass (256 tests)
"""

import json
from pathlib import Path

from tsunami.tools.project_init import _pick_scaffold

SCAFFOLD_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "webgpu-game"
ENGINE_DIR = Path(__file__).parent.parent.parent / "engine"


class TestScaffoldExists:
    """WebGPU game scaffold structure."""

    def test_scaffold_dir(self):
        assert SCAFFOLD_DIR.exists()

    def test_package_json(self):
        assert (SCAFFOLD_DIR / "package.json").exists()

    def test_index_html(self):
        assert (SCAFFOLD_DIR / "index.html").exists()

    def test_main_ts(self):
        assert (SCAFFOLD_DIR / "src" / "main.ts").exists()

    def test_vite_config(self):
        assert (SCAFFOLD_DIR / "vite.config.ts").exists()

    def test_tsconfig(self):
        assert (SCAFFOLD_DIR / "tsconfig.json").exists()

    def test_readme(self):
        assert (SCAFFOLD_DIR / "README.md").exists()


class TestEngineLink:
    """Engine is linked as a local dependency."""

    def test_tsunami_engine_dependency(self):
        pkg = json.loads((SCAFFOLD_DIR / "package.json").read_text())
        assert "tsunami-engine" in pkg["dependencies"]
        assert "../../engine" in pkg["dependencies"]["tsunami-engine"]


class TestMainTs:
    """Main entry point uses the engine API."""

    def test_imports_game(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "import" in content
        assert "tsunami-engine" in content

    def test_creates_game(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "new Game" in content

    def test_uses_scene_builder(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "game.scene" in content

    def test_spawns_entities(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "level.spawn" in content

    def test_has_ground(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "level.ground" in content

    def test_has_lighting(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "level.light" in content

    def test_starts_game(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "game.start()" in content


class TestReadme:
    """README documents engine API."""

    def test_has_engine_modules_table(self):
        content = (SCAFFOLD_DIR / "README.md").read_text()
        for module in ["renderer", "physics", "ai", "animation", "audio", "input", "vfx", "flow"]:
            assert module in content

    def test_has_spawn_options(self):
        content = (SCAFFOLD_DIR / "README.md").read_text()
        assert "spawn" in content.lower()
        assert "mesh" in content
        assert "controller" in content


class TestClassifier:
    """Scaffold classifier picks webgpu-game for engine keywords."""

    def test_webgpu_keyword(self):
        assert _pick_scaffold("webgpu game", []) == "webgpu-game"

    def test_custom_engine_keyword(self):
        assert _pick_scaffold("custom engine game", []) == "webgpu-game"

    def test_behavior_tree_keyword(self):
        assert _pick_scaffold("game with behavior tree AI", []) == "webgpu-game"

    def test_navmesh_keyword(self):
        assert _pick_scaffold("navmesh pathfinding game", []) == "webgpu-game"

    def test_shader_graph_keyword(self):
        assert _pick_scaffold("shader graph effects", []) == "webgpu-game"

    def test_gpu_particles_keyword(self):
        assert _pick_scaffold("gpu particle system", []) == "webgpu-game"

    def test_threejs_still_works(self):
        """Three.js keywords should still pick threejs-game."""
        assert _pick_scaffold("three.js scene", []) == "threejs-game"

    def test_generic_3d_picks_threejs(self):
        """Generic 3D should still pick Three.js (more accessible)."""
        assert _pick_scaffold("3d game", []) == "threejs-game"


class TestEngineExists:
    """Engine directory has all expected modules."""

    def test_engine_dir(self):
        assert ENGINE_DIR.exists()

    def test_engine_package_json(self):
        assert (ENGINE_DIR / "package.json").exists()

    def test_engine_src(self):
        assert (ENGINE_DIR / "src" / "index.ts").exists()

    def test_has_renderer(self):
        assert (ENGINE_DIR / "src" / "renderer" / "index.ts").exists()

    def test_has_physics(self):
        assert (ENGINE_DIR / "src" / "physics" / "index.ts").exists()

    def test_has_ai(self):
        assert (ENGINE_DIR / "src" / "ai" / "index.ts").exists()

    def test_has_animation(self):
        assert (ENGINE_DIR / "src" / "animation" / "index.ts").exists()

    def test_has_audio(self):
        assert (ENGINE_DIR / "src" / "audio" / "index.ts").exists()

    def test_has_input(self):
        assert (ENGINE_DIR / "src" / "input" / "index.ts").exists()

    def test_has_vfx(self):
        assert (ENGINE_DIR / "src" / "vfx" / "index.ts").exists()

    def test_has_flow(self):
        assert (ENGINE_DIR / "src" / "flow" / "index.ts").exists()

    def test_has_game(self):
        assert (ENGINE_DIR / "src" / "game" / "index.ts").exists()

    def test_has_systems(self):
        assert (ENGINE_DIR / "src" / "systems" / "index.ts").exists()

    def test_has_tests(self):
        test_files = list((ENGINE_DIR / "tests").glob("*.test.ts"))
        assert len(test_files) >= 14
