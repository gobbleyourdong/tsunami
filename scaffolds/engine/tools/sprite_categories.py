"""CategoryConfig registry — 8 v1.1 categories.

Each category bundles the style_prefix + negative_prompt + generation
settings + post_process chain + scorer + metadata_schema needed to
synthesize one class of sprite. style_prefix and negative_prompt come
verbatim from sprites/recipes/<category>.md — don't reword.

Three ports from the legacy STYLE_PREFIXES:
  character, item (renamed from 'object'), texture

Five new from recipes/<category>.md:
  tileset, background, ui_element, effect, portrait

v1.2-deferred ops (autotile_variant_gen, parallax_depth_tag,
nine_slice_detect, unify_palette) are intentionally absent from the
chains below — generate_asset would reject them and recipes carried
them as "architecture thread to add." They re-appear in v1.2 once
impls land.

Backend policy (post-Phase 6.2): all 8 categories primary on ERNIE-
Image-Turbo (:8092) with backend_fallback='z_image' (:8090 Z-Image-
Turbo). ERNIE is the shipping default per operator directive —
8 steps / CFG 1.0 / use_pe=False — with z_image as the always-
available fallback when the ERNIE server is mid-swap or offline.
Recipe settings (gen_size / variations / palette) stay as the
authors chose them; ERNIE accepts arbitrary aspect ratios so we
don't force 1024² except where the recipe already specified it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from sprite_backends import BackendName


# ─── Metadata schema ─────────────────────────────────────────────────

MetadataType = Literal[
    "string", "int", "float", "bool",
    "list[int]", "list[float]", "list[string]",
    "enum", "object",
]


@dataclass
class MetadataFieldSpec:
    type: MetadataType
    required: bool = False
    enum_values: Optional[list[str]] = None
    item_type: Optional[str] = None
    description: str = ""


# ─── CategoryConfig ──────────────────────────────────────────────────

@dataclass
class CategoryConfig:
    name: str
    description: str

    # Prompting — copied verbatim from recipes/<category>.md.
    style_prefix: str
    style_suffix: str = ""
    negative_prompt: str = ""

    # Generation.
    gen_size: tuple[int, int] = (512, 512)
    variations: int = 4

    # Output.
    target_size: tuple[int, int] = (64, 64)
    palette_colors: int = 16

    # Pipeline.
    post_process: list[str] = field(default_factory=list)
    scorer: str = "default_scorer"

    # Backend.
    backend: BackendName = "ernie"
    backend_fallback: Optional[BackendName] = "z_image"

    # Quality (warn-only — below threshold stamps score_warning=True).
    min_acceptable_score: Optional[float] = None

    # Metadata validation.
    metadata_schema: dict[str, MetadataFieldSpec] = field(default_factory=dict)


# ─── Legacy negatives — shared across the 3 ported categories ────────

_LEGACY_NEG = (
    "blurry, soft, anti-aliased, gradient background, realistic, photo, "
    "3d render, text, watermark, signature, border, frame, cropped, "
    "low quality, noise, artifacts, multiple characters, group, crowd, "
    "multiple objects, collection, set, grid, sheet, collage"
)


# ─── Registry ────────────────────────────────────────────────────────

CATEGORIES: dict[str, CategoryConfig] = {

    # ─ character (ported) ──────────────────────────────────────────
    "character": CategoryConfig(
        name="character",
        description="Full-body pixel-art character sprite, one figure, "
                    "magenta background, side or front view.",
        style_prefix=(
            "single pixel art game character sprite, one character only, "
            "clean silhouette, centered, full body head to feet, "
            "solid magenta background, bright magenta #FF00FF background, "
            "no ground, no shadow, no other characters, no props on ground, "
            "sharp pixels, 16-bit style, "
        ),
        negative_prompt=_LEGACY_NEG,
        gen_size=(512, 512),
        variations=4,
        target_size=(64, 64),
        palette_colors=16,
        post_process=[
            "pixel_extract",
            "isolate_largest",
            "trim_transparent",
            "normalize_height",
            "quantize_palette",
            "pixel_snap",
        ],
        scorer="character_scorer",
        min_acceptable_score=0.5,
        metadata_schema={
            "class": MetadataFieldSpec(type="string",
                description="e.g. 'knight', 'mage', 'slime'"),
            "facing": MetadataFieldSpec(type="enum",
                enum_values=["front", "side", "three_quarter"]),
        },
    ),

    # ─ item (ported from 'object') ─────────────────────────────────
    "item": CategoryConfig(
        name="item",
        description="One pickupable sprite — potion, coin, key, weapon. "
                    "Small, centered, isolated.",
        style_prefix=(
            "single pixel art game item sprite, one item only, centered, "
            "clean edges, solid magenta background, bright magenta #FF00FF "
            "background, no shadow, no other objects, sharp pixels, "
            "16-bit style, "
        ),
        negative_prompt=_LEGACY_NEG,
        gen_size=(512, 512),
        variations=4,
        target_size=(32, 32),
        palette_colors=12,
        post_process=[
            "pixel_extract",
            "isolate_largest",
            "trim_transparent",
            "center_crop_object",
            "quantize_palette",
            "pixel_snap",
        ],
        scorer="item_scorer",
        min_acceptable_score=0.5,
        metadata_schema={
            "rarity": MetadataFieldSpec(type="enum",
                enum_values=["common", "uncommon", "rare", "epic", "legendary"]),
        },
    ),

    # ─ texture (ported) ────────────────────────────────────────────
    "texture": CategoryConfig(
        name="texture",
        description="Seamless tileable texture — single pattern, fills the "
                    "whole frame, no subject.",
        style_prefix=(
            "pixel art seamless tileable texture, top-down view, "
            "game asset, repeating pattern, sharp pixels, 16-bit style, "
        ),
        negative_prompt=_LEGACY_NEG,
        gen_size=(512, 512),
        variations=3,
        target_size=(64, 64),
        palette_colors=12,
        post_process=[
            "pixel_extract",
            "pixel_snap",
            "quantize_palette",
        ],
        scorer="texture_scorer",
        min_acceptable_score=0.5,
    ),

    # ─ tileset (new — recipes/tileset.md) ──────────────────────────
    "tileset": CategoryConfig(
        name="tileset",
        description="N×N grid of seamless terrain tiles — unified palette, "
                    "magenta gutter between tiles for clean grid recovery.",
        style_prefix=(
            "pixel art tileset sheet, N×N grid of square tiles, each tile "
            "is a distinct terrain type, tiles share a unified color "
            "palette, edges seamless between neighbors, top-down 2D view, "
            "solid magenta #FF00FF background between tiles, no characters, "
            "no shadows cast on tiles, clean pixel edges, 16-bit style, "
        ),
        negative_prompt=(
            "single tile, isolated, random colors, mismatched palette, "
            "3d, perspective, photo, realistic, blurry, soft, gradient, "
            "anti-aliased, text, labels, numbers, border, frame, "
            "characters, animals, objects on tiles, shadows, "
            "blurred edges between tiles, non-square tiles, trapezoid"
        ),
        gen_size=(1024, 1024),
        variations=4,
        target_size=(16, 16),  # PER TILE
        palette_colors=12,
        # autotile_variant_gen deferred to v1.2.
        post_process=[
            "pixel_extract",
            "grid_cut",
            "seamless_check",
            "trim_transparent",
            "pixel_snap",
            "pack_spritesheet",
        ],
        scorer="tileset_scorer",
        min_acceptable_score=0.4,
        metadata_schema={
            "biome": MetadataFieldSpec(type="string", required=True),
            "tile_grid_w": MetadataFieldSpec(type="int", required=True),
            "tile_grid_h": MetadataFieldSpec(type="int", required=True),
            "autotile_variants": MetadataFieldSpec(type="enum",
                enum_values=["none", "basic", "47", "blob"]),
            "shared_palette": MetadataFieldSpec(type="bool"),
        },
    ),

    # ─ background (new — recipes/background.md) ────────────────────
    "background": CategoryConfig(
        name="background",
        description="Wide horizontal parallax layer — no centered subject, "
                    "tileable left-to-right for camera scroll.",
        style_prefix=(
            "pixel art game background layer, wide horizontal composition, "
            "parallax-ready, no centered subject, no characters, "
            "no foreground objects, horizontally tileable left-to-right, "
            "top-down or side-view horizon line, solid magenta #FF00FF "
            "sky or bottom-edge alpha, clean pixel edges, 16-bit style, "
        ),
        negative_prompt=(
            "centered subject, character, enemy, player, hero, "
            "foreground object, isolated building, prominent tree, "
            "obvious focal point, vertical composition, portrait aspect, "
            "3d, photo, realistic, blurry, soft, anti-aliased, "
            "gradient background, text, watermark, border, frame, "
            "cropped, signature, different left and right edges"
        ),
        gen_size=(1024, 512),
        variations=3,
        target_size=(512, 256),
        palette_colors=16,
        # parallax_depth_tag deferred to v1.2.
        post_process=[
            "pixel_extract",
            "horizontal_tileable_fix",
            "pixel_snap",
        ],
        scorer="background_scorer",
        min_acceptable_score=0.4,
        metadata_schema={
            "layer": MetadataFieldSpec(type="enum",
                enum_values=["near", "mid", "far"]),
            "time": MetadataFieldSpec(type="enum",
                enum_values=["day", "dusk", "night", "dawn", "overcast"]),
            "biome": MetadataFieldSpec(type="string"),
            "tileable_horizontal": MetadataFieldSpec(type="bool"),
            "tileable_vertical": MetadataFieldSpec(type="bool"),
        },
    ),

    # ─ ui_element (new — recipes/ui_element.md) ────────────────────
    "ui_element": CategoryConfig(
        name="ui_element",
        description="Single UI chrome asset — button, panel, icon, bar. "
                    "Flat design, high contrast, retro-GUI aesthetic.",
        style_prefix=(
            "pixel art UI element, single game interface asset, flat design, "
            "clean geometric shapes, solid magenta #FF00FF background, "
            "centered, high contrast edges, sharp pixels, "
            "16-bit game menu aesthetic, minimal shading, bold outlines, "
        ),
        negative_prompt=(
            "realistic, photographic, 3d rendered, glossy, gradient, "
            "blurry, soft, anti-aliased, lens flare, bokeh, text, label, "
            "icon with letters, decorative serif, ornate filigree, baroque, "
            "cluttered, busy background, perspective, isometric, "
            "skeuomorphic, multiple elements, set"
        ),
        gen_size=(512, 512),
        variations=3,
        target_size=(64, 32),
        palette_colors=6,
        # nine_slice_detect deferred to v1.2.
        post_process=[
            "pixel_extract",
            "isolate_largest",
            "flat_color_quantize",
            "trim_transparent",
            "pixel_snap",
        ],
        scorer="ui_element_scorer",
        min_acceptable_score=0.5,
        metadata_schema={
            "role": MetadataFieldSpec(type="enum",
                enum_values=["button", "panel", "icon", "bar", "frame",
                             "cursor", "marker", "indicator"]),
            "is_nine_slice": MetadataFieldSpec(type="bool"),
            "state": MetadataFieldSpec(type="string"),
            "target_aspect": MetadataFieldSpec(type="string"),
        },
    ),

    # ─ effect (new — recipes/effect.md) ─────────────────────────────
    "effect": CategoryConfig(
        name="effect",
        description="Single visual-effect sprite — explosion, magic burst, "
                    "impact, glow. Radial, bright-core, transparent edges.",
        style_prefix=(
            "pixel art game effect, single visual effect sprite, "
            "bright glowing core, radial symmetry, centered, "
            "solid magenta #FF00FF background, high contrast, "
            "energetic composition, sharp pixels, 16-bit style, "
            "animation key-frame peak-intensity moment, "
        ),
        negative_prompt=(
            "full scene, landscape, character, enemy, monster, weapon, "
            "realistic, photo, 3d render, text, watermark, border, frame, "
            "multiple effects, smoke trail stretched to edges, static object, "
            "inert, unlit, dark center, cold, muted, subtle"
        ),
        gen_size=(768, 768),
        variations=5,
        target_size=(96, 96),
        palette_colors=24,
        post_process=[
            "pixel_extract",
            "radial_alpha_cleanup",
            "preserve_fragmentation",
            "trim_transparent",
            "additive_blend_tag",
            "pixel_snap",
        ],
        scorer="effect_scorer",
        min_acceptable_score=0.4,
        metadata_schema={
            "type": MetadataFieldSpec(type="enum",
                enum_values=["explosion", "magic", "impact",
                             "projectile_trail", "buff", "debuff",
                             "environmental"]),
            "element": MetadataFieldSpec(type="string"),
            "composite_mode": MetadataFieldSpec(type="enum",
                enum_values=["normal", "additive", "screen", "multiply"]),
            "loop_frame_hint": MetadataFieldSpec(type="enum",
                enum_values=["peak", "sustain", "fade"]),
        },
    ),

    # ─ portrait (new — recipes/portrait.md) ────────────────────────
    #
    # Recipe lists backend: ernie preferred, fallback: z_image. Per G2
    # we ship MVP with z_image only + fallback=None; Phase 6.2 swaps to
    # ernie + z_image fallback once ErnieBackend.generate is wired.
    "portrait": CategoryConfig(
        name="portrait",
        description="Head-and-shoulders portrait — JRPG dialogue style, "
                    "eyes visible, one face, magenta background.",
        style_prefix=(
            "pixel art character portrait, head and shoulders close-up, "
            "eyes clearly visible, facing forward or three-quarter view, "
            "solid magenta #FF00FF background, centered head, expressive "
            "face, clean silhouette, sharp pixel edges, "
            "16-bit JRPG dialog portrait style, "
        ),
        negative_prompt=(
            "full body, legs, feet, arms visible, weapon, inventory, "
            "background scenery, multiple faces, group portrait, "
            "tiny face in large frame, blurry, soft, anti-aliased, "
            "photographic, 3d render, realistic, anime gradient shading, "
            "painted background, text, speech bubble, name plate, "
            "caption, border decoration"
        ),
        gen_size=(512, 512),
        variations=4,
        target_size=(128, 128),
        palette_colors=20,
        backend="ernie",
        backend_fallback="z_image",
        post_process=[
            "pixel_extract",
            "isolate_largest",
            "eye_center",
            "head_only_crop",
            "trim_transparent",
            "pixel_snap",
        ],
        scorer="portrait_scorer",
        min_acceptable_score=0.5,
        metadata_schema={
            "character_id": MetadataFieldSpec(type="string"),
            "emotion": MetadataFieldSpec(type="string"),
            "facing": MetadataFieldSpec(type="enum",
                enum_values=["front", "three_quarter_left",
                             "three_quarter_right",
                             "profile_left", "profile_right"]),
            "age": MetadataFieldSpec(type="string"),
            "species": MetadataFieldSpec(type="string"),
        },
    ),
}


def get_category(name: str) -> CategoryConfig:
    """Dispatch by name; raises KeyError on unknown (generate_asset
    maps this to the `unknown_category` validator error)."""
    return CATEGORIES[name]


# ─── Metadata validation ─────────────────────────────────────────────

class MetadataSchemaViolation(ValueError):
    """Raised when `metadata` doesn't match the category's
    metadata_schema. Surfaced as the `metadata_schema_violation`
    validator error."""


def validate_metadata(
    category: str,
    metadata: dict,
) -> None:
    """Type-check `metadata` against the category's schema. Permissive
    on extra keys — recipes document canonical fields but authors may
    add freeform keys (e.g. `class` specialization). Reject when a
    required field is missing or a declared field has the wrong type."""
    cfg = CATEGORIES.get(category)
    if cfg is None:
        raise ValueError(f"unknown_category: {category!r}")
    schema = cfg.metadata_schema or {}

    for name, spec in schema.items():
        if spec.required and name not in metadata:
            raise MetadataSchemaViolation(
                f"{category}.{name} is required but missing"
            )
        if name not in metadata:
            continue
        value = metadata[name]
        if not _type_matches(spec, value):
            raise MetadataSchemaViolation(
                f"{category}.{name}: expected {spec.type}"
                + (f" in {spec.enum_values}" if spec.type == 'enum' else "")
                + f", got {type(value).__name__}={value!r}"
            )


def _type_matches(spec: MetadataFieldSpec, value) -> bool:
    t = spec.type
    if t == "string":
        return isinstance(value, str)
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "bool":
        return isinstance(value, bool)
    if t == "enum":
        return (isinstance(value, str)
                and (not spec.enum_values or value in spec.enum_values))
    if t == "list[int]":
        return (isinstance(value, list)
                and all(isinstance(v, int) and not isinstance(v, bool)
                        for v in value))
    if t == "list[float]":
        return (isinstance(value, list)
                and all(isinstance(v, (int, float))
                        and not isinstance(v, bool) for v in value))
    if t == "list[string]":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if t == "object":
        return isinstance(value, dict)
    return False
