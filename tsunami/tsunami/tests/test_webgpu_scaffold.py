"""Tests for WebGPU game scaffold + engine integration.

Verifies:
- Scaffold structure exists
- Engine is referenced via @engine path alias
- Classifier picks webgpu-game for engine-level keywords
- Engine source exists with all modules
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


class TestEngineAlias:
    """Engine linked via @engine path alias."""

    def test_vite_has_engine_alias(self):
        content = (SCAFFOLD_DIR / "vite.config.ts").read_text()
        assert "@engine" in content

    def test_tsconfig_has_engine_paths(self):
        content = (SCAFFOLD_DIR / "tsconfig.json").read_text()
        assert "@engine" in content


class TestMainTs:
    """Main entry point uses the engine API via @engine imports."""

    def test_imports_engine(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "@engine" in content

    def test_uses_game_class(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "Game" in content

    def test_uses_input(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "KeyboardInput" in content or "ActionMap" in content

    def test_uses_scene_manager(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "SceneManager" in content or "sceneManager" in content

    def test_has_game_loop(self):
        content = (SCAFFOLD_DIR / "src" / "main.ts").read_text()
        assert "requestAnimationFrame" in content or "game.start" in content


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
        assert _pick_scaffold("three.js scene", []) == "threejs-game"

    def test_generic_3d_picks_threejs(self):
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
