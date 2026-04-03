"""Tests for Chunk 13: Post-Processing + Shaders.

Verifies:
- PostProcessing component with effect toggles
- CustomShader with built-in fog + ocean shaders
- Both exported from index.ts
"""

from pathlib import Path

COMP_DIR = Path(__file__).parent.parent.parent / "scaffolds" / "threejs-game" / "src" / "components"


class TestPostProcessing:
    """PostProcessing component."""

    def test_file_exists(self):
        assert (COMP_DIR / "PostProcessing.tsx").exists()

    def test_has_effect_composer(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "EffectComposer" in content

    def test_has_bloom(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "Bloom" in content
        assert "intensity" in content
        assert "luminanceThreshold" in content

    def test_has_dof(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "DepthOfField" in content
        assert "focusDistance" in content
        assert "bokehScale" in content

    def test_has_vignette(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "Vignette" in content

    def test_has_props_interface(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "interface PostProcessingProps" in content

    def test_boolean_or_object_config(self):
        """Each effect can be true (defaults) or an object (custom values)."""
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "typeof bloom === \"object\"" in content

    def test_default_export(self):
        content = (COMP_DIR / "PostProcessing.tsx").read_text()
        assert "export default function PostProcessing" in content


class TestCustomShader:
    """CustomShader component + built-in shaders."""

    def test_file_exists(self):
        assert (COMP_DIR / "CustomShader.tsx").exists()

    def test_has_shader_material(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "shaderMaterial" in content

    def test_has_vertex_fragment(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "vertexShader" in content
        assert "fragmentShader" in content

    def test_has_uniforms_interface(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "uniforms" in content
        assert "uTime" in content

    def test_has_volumetric_fog(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "VOLUMETRIC_FOG_FRAG" in content
        assert "uDensity" in content
        assert "scatter" in content

    def test_has_ocean_shader(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "OCEAN_FRAG" in content
        assert "OCEAN_VERT" in content
        assert "uWaveHeight" in content
        assert "foam" in content.lower()

    def test_ocean_has_multi_octave_waves(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "wave1" in content
        assert "wave2" in content

    def test_ocean_has_fresnel(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "fresnel" in content

    def test_fog_has_light_scattering(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "scatter" in content
        assert "lightDir" in content

    def test_has_time_uniform(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "useFrame" in content
        assert "uTime" in content

    def test_has_side_options(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "front" in content
        assert "back" in content
        assert "double" in content

    def test_default_export(self):
        content = (COMP_DIR / "CustomShader.tsx").read_text()
        assert "export default function CustomShader" in content


class TestExports:
    """Components exported from index.ts."""

    def test_post_processing_exported(self):
        index = (COMP_DIR / "index.ts").read_text()
        assert "PostProcessing" in index

    def test_custom_shader_exported(self):
        index = (COMP_DIR / "index.ts").read_text()
        assert "CustomShader" in index
        assert "VOLUMETRIC_FOG_FRAG" in index
        assert "OCEAN_FRAG" in index
        assert "OCEAN_VERT" in index

    def test_total_threejs_components(self):
        """Should have 14 Three.js component files now."""
        tsx_files = list(COMP_DIR.glob("*.tsx"))
        assert len(tsx_files) >= 14
