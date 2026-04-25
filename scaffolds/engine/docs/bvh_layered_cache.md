# Layered BVH Cache — Environment & Scene Partitioning

Status: **Plan**. Not yet implemented. Captures the architecture for
extending today's single-character raymarch cache into a layered scene
renderer suitable for environments + multiple characters.

## The problem

Today the renderer treats the scene as one flat primitive list with one
offscreen-FB cache. That's correct for a single character on an empty
canvas. It breaks the moment we add:

- A static environment (sky, terrain, buildings) that should render once
  and be reused, not re-marched every frame.
- Destructible mid-ground props (barrels, fences) that should re-march
  only when something changes.
- Multiple characters sharing the scene — currently their primitives
  would all live in one flat list with one BVH, no partition.

The cure: per-layer primitive lists, per-layer BVH, per-layer cache
invalidation, deferred-composite final pass.

## Four-tier scene partition

| Layer | Update rule | Cache strategy | Example contents |
|---|---|---|---|
| **L0 — BG** | On level load | Bake once, reuse forever | Sky, distant terrain, parallax mountains |
| **L1 — MG static** | On level load | Bake once | Buildings, fixed props, ground tiles |
| **L2 — MG destructible** | On AABB change | Cache + dirty-mark per element | Barrels, breakable walls, hazards |
| **L3 — animated** | Every frame | No cache | Player, enemies, projectiles |

L0 and L1 collapse into one cache in practice (nothing in either ever
moves). L2 stays separate because destruction events are localised —
when one barrel breaks, only its AABB region invalidates. L3 is the
existing per-frame raymarch.

For most frames in a typical level, only L3 raymarches. L2 fires
occasionally during combat. L0/L1 are pure read. Total per-frame
raymarch cost drops to ~10-20% of today's "march everything" model.

## Per-layer BVH

Each layer builds an AABB tree once, traversed per ray:

- Cost per ray drops from O(N) flat scan to O(log N) tree walk
- Rays that hit only L0 (sky, distant) never touch L2 / L3 at all
- The existing per-primitive bounding-sphere check (in
  `raymarch_renderer.ts:584-588`) is essentially a 1-level BVH —
  generalising to a real tree is incremental, not a rewrite

A 2-level BVH (root AABB → leaf primitive groups) covers most real
scenes. 3+ levels only matter at hundreds of primitives per layer.

## Cache invalidation rules

- **L0 / L1**: dirty bit set only on level load or zone transition.
  Cache lives until the player leaves the zone.
- **L2**: per-element dirty bit. When element destroyed or moved →
  mark its screen-space AABB dirty → next frame, re-raymarch ONLY
  the dirty AABB region, not the whole layer. Same trick used for
  screen-space damage decals.
- **L3**: always-dirty (existing behaviour).

L2 partial invalidation is the key efficiency: a one-barrel destruction
re-marches a 30×30-pixel region, not a 256×256 cache.

## Cross-layer interactions: deferred composite

The classic "shadow on terrain" problem — character casts shadow on
wall, but wall's cached image doesn't have the shadow. Solution is
what deferred renderers do today:

**Each layer caches a G-buffer (color + normal + depth), not a finished
image.** Shading happens in a final composite pass:

1. Walk layer caches back-to-front, pick nearest depth per pixel
2. Apply animated lights, character shadows, post-effects
3. Run the existing outline pass (depth-edge detection) on the
   composited depth buffer

Today's pipeline already does deferred shading — raymarch writes
G-buffer, outline pass does shading. Per-layer G-buffers is an
incremental change to that, not a rewrite.

## Multi-character blend-group collision

Adjacent issue worth flagging now so it's not a forced rewrite later.

Today's blend groups are scene-global (1=Head, 2-3=arms, 4-5=legs,
6=body sack, 7-9=clothing/cape). When two characters share a frame:

```
Character A: head=1, arms=2/3, legs=4/5, body=6
Character B: head=1, arms=2/3, legs=4/5, body=6
```

A's spine and B's spine smin together when they walk past each other.
Wrong.

Three fixes, ranked by complexity:

1. **Per-character group offset.** Reserve groups by character index:
   char-0 uses 1-15, char-1 uses 16-30. Shader uses
   `localGroupId = primitive.blendGroup - characterBase`. Caps at
   ~4 characters with the current 16-group accumulator. **Right
   answer for most games.**
2. **Per-character accumulator array.** Bump
   `array<f32, 16>` to `array<f32, 16 * MAX_CHARACTERS>`, key by
   `(characterIdx, localGroup)`. Linear shader cost increase.
3. **Cross-character group masking.** Each primitive carries a
   `characterMask: u32` bitfield; smin only fuses primitives with
   matching masks.

For sprite games with 1-3 characters typically on screen, **option 1**.
Reserve a private 16-group range per character. Bake the offset into
`chibiRaymarchPrimitives()` when emitting:

```ts
const baseGroup = characterIdx * GROUP_BASE_PER_CHAR
// Head: blendGroup = baseGroup + 1
// Body sack: blendGroup = baseGroup + 6
// Cape: blendGroup = baseGroup + 9
```

The shader's `MAX_BLEND_GROUPS` becomes 64 (4 chars × 16). Cheap.

**Decision flag for current cape work**: emit shells with `baseGroup +
N` instead of literal group indices. Even if multi-character ships
later, baking the offset in early prevents a forced rewrite.

## Implementation order

Each step is independently shippable:

1. **Rename existing cache to L3.** No behavioural change. Establishes
   the layer concept.
2. **Add L0+L1 combined cache.** Populated on scene load with all
   "static" primitives. Composite L0+L1 with L3 by depth.
3. **Layered composite pass.** Deferred-style: each layer writes a
   G-buffer, composite picks nearest depth per pixel, outline runs
   on the composited depth.
4. **Add L2 with per-element AABB invalidation.** Destructible props
   stop re-marching every frame.
5. **Per-layer BVH.** Optimization, can land last. Single-level
   bounding-sphere check (today's behavior) → 2-level AABB tree →
   N-level if needed.
6. **Multi-character blend-group offsets.** Per-character group
   ranges. Necessary when more than one character ships on screen.

## Decision triggers

Don't build any of this until one of these fires:

- **Environment work begins.** Need cached terrain, build steps 1-3.
- **Destructible props show up.** Step 4.
- **Multi-character scenes ship.** Step 6.
- **Per-frame raymarch budget exceeds 50% of frame time at target
  resolution.** Steps 1-5 unlock 5-10× headroom.

Until then: today's single-cache model is correct. This doc exists to
prevent forced rewrites by laying the architectural marker now.

## Related design docs

- `secondary.ts` — spring jiggle for single-mass attachments.
- `node_particle.ts` — chain mechanic for capes / long hair / trails.
- *PBR sweep* (planned) — material params (metalness, roughness, AO)
  layered onto the existing G-buffer.
