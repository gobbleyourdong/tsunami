"""Tests for Chunk 12: 3D Particles + GLTF.

Verifies:
- ParticleSystem component exists with presets and instanced rendering
- GLTFModel component exists with animation support
- Both exported from index.ts
"""

from pathlib import Path

COMP_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "threejs-game" / "src" / "components"


class TestParticleSystem:
    """ParticleSystem component."""

    def test_file_exists(self):
        assert (COMP_DIR / "ParticleSystem.tsx").exists()

    def test_has_instanced_mesh(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "instancedMesh" in content or "InstancedMesh" in content

    def test_has_presets(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        for preset in ["fire", "smoke", "rain", "snow", "sparks", "confetti"]:
            assert preset in content, f"Missing preset: {preset}"

    def test_has_particle_config(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "interface ParticleConfig" in content

    def test_has_lifetime(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "lifetime" in content

    def test_has_gravity(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "gravity" in content

    def test_has_fade_out(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "fadeOut" in content

    def test_has_color_support(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "color" in content
        assert "setColorAt" in content

    def test_uses_use_frame(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "useFrame" in content

    def test_has_emitting_control(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "emitting" in content

    def test_default_export(self):
        content = (COMP_DIR / "ParticleSystem.tsx").read_text()
        assert "export default function ParticleSystem" in content


class TestGLTFModel:
    """GLTFModel component."""

    def test_file_exists(self):
        assert (COMP_DIR / "GLTFModel.tsx").exists()

    def test_has_use_gltf(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "useGLTF" in content

    def test_has_animation_mixer(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "useAnimations" in content

    def test_has_animation_control(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "animation" in content
        assert "animationSpeed" in content

    def test_has_play_pause_loop(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "loop" in content
        assert "autoPlay" in content

    def test_has_animation_blending(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "fadeIn" in content or "fadeOut" in content

    def test_has_shadow_support(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "castShadow" in content
        assert "receiveShadow" in content

    def test_has_preload(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "preload" in content.lower()

    def test_has_on_load_callback(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "onLoad" in content

    def test_default_export(self):
        content = (COMP_DIR / "GLTFModel.tsx").read_text()
        assert "export default function GLTFModel" in content


class TestExports:
    """Components exported from index.ts."""

    def test_particle_system_exported(self):
        index = (COMP_DIR / "index.ts").read_text()
        assert "ParticleSystem" in index
        assert "PARTICLE_PRESETS" in index

    def test_gltf_model_exported(self):
        index = (COMP_DIR / "index.ts").read_text()
        assert "GLTFModel" in index
        assert "preloadModel" in index

    def test_total_threejs_components(self):
        """Should have 12+ Three.js component files now (11 original + 2 new)."""
        tsx_files = list(COMP_DIR.glob("*.tsx"))
        assert len(tsx_files) >= 12
