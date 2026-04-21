# vfx_library

**Flag:** ANIM / LOOP (varies per VFX)
**Projection:** 2D stage-centered (no perspective; effect fills a square)
**Coral gap:** `asset_vfx_library_001`
**Consumer scaffolds:** every scaffold that needs on-screen VFX. The
library exists so scaffolds don't regenerate the same impact-burst,
healing-pulse, hit-flash twelve times.

20 canonical VFX described in `anim_set.json::vfx`; prompt template at
`prompt_template.md`. Each VFX is a short per-frame animation sequence
(1–12 frames). **This directory ships the catalog + 3 canary seeds;
the full 20-VFX library is built on demand** (`fire_vfx_library_full.py`
in `~/shoal_scratch/notes/` — not yet written, runs on the next Shoal
round that focuses on library production).

## Pick this library over a per-scaffold custom VFX when…

- The VFX is one of the 20 canonical names (impact_burst, ring_shockwave,
  dash_trail_loop, hit_flash, slash_diagonal, explosion, puff_of_smoke,
  sparkle_twinkle, lightning_bolt, freeze_ice, burn_fire_loop, heal_pulse,
  poison_cloud, bleed_drops, confusion_swirl, charm_hearts, sleep_Zs,
  stun_stars, death_spiral, shockwave_dust).
- The scaffold is willing to accept the library's style (per
  `color_palette` and `style_modifiers` defaults in `anim_set.json`). If
  the scaffold needs a different visual register (neon cyberpunk,
  grimdark, kawaii), the library serves as a reference template — clone
  the per-VFX entry, adjust `style_modifiers`, re-run the per-frame gen.

## Pipeline (per VFX)

1. Look up `anim_set.json::vfx[<name>]` → `{frames, per_frame_ms,
   seed_base, color_palette, poses}`.
2. For each `frame_index` in `0..frames-1`:
   - fill `prompt_template.md`'s placeholders
   - hit ERNIE `/v1/workflows/icon` with `seed = seed_base + frame_index`
   - set `overrides: {"keep_largest_only": False}` for spike/radial
     effects (see canary findings below). Use `True` only for
     compact-silhouette effects (single blob, orb, Z-character).
3. `postprocess.alpha_bbox_crop(frame, pad_px=24, out_side=256)` — tight
   crop and resize.
4. `postprocess.stack_horizontal(frames, spritesheet.png)` — N-wide
   strip. Or `postprocess.center_frame_in_square(frame, 128)` for grid
   engines that want fixed tiles.

## Per-VFX ERNIE call count budget

Per `anim_set.json::ernie_call_count.total`: **117 calls** for the full
20-VFX library. At ~9 s / Turbo call on a single pipeline that's ~17.5
min wall-clock; ~6 min with 3-way parallel pipelines (3 ERNIEs on pod).

## Canary corpus (3 single-frame renders)

Three canaries in this directory (see `canary_prompts.jsonl`):

- `canary_001_impact_burst_peak.png` — radial burst at peak, white-yellow-orange
- `canary_002_burn_fire_loop_phase3.png` — pixel-art flame mid-loop
- `canary_003_heal_pulse_peak.png` — emerald healing orb with plus-cross center

Each is a 256-px PNG ≤ 18 KB (pixel-art fire canary is 4 KB —
chromakey-perfect, limited-palette compresses beautifully).

## Library seed

`scaffolds/engine/asset_library/vfx_library/baseline_pixel_fire.png` —
the pixel-art fire canary. The cleanest chromakey result we observed;
serves as a style anchor for scaffolds that want "pixel-art VFX" aesthetic
and a reference for what clean magenta extraction looks like.

## Known caveats (from the 3-canary round)

### `keep_largest_only` picks the wrong default for spike-radial VFX

Canary 001 (impact burst) left large magenta patches between the star's
spike rays because `keep_largest_only=True` treats the effect as one
connected subject and preserves interior "holes" matching the
chromakey. Set `overrides.keep_largest_only = False` at the client
`/v1/workflows/icon` boundary for:

- Impact bursts, shockwaves, rings, radial explosions, slash arcs,
  lightning bolts, spiky VFX.

Keep `True` only for **compact-silhouette effects** where the subject is
a single blob without interior magenta pockets:

- healing orbs, hit flashes (star-shape but filled), sleep-Zs (solid Z),
  charm hearts (solid hearts), confusion swirls (filled spirals), charm
  hearts, poison clouds, dust puffs.

The per-VFX taxonomy in `anim_set.json` should (future work) grow a
`keep_largest_only` flag per VFX to set this automatically.

### Magenta-adjacent colors survive chromakey

Canary 003 (heal pulse) has a dark-maroon outer ring that survived
`extract_bg` because maroon is close-in-hue to magenta. The `color_palette`
placeholder already includes an explicit "avoid pure magenta chroma in
the effect" guardrail, which helps but isn't absolute. If a scaffold
needs colors near the magenta hue (purple, pink, deep red VFX), consider:

1. Swapping `mode=icon` (magenta chromakey) for `mode=alpha` (luminance
   chromakey) at the server call — black-on-black backgrounds with
   luminance keying. The tradeoff: soft edges lose opacity.
2. Running `normalize_palette(frames, max_colors=16)` with an excluded
   magenta hue to snap fringe colors away from the chromakey-killed
   range.
3. Regenerating with a seed bump and tighter color prompting.

### Pixel-art VFX render exceptionally cleanly

Canary 002 (pixel-art fire) had perfect chromakey, limited palette,
ready-to-ship quality. When a scaffold calls for pixel-art aesthetic,
the `style_modifiers: "pixel-art with visible pixel edges, no
antialiasing, 32-color limited palette"` value is worth inheriting
verbatim — it trades some visual range for bulletproof chromakey
behavior and tiny file sizes (canary_002 is 4 KB at 256 px).

### Animation-phase fidelity > character-identity fidelity

Unlike characters, VFX don't need consistent-identity across frames
(each frame is standalone art). This means:

- **Seed pinning** is per-(vfx_name, frame_index), not per-character.
  Frame 3 of impact_burst always renders with `seed=8001+3` regardless
  of run.
- **Parallel pipelines** help linearly — any frame can render on any
  pipeline.
- **Failed frames can be regenerated independently** by bumping just
  that frame's seed. No identity drift to worry about.
