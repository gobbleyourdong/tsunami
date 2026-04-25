# Character Pipeline — Status & Architecture

Captures the engine's character rendering + secondary animation + PBR
state as of this writing. Designed so a fresh session can pick up
without the prior conversation context.

## Pipeline at a glance

```
Per character:
  1. Mixamo rig loaded (~50-60 bones after virtual joint extensions)
  2. chibiMaterial(rig) → palette (16 slots) + per-bone palette indices
  3. chibiRaymarchPrimitives(rig, material) → ~50 RaymarchPrimitives
     - Head: sphere + cone-jaw (blend group 1)
     - Torso "potato sack": Spine/Spine1/Spine2/Hips ellipsoids + Neck
       box + LeftShoulder/RightShoulder spheres (group 6)
     - Arms: shoulder→arm→forearm→hand chain (groups 2 / 3)
     - Legs: upleg→leg→foot chain (groups 4 / 5)
     - Cape: 3-segment chain CapeRoot/CapeMid/CapeTip (group 9)
     - Bob hair: ellipsoid on Head (palette slot hair)
     - Grenades: 2 spheres on Hips (palette slot weapon)

Per frame:
  1. composer.update(frameIdx, characterParams) → bone world matrices
  2. Cape: tick node particle chain → override cape bone matrices
  3. Springs (hair + grenades): tick → override translation slots
  4. Reupload modified bone matrix slots to GPU
  5. Raymarch pass: writes G-buffer (color, normal+metalness, depth+roughness+ao)
  6. Outline pass: 3-band cel shading (shadow/lit/highlight) + NAVY edges
  7. Composite to canvas
```

## Files of record

| File | What |
|---|---|
| `src/character3d/skeleton.ts` | Procedural HUMANOID_RIG (16 bones), Vec3 type |
| `src/character3d/glb_loader.ts` | VAT loading, retarget composer (computes world matrices, uploads to GPU each frame) |
| `src/character3d/mixamo_loader.ts` | CHIBI_SLOTS, chibiMaterial, chibiRaymarchPrimitives (the ~1100-line primitive emitter), rig extension functions, DEFAULT_BODY_PARTS / DEFAULT_CAPE_PARTS / DEFAULT_BOB_HAIR / DEFAULT_GRENADE_BELT, SLOT_PBR table |
| `src/character3d/raymarch_renderer.ts` | RaymarchPrimitive type, WGSL raymarch shader, MRT G-buffer write, primitive storage buffer encoder, public API (setPrimitives, setPaletteSlot, etc) |
| `src/character3d/outline.ts` | 3-band cel shader, 4-conn NAVY outline, screen-space face-paint stamps (Mario eyes, mouth styles), depth-step interior outlines |
| `src/character3d/secondary.ts` | Spring system (single-mass jiggle for hair/breasts/grenades) |
| `src/character3d/node_particle.ts` | Chain mechanic with one-frame-stale parent reads (cape, long hair, tentacles) |
| `demos/skeleton_demo.ts` | The single test harness — wires everything, palette UI, PBR sliders, expression buttons, key bindings |
| `docs/bvh_layered_cache.md` | Future scene-partition architecture |

## Palette slots (CHIBI_SLOTS)

```
0  bg          (always black, never exposed to UI)
1  hair        — bob hair, ponytails
2  skin        — face, arms, hands, neck
3  shirt       — Spine/Spine1/Spine2 + shoulders
4  pants       — Hips + leg chain
5  shoes       — feet (currently roundedBox wedge)
6  eyewhite    — face feature (currently unused, eyes are stamps)
7  pupil       — face feature (currently unused)
8  mouth       — face feature (currently unused)
9  nose        — face feature (currently unused)
10 weapon      — sword rod accessory + grenades
11 accent      — pauldrons / belts / straps
12 fire_base   — VFX flame palette ramp
13 fire_mid
14 fire_tip
15 cape        — cape segments
```

Face features (eyes/mouth) emit no SDF primitives by default
(DEFAULT_FACE = []). All face details come from screen-space pixel
stamps in `outline.ts` shader.

## Blend groups

```
0  standalone (plain min, no smoothing)
1  Head + jaw + (formerly cheeks/sockets, removed) — group: 0.10 blend
2  LeftShoulder placeholder ... actually shoulders moved to group 6
2  LeftArm + LeftForeArm + LeftHand           — group: 0.055 blend
3  RightArm + RightForeArm + RightHand        — group: 0.055 blend
4  LeftUpLeg + LeftLeg + LeftFoot             — group: 0.055 blend
5  RightUpLeg + RightLeg + RightFoot          — group: 0.055 blend
6  TORSO SACK: Spine + Spine1 + Spine2 + Hips + Neck + both Shoulders — 0.07 blend
7  (reserved for SHIRT shells when wardrobe/clothing system lands)
8  (reserved for PANTS shells)
9  CAPE: CapeRoot + CapeMid + CapeTip         — 0.04 blend
10-15  reserved for additional clothing layers (greaves, plate, boots)
```

Cross-group → plain min (visible seam). Group sharing → smin (smooth).
Multi-character collision = future per-character offset, see
`docs/bvh_layered_cache.md`.

## Head shape (perfect primitive)

The head is intentionally just two primitives, locked across all
proportion presets — only the JAW WIDTH dials chibi vs normal.

```
HEAD (sphere, type 0):
  radius   = CHIBI_CENTERED_SIZE.Head[0] = 0.18
  offset   = CHIBI_CENTERED_OFFSET.Head = [0, 0.12, 0]
  blend    = group 1, radius 0.10

JAW (cone, type 12):
  half-angle  = sin = cos = 0.7071  (45°, anime/normal default)
              for chibi: drop sin toward 0.4 (rounder chin)
              for sharp: bump sin to 0.85 (pointy chin)
  height      = HEAD_RADIUS = 0.18
  rotation    = (1, 0, 0, 0)  → 180° X-axis flip; tip points DOWN
  offset.y    = head.offset.y - HEAD_RADIUS * 1.3
              = 0.12 - 0.234 = -0.114  (tip ~5cm below sphere bottom)
  blend       = group 1, radius 0.10
```

No nose, no cheeks, no eye sockets. Face features come from screen-
space stamps in the outline shader.

## Eye + mouth stamps (screen-space, pixel-exact)

Authored in `outline.ts`'s WGSL shader. Each eye/mouth is a fixed
pixel pattern stamped at a CPU-projected anchor.

Eye styles (ID in `faceFlags.x`):
- 0 mario   — 2×3, outer white col, inner W/B/B pupil pillar
- 1 dot     — single black pixel
- 2 round   — 2×2 solid pupil
- 3 goggles — 3×3, accent rim, inner pupil
- 4 glowing — 2×2 accent + bright core, pulses with `faceFlags.w`
- 5 closed  — 2×1 horizontal line (also forced when blink ≥ 0.5)
- 6 crying  — closed + 2-pixel cyan tear stream

Mouth styles (ID in `faceFlags.y`):
- 0 off, 1 line (3×1), 2 smile (corners + dip), 3 open_o (2×2),
- 4 frown (corners + rise), 5 pout (1×1 dot)

Anchor placement (in `skeleton_demo.ts`):
- Project face center (head-local 0, 0.115, 0.17) and one eye
  (head-local 0.055, 0.115, 0.17) to screen
- Compute unit "head right" axis from those two points
- Place anchors at fcRx ± ux (1 pixel each side of face center)
- Result: anchor separation = 2 pixels, ensuring 1-pixel gap between
  the two eye blocks regardless of LOD or character orientation
- Mouth at head-local (0, 0, 0.19)

Expression buttons drive a `FACE_STYLES` registry that picks
(eyeStyle, mouthStyle) per current expression. J cycles eye style
override; ./, cycle mouth style override.

## Secondary animation: TWO mechanisms

### 1. Spring (`secondary.ts`)
For SINGLE-MASS jiggle — a mass that wants to oscillate around an
anchor with overshoot. Has position + velocity state.

Used for:
- Bob hair (Head-anchored)
- Grenades on belt (Hips-anchored, one spring per grenade)
- Future: breast / butt / belly bounce, helmet feathers, ear baubles

Each spring tick:
```
displacement = position - restTarget
accel = -stiffness * displacement
velocity += accel * dt - velocity * (1 - damping)
position += velocity * dt
```

Defaults: stiffness 18, damping 0.90. Hair tighter (28 / 0.84),
grenades looser (14 / 0.93).

### 2. Node particle (`node_particle.ts`)
For CHAINS — each link trails the previous with one-frame-stale parent
reads. NO velocity state. Pattern from Returnal node particles.

Used for:
- Cape (Spine2 → CapeRoot → CapeMid → CapeTip)
- Future: long hair / ponytails / braids, tentacles, ribbons, trails

Each particle:
- restOffset (Vec3 in parent's local frame)
- minLength / maxLength (rigid-with-give clamp around restLength)
- prevParentPos (cached parent world pos from LAST frame)

Tick logic:
```
target = prevParentPos + restOffsetWorld    // STALE parent gives lag
clampedDist = clamp(dist(target, parentNow), minLength, maxLength)
position = parentNow + (target - parentNow) * (clampedDist / dist)
prevParentPos = parentNow                   // for NEXT frame's children
```

That's the whole tick — no integration, no springs, no instability.
Returnal pattern correctly attributed in node_particle.ts header.

## Cape integration in demo

Per-frame after composer.update(), in skeleton_demo.ts:
1. tickNodeParticle on each cape segment, top-down
2. For each cape bone, compute world matrix:
   - Translation = midpoint between segment top and bottom joints
   - +Y axis = (top - bottom) normalized   (chain direction)
   - +X axis = world X projected onto perpendicular plane
   - +Z axis = X × Y
3. Write into composer.worldMatrices[capeBoneIdx]
4. device.queue.writeBuffer for the 3-bone contiguous range (192 bytes)
5. invalidateRaymarchCache()

Cape is in blend group 9 (its own). Cross-group min against body keeps
the cape silhouette distinct.

## Choosing the right secondary mechanism

| Element | Mechanism | Why |
|---|---|---|
| Cape | Node particle chain | Wants chain flow, no bounce |
| Long hair / ponytail / braid | Node particle chain | Same |
| Tentacles, ribbons, trails | Node particle chain | Returnal exactly |
| Short hair / bob / crew cut | **Spring (head-anchored)** | Wants overshoot |
| Breast / butt / belly bounce | Spring | Wants overshoot |
| Grenades on belt | Spring per item | Wants overshoot |
| Head ornaments (feathers) | Spring per ornament | Wants overshoot |

Heuristic: if it extends past anchor bone's silhouette and trails →
chain. If it sits within the bone bulk and bounces → spring.

## PBR pipeline (current)

### Per-primitive scalar fields
`RaymarchPrimitive.metalness`, `.roughness`, `.ao` — all in [0,1].
Stored in primitive buffer slot 5 (vec4: m, r, ao, _).

### G-buffer pack
- `color.rgb` = albedo (palette tint), `color.a` = mask
- `normal.rgb` = encoded normal, `normal.a` = metalness
- `depth.r` = NDC depth, `depth.g` = roughness, `depth.b` = ao

### Cel shading (3 bands, in outline.ts)
```
shadowTone = 0.55 * (1 - 0.4*ao)     ; AO darkens shadow band
litTone    = mix(1.0, 1.18, metal)   ; metal brightens lit band
highlightThresh = 0.80 + 0.15*(1-glossy)   ; smooth = lower threshold
isHighlight = glossy > 0.5 && d > highlightThresh
if isHighlight: litTone = mix(1.40, 1.60, metal)
band = (d > 0) ? litTone : shadowTone
finalColor = albedo × band
```

### SLOT_PBR defaults (chibiRaymarchPrimitives post-process)
Per palette slot, applied to any prim that didn't set explicit values:
```
skin     m=0    r=0.85 ao=0.15
shirt    m=0    r=0.95 ao=0.25
pants    m=0    r=0.95 ao=0.25
shoes    m=0.10 r=0.55 ao=0.20    (leather sheen)
hair     m=0    r=0.40 ao=0.50    (visible highlight)
cape     m=0    r=0.95 ao=0.30
weapon   m=1.0  r=0.20 ao=0.10    (full metal, tinted highlight)
accent   m=0.60 r=0.30 ao=0.10
eyewhite m=0    r=0.30 ao=0.10
pupil    m=0    r=0.10 ao=0.05    (wet glossy)
mouth    m=0    r=0.30 ao=0.20    (moist)
nose     m=0    r=0.85 ao=0.20
```

### UI sliders
Per palette slot in the palette panel: M / R / AO sliders next to the
color picker. On change, walks faceRaymarchPrims, updates per-prim
PBR fields, calls raymarch.setPrimitives() + invalidateRaymarchCache.

## Procedural patterns (colorFunc 4-6, NEW this session)

Patterns evaluate in PRIMITIVE-LOCAL space (the same coordinate the
SDF eval already computes via worldToLocal). Bind-space anchoring is
free — patterns stay fixed to the body part across animation.

```
0 flat        (existing) — always paletteSlot
1 gradientY   (existing) — slotA at bottom, slotB at top, 3 bands
2 pulsate     (existing) — time-oscillating slot swap
3 radialFade  (existing) — slotA center, slotB edge
4 stripes     (NEW)      — alternating slotA/slotB along local Y
                         colorExtent = stripes per metre
5 dots        (NEW)      — circular dots tiled in primitive-local XY
                         colorExtent = cell size in metres, dot radius = 0.30 × cell
6 checker     (NEW)      — 3D checker in primitive-local space
                         colorExtent = cell size in metres
```

To use: set `primitive.colorFunc = 4`, `primitive.paletteSlotB = N`,
`primitive.colorExtent = 8` (stripes per metre).

UI for testing patterns NOT yet wired (next tick).

## What's still open (roadmap)

**Tick 10 finishing**: UI control to test procedural patterns per slot.
**Tick 11**: Real AO from neighbour-SDF sampling (per-pixel, replaces
            per-primitive scalar AO).
**Tick 12**: Decal projection — small storage buffer of decal
            (worldPos, projectionAxis, halfExtents, image),
            iterated per pixel in color-decision section. Reuses the
            face-marks pattern (storage buffer at binding 4).
**Future**: Wardrobe system (V3 character spec, ClothingSpec with
            wardrobe identifier referencing engine WARDROBE library).
            Color manipulation already works via existing palette
            picker + setPaletteSlot. Shell primitives for clothing
            volume not yet emitted.
**Future**: Layered BVH cache (see docs/bvh_layered_cache.md) for
            environments, multi-character scenes, destructible props.

## Key bindings (demo)

```
1/2/3/4   sprite mode (sz24/sz32/sz48/debug)
V         cycle view: color / normal / depth
M         next animation
D         depth outline on/off
L         lighting on/off (PBR effects only fire when on)
T         rest pose toggle
K         naked-man mode (clothing slots → skin)
F         preview mode toggle
J / shift+J  cycle eye style override
. / ,     cycle mouth style override
[ / ]     adjust eye spacing in pixels
space     spawn swipe VFX
X         spawn impact-star VFX
Z         spawn muzzle-flash VFX
N         spawn lightning VFX
B         spawn beam VFX
```

UI buttons: proportion preset (chibi / stylized / realistic),
expression (neutral / blink / smile / surprise / squint / crying),
palette + PBR sliders per slot.

## Memory locations

User profile + project context lives in
`/home/jb/.claude/projects/-home-jb-ComfyUI-CelebV-HQ-ark/memory/`.
See MEMORY.md index. Particularly relevant:
- `face_marks_doctrine.md` (superseded by screen-space stamps)
- `vat_lut_character_pipeline.md` (overall architecture)
- `3d_first_pipeline.md`
- `sdf_vfx_unification.md`
- `deferred_lighting_doctrine.md`
- `raymarch_cache_occlusion.md`
- `proportion_as_lod.md`

---

# Addendum — second pass

Captures changes since the document above was first written.

## Lighting (simplified to two-tone)

PBR was tried (per-prim metalness/roughness/AO, highlight band, SDF AO)
and pulled out. Smin'd convex characters have no crevices for SDF AO
to find, and roughness control ended up too complicated for the cel
look we want. Current state:

- **Ambient** — `(0.85, 0.86, 0.90) × 0.55`, near-neutral with faint cool
  bias. Applied to every lit pixel.
- **Key directional** — `lights[0]`, white `(1, 1, 1)`, intensity 0.55.
  Cel-quantized: `n·keyDir > 0` → full contribution, else 0.
- **No fill** — `lights[1]` slot reserved, intensity 0.
- **Point lights** — up to 4 transient, used by VFX (muzzle flashes,
  flares, explosion bursts). Quadratic falloff is CEL-QUANTIZED:
  hard ring at the radius + cel terminator from `n·lightDir > 0`.
  No smooth gradient anywhere.
- **Lighting modes**: 0 = off (flat), 1 = on (ambient + key + active
  point lights). Two-state toggle on `L`.

Day/night cycle hooks naturally onto this — sunrise/dusk = warm-tinted
ambient + warm key; midnight = very-low blue ambient + maybe no key.

### Shadow saturation boost (color-burn)

On shadow-side pixels, albedo gets extrapolated AWAY from its grayscale
luminance by 1.2× before multiplying by ambient — pushes saturation so
shadows feel deep instead of flat-multiplied gray. `clamp(mix(luma,
albedo, 1.2), 0, 1)` keeps colours in valid RGB.

### Selective specular (`shiny` flag, dormant)

Per-primitive `shiny: boolean` exists but no slot auto-flags it. When
set, surface gets a hot-spot at `keyDot > 0.85`. For pixel-art correct
specular (1-2 pixel dot, not a wash), threshold needs to climb to ~0.97
per-slot — work for later. Reference notes in mixamo_loader's authoring
sweep comment.

### Unlit primitives (`unlit` flag)

VFX primitives carry their own bright emissive colour and shouldn't get
cel-shaded. Per-prim `unlit: boolean` bit-packed into colorFunc bit 6
(0x40). Outline pass reads it from `depth.g`, skips the entire lighting
block for those pixels. `VFXSystem.getPrimitives()` auto-flags every
emitted prim. The persistent right-hand flame is also flagged.

## Cape (final architecture)

5-segment chain `Cape0..Cape4`:

- Bone names: `Cape0` (root, locked anchor at shoulder) through
  `Cape4` (tip).
- Cape0 is LOCKED — every frame, `position = Spine2.world +
  rotated((0, 0.10, -0.20))`. No stale-read lag at the attachment.
  Cape root rigidly tied to body, can't drift forward into the torso.
- Cape1..4 use node-particle physics — one-frame-stale parent reads
  + distance clamp. Each segment lags previous by one frame.
- Rest offsets all rotate by Spine2's world matrix per frame, so the
  cape follows body rotation (faces "behind" relative to body, not
  world axes).
- Wind: world-space drift biased into the offsets, scaled by chain
  depth so tip flutters more than root.
- Body collision: bounding spheres at Spine2 (r=0.16) and Hips
  (r=0.17). Particles 1..4 push out radially when inside.
- Render: each bone's segment spans `particle[i] → particle[i+1]`,
  centered at the midpoint with +Y axis along the chain direction.
  The last bone extrapolates a tail of `CAPE_SEG_DROP` for a clean
  hem. NO segment between Spine2 and Cape0 (which is what caused the
  earlier "abrupt up-bend" at the attachment).
- Smin: blend group 9, blend radius 0.08m. Adjacent primitives
  overlap 0.08m on each side (halfY 0.13, segment spacing 0.18m), so
  smin has a real fusion zone — cape reads as one continuous cloth
  volume, not stacked blocks.

## Hair (current: locked to head)

Single ellipsoid `HairBob` parented to Head, offset `(0, 0.16, 0)`,
displaySize `(0.22, 0.16, 0.22)`. Sits as a brown shell over the
upper cranium with the lower face exposed. **Not spring-driven** —
single rigid primitive, "lock root + move tip" reduces to "stay glued
to head."

Long hair will revisit with multi-segment chains: root segment locked
to head (same pattern as Cape0 → Spine2), tip segments use chain
physics or per-tip springs.

## Update pipeline (Unreal-style)

```
update animation  →  update physics  →  draw
```

Both anim (`composer.update`) and physics (cape, springs) tick on the
sprite-FPS cadence (8-15Hz depending on sprite mode). Render runs free
at display refresh.

Implementation: a `tickShouldRun` flag detects frame change OR rest-
pose toggle; gates composer.update + cape secondary + spring updates.
Between ticks the GPU keeps last-tick world matrices, the raymarch
cache stays valid, and the frame is essentially a free blit. Massive
headroom for non-rendering work (audio, AI, network, gameplay).

Camera moves still trigger raymarch (the camera.view fingerprint is a
separate cache invalidation axis, independent of anim/physics).

## Removed / parked

- **Per-prim PBR** — metalness, roughness, ao fields removed from
  `RaymarchPrimitive`. Encoding shrunk back to 5 vec4 per prim (was 6).
- **SDF AO** — 5-tap Inigo Quilez sampling removed; smin'd convex
  characters had no crevices to find.
- **Highlight band** — code stays in outline shader behind the dormant
  shiny flag. Per-slot threshold work is future.
- **Mode 2 lighting (point-only)** — collapsed back to single "on"
  state since point lights now layer on top of directional.
- **chibi_head SDF (type 13)** — pixel-fitted head from /tmp/sdf_research,
  kept in the shader but not currently emitted. The `max(side, front)`
  combine of two extruded silhouettes produces square-from-top cross-
  sections; needs rework into elliptical-cross-section approach before
  re-enabling.

## Files added

- `src/character3d/secondary.ts` — single-mass spring (jiggle).
- `src/character3d/node_particle.ts` — chain mechanic (cape, long hair,
  tentacles, ribbons).
- `docs/bvh_layered_cache.md` — future scene-partition architecture.
- `docs/character_pipeline_status.md` — this document.
