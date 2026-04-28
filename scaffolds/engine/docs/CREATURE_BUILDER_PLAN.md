# Creature Builder — Overnight Runbook

**STATUS (v1 complete)**: All 6 plan tasks delivered across overnight session iters 1-11. See "v1 Completion Summary" at the bottom for what shipped, the commit chain, and the open polish items for v2.

**Goal**: extend the humanoid character system into a full creature builder. One rig + one anim library. Creature variety comes from per-bone scale overrides, procedural limb attachments, and chain-driven cosmetics. Spider, dragon, bird, quadruped, snake-thing — all from the same skeleton.

**Vision** (per user direction earlier in session):

> "we just need to make sure slots are set up as permaslots and then things slot in and out"
> "I plan to do 1 million cosmetics instead of training a model because that's how cheap our assets are"

A creature spec becomes a 5-10 line JSON: `{ bone_overrides, attachments, procedural_limbs, default_anim }`. Composing them = building creatures.

---

## Architecture (what reuses, what's new)

| Capability | Already in place | Need to add |
|---|---|---|
| Per-bone scale (proportion presets) | ✅ characterParams.scales[boneIdx] | per-bone runtime override layer (overrides preset values) |
| Chain attachments (cape, tail, hair, strands) | ✅ simulateRibbonChain helper | new chains: wings, snake-neck, procedural limbs |
| Type-23 ribbon SDF with taper | ✅ params.w = tipScale (just added) | reuse for wings + snake body |
| Cone SDF for spike-style attachments | ✅ type 12 + radialSpikeRot | maybe reuse for claws, horns |
| Bone hierarchy extension | ✅ extendRigWithBodyParts / WithHair | add wings + snake bones to permaslot |
| Animation library | ✅ 25 mixamo VATs (after tonight's bake) | use crawling, running_crawl, mutant_run for quadruped |
| Loadout toggles + UI rows | ✅ pattern: makeRow + boolean | add toggles for each new attachment |
| Save/load (V2 spec) | ✅ serializeCharacter / loadout merger | add new fields |

The system is in good shape — most of this work is **adding attachments under the existing patterns**, not designing new mechanisms.

---

## Task List (build order — cheapest first, most disruptive last)

### Task 1: Wings (in flight — partial) — ~30 min

**Status**: bones added (DEFAULT_WINGS_L, DEFAULT_WINGS_R, DEFAULT_WINGS) in `mixamo_loader.ts`. Emission + loadout wiring TODO.

**Files**:
- `scaffolds/engine/src/character3d/mixamo_loader.ts` — already has bone defs near `DEFAULT_TAIL`
- `scaffolds/engine/demos/skeleton_demo.ts` — needs loadout, allBodyParts, primitive lookup, UI

**Steps**:
1. Add primitive emission in `mixamo_loader.ts` `chibiRaymarchPrimitives`. After the `^Tail` branch, add:
   ```ts
   } else if (/^Wing(L|R)0$/.test(name)) {
     const sideKey = /WingL/.test(name) ? 'L' : 'R'
     const halfW = bp.displaySize[0]
     const halfThick = bp.displaySize[2]
     const wingIndices: number[] = [j]
     for (let k = 1; k < 4; k++) {
       const idx = rig.findIndex(joint => joint.name === `Wing${sideKey}${k}`)
       if (idx >= 0) wingIndices.push(idx)
     }
     if (wingIndices.length < 2) continue
     prims.push({
       type: 23, paletteSlot: slot, boneIdx: j,
       params: [wingIndices.length, halfW, halfThick, 0.15],   // tipScale=0.15 → very pointy at tip
       offsetInBone: [0, 0, 0],
       blendGroup: 19, blendRadius: 0,    // own group, distinct from cape/tail
     })
   } else if (/^Wing/.test(name)) {
     continue   // chain-only contributors
   }
   ```
2. Add `Wing` regex to `accessorySlot()` so it routes to `CHIBI_SLOTS.cape` (or new `feather` slot — TBD).
3. In `skeleton_demo.ts`:
   - Import `DEFAULT_WINGS_L`, `DEFAULT_WINGS_R`, `DEFAULT_WINGS`
   - Add to `bodyAndExtras` rig extension list (~line 222)
   - Add `wings: boolean` to Loadout interface
   - Add `wings: false` to default loadout
   - Add to `bodyAndExtrasPrims` for runtime
   - Add to `rebuildPersistentPrims`'s `bodyAndExtras` filter list with `loadout.wings ? DEFAULT_WINGS : []`
   - Save/load: `serializeCharacter` write, `loadFromSpec` read, legacy compat
   - UI: `makeRow('wings', ['on', 'off'], () => loadout.wings, ...)`
   - Shuffle/reset functions
4. Update `head` GROUP_PATTERNS regex? **No** — wings are torso-anchored (LeftShoulder/RightShoulder are in torso group already)
5. Verify in browser: toggle wings on/off, see them extend from shoulders.

**Acceptance**: with `wings: on`, character has visible 50cm wing membrane on each side.

### Task 2: Hind retarget (quadruped) — ~15 min

**Goal**: zero out the shin scale on both legs so the foot lands where the knee was, giving humanoid bones a quadruped silhouette. Combine with `crawling` or `running_crawl` anim.

**Files**:
- `skeleton_demo.ts` only — pure runtime override.

**Steps**:
1. Add `quadrupedHind: boolean` to Loadout interface, default `false`
2. Add UI row `makeRow('quad', ...)`
3. Save/load: serializer + legacy load
4. Shuffle/reset
5. After `applyPreset()` in init AND in the toggle callback, call:
   ```ts
   function applyHindRetarget() {
     const lLegIdx = rig.findIndex(j => j.name === 'LeftLeg')
     const rLegIdx = rig.findIndex(j => j.name === 'RightLeg')
     if (loadout.quadrupedHind) {
       if (lLegIdx >= 0) characterParams.scales[lLegIdx] = [1, 0.05, 1]
       if (rLegIdx >= 0) characterParams.scales[rLegIdx] = [1, 0.05, 1]
     } else {
       // Restore via re-applying the proportion preset
       applyPreset(currentProportion)
     }
     invalidateRaymarchCache()
   }
   ```
   Why 0.05 not 0: avoid degenerate columns in worldToLocal. Translation column is unaffected by scale → Foot world position naturally collapses to Knee position.

**Acceptance**: with `quadrupedHind: on` + `crawling` animation, character looks like a dog/cat on all fours.

### Task 3: Procedural extra limbs (spider) — ~60 min

**Goal**: 4 phantom limbs that PHASE-OFFSET copy the world transforms from the existing 4 limbs. Spider ends up with 8 effective legs.

**Files**:
- `mixamo_loader.ts` — add `DEFAULT_EXTRA_LIMBS` body parts
- `skeleton_demo.ts` — per-frame transform copy

**Bone definitions** (4 phantom limbs, parented to Hips — ride along with hip rotation):
```ts
export const DEFAULT_EXTRA_LIMBS: BodyPart[] = [
  // Front-left extra: copies LeftArm chain phase-offset by 0.5 cycles
  { name: 'ExtraFL_Up',   parentName: 'Hips',      offset: [-0.10, 0.10,  0.10], displaySize: [0.04, 0.20, 0.04] },
  { name: 'ExtraFL_Lower',parentName: 'ExtraFL_Up',offset: [ 0.00,-0.20,  0.00], displaySize: [0.03, 0.18, 0.03] },
  { name: 'ExtraFL_Tip',  parentName: 'ExtraFL_Lower', offset: [0.00,-0.18, 0.00], displaySize: [0.03, 0.05, 0.03] },
  // Front-right mirror
  { name: 'ExtraFR_Up',   parentName: 'Hips',      offset: [ 0.10, 0.10,  0.10], displaySize: [0.04, 0.20, 0.04] },
  // ... etc for FR, BL, BR, each parented to Hips
]
```

**Per-frame transform copy** (after composer.update, before raymarch render):
```ts
function applyExtraLimbsCopy() {
  if (!loadout.extraLimbs) return
  const wm = composer.worldMatrices
  // Map: extra limb bone → source limb bone + phase offset
  const COPIES: { extra: string; source: string; phaseShift: number }[] = [
    { extra: 'ExtraFL_Up', source: 'LeftArm', phaseShift: 0.5 },
    // etc.
  ]
  // For phase shift: we'd want to sample the source bone at frameIdx + 0.5*numFrames % numFrames
  // BUT current composer evaluates ONE frame at a time. To get phase-offset,
  // either: (a) pre-bake a separate mat list per phase, (b) cycle two frames 
  // and lerp, (c) just copy directly without phase offset for v1.
  
  // V1 SIMPLE: just copy with NO phase offset — extras mirror their source 1:1
  // (so spider has 8 legs all moving in phase). Add phase shift in v2.
  for (const c of COPIES) {
    const srcIdx = rig.findIndex(j => j.name === c.source)
    const dstIdx = rig.findIndex(j => j.name === c.extra)
    if (srcIdx < 0 || dstIdx < 0) continue
    const srcOff = srcIdx * 16
    const dstOff = dstIdx * 16
    // Copy the FULL 4×4 matrix
    for (let i = 0; i < 16; i++) wm[dstOff + i] = wm[srcOff + i]
    // Then translate to the offset position relative to Hips
    // ... offset math here ...
    device.queue.writeBuffer(vatHandle.buffer, dstIdx * 64, wm.buffer, wm.byteOffset + dstOff * 4, 64)
  }
  invalidateRaymarchCache()
}
```

**Caveats**:
- Phase offset needs frame-N + frame-N+offset mat blending. Skip for v1.
- Position offset: tricky because we want the EXTRA limb to be at a different anchor (hip-side) but COPY rotation from the source. Manually compose: extra_world = newAnchor_world × (relative rotation from source's anchor to source bone).

**Acceptance**: with `extraLimbs: on` + `crawling`, character has 8 limbs, all in phase. Spider silhouette readable in profile.

### Task 4: Snake-neck rig — ~45 min

**Goal**: replace humanoid Head with a chain that extends forward from Neck. Tip carries the visible head primitive.

**Files**:
- `mixamo_loader.ts` — add `DEFAULT_SNAKE_NECK` body parts
- `skeleton_demo.ts` — chain physics call site, head visibility override

**Bone defs** (5-bone chain forward from Neck):
```ts
export const DEFAULT_SNAKE_NECK: BodyPart[] = [
  { name: 'SnakeNeck0', parentName: 'Neck',      offset: [0, 0.05,  0.10], displaySize: [0.06, 0.10, 0.06] },
  { name: 'SnakeNeck1', parentName: 'SnakeNeck0',offset: [0, 0.00,  0.10], displaySize: [0.05, 0.10, 0.05] },
  { name: 'SnakeNeck2', parentName: 'SnakeNeck1',offset: [0, 0.00,  0.10], displaySize: [0.05, 0.10, 0.05] },
  { name: 'SnakeNeck3', parentName: 'SnakeNeck2',offset: [0, 0.00,  0.10], displaySize: [0.04, 0.10, 0.04] },
  { name: 'SnakeNeckHead', parentName: 'SnakeNeck3', offset: [0, 0.00, 0.10], displaySize: [0.08, 0.06, 0.07] },
]
```

**Primitive emission**: type-23 ribbon for the body chain (`SnakeNeck0..3`) + ellipsoid for the tip head (`SnakeNeckHead`). Use new palette slot `snake_skin`?

**Chain physics**: Use existing `simulateRibbonChain`. Anchor=Neck, anchorOnBack=false (front-anchored), gravity OFF (snakes hold their head up).
- This means we need the helper to support "no gravity drape" — a flag to disable the tip drape blend.
- Or just set `restDirSin = 0` and let the rest target be the bind-pose forward direction.

**Head hide**: when `loadout.snakeNeck: true`:
- Set `characterParams.scales[HeadIdx] = [0.05, 0.05, 0.05]` (collapse Head bone)
- Skip emission of Head primitive (filter in `chibiRaymarchPrimitives` based on a flag, OR conditionally include in `hairList`)

**Acceptance**: with `snakeNeck: on`, head sphere disappears and a 50cm tapering snake body extends forward from neck. Tip has a visible head ellipsoid.

### Task 5: Creature presets (load all the above) — ~30 min

**Goal**: one-click "spider", "dragon", "bird", "horse", "snake" buttons that set the right combination of toggles + scales + default anim.

**Files**:
- `skeleton_demo.ts` — new preset map + UI buttons

**Preset spec** (TypeScript object literal):
```ts
const CREATURE_PRESETS = {
  human:   { wings: false, quadrupedHind: false, extraLimbs: false, snakeNeck: false, defaultAnim: 'idle' },
  spider:  { wings: false, quadrupedHind: false, extraLimbs: true,  snakeNeck: false, defaultAnim: 'crawl_backwards' },
  dragon:  { wings: true,  quadrupedHind: true,  extraLimbs: false, snakeNeck: true,  defaultAnim: 'crawling',
             tail: true,   spikesBack: true,    bob: false },
  bird:    { wings: true,  quadrupedHind: false, extraLimbs: false, snakeNeck: false, defaultAnim: 'idle',
             // arms scaled to 0 — wings replace them
             override_LeftArm:  [0,0,0], override_RightArm: [0,0,0] },
  horse:   { wings: false, quadrupedHind: true,  extraLimbs: false, snakeNeck: false, defaultAnim: 'running_crawl',
             tail: true,   bob: true },
  snake:   { wings: false, quadrupedHind: false, extraLimbs: false, snakeNeck: true,  defaultAnim: 'crawling',
             // arms + legs all collapsed
             override_LeftArm: [0,0,0], override_RightArm: [0,0,0],
             override_LeftUpLeg: [0,0,0], override_RightUpLeg: [0,0,0] },
}

function applyCreaturePreset(name: keyof typeof CREATURE_PRESETS) {
  const p = CREATURE_PRESETS[name]
  for (const k of Object.keys(p)) {
    if (k.startsWith('override_')) {
      const boneName = k.replace('override_', '')
      const idx = rig.findIndex(j => j.name === boneName)
      if (idx >= 0) characterParams.scales[idx] = (p as any)[k]
    } else if (k === 'defaultAnim') {
      switchAnimation(animations.findIndex(a => a.tag === (p as any)[k]))
    } else {
      (loadout as any)[k] = (p as any)[k]
    }
  }
  rebuildPersistentPrims()
  invalidateRaymarchCache()
}
```

**UI**: row of buttons. `human / spider / dragon / bird / horse / snake`.

**Acceptance**: clicking each button visibly transforms the character into that creature with no further config needed.

### Task 6: Polish + edge cases — ~30 min

- **Procedural limb phase offset**: pre-bake an offset frame index per source so spider legs alternate. Use frameIdx + numFrames/2 mod numFrames.
- **Wing flap animation**: simple sin-driven y-rotation per wing bone, frequency 5Hz, amplitude 30°. Toggle `loadout.wingFlap: boolean`.
- **Snake-neck idle motion**: subtle weave motion via wind-style perturbation in chain rest target (already supported by simulateRibbonChain `wind` param).
- **Anatomy pass**: per-creature, hide unused bones (e.g. snake doesn't need Spine ellipsoids visible; dragon doesn't need humanoid Head).

---

## Risks / Gotchas

1. **Bone hierarchy explosion**: every creature attachment adds 4-8 bones to the rig. Currently rig is ~80 bones. After all creature additions: ~120 bones. VAT memory + bind group overhead grows linearly. Acceptable but watch performance.

2. **Procedural limb position**: copying transforms from one bone to another only gets the ROTATION right. Position needs explicit anchor offset. Make sure `Hips × extraOffset × source's_local_rotation` composes correctly.

3. **Tip-taper on wings**: type-23 ribbon already supports it via `params.w = tipScale`. Wings should look feather-tipped at value 0.15.

4. **Per-bone visibility**: currently filter is `if scale.x < 0.01 skip primitive`. Make sure this applies to PRIMITIVE EMISSION at runtime (`rebuildPersistentPrims`), not just at compile time. Otherwise toggles won't update render.

5. **DAE bake script gotcha**: bake_dae_vat.mjs uses `name.replace(' ', '_')` — single replace. For "Crawl Backwards", first space replaced → "Crawl_Backwards". That's fine. Just verify all VAT filenames look correct after bake.

---

## Testing checklist (visual, in-browser)

After all tasks land, smoke-test:
- [ ] Default human + idle: looks like before
- [ ] Spider preset: 8 limbs visible, crawling smoothly
- [ ] Dragon preset: wings extended, quadruped hind, tail, snake-neck visible
- [ ] Bird preset: arms gone, wings out, idle pose
- [ ] Horse preset: 4 legs (humanoid arms + collapsed-shin legs), running crawl
- [ ] Snake preset: long neck-body, no limbs, slithering on crawling anim
- [ ] All sliders still work (cape length, hair length, tail length, spike scale, strand length)
- [ ] All cosmetic layers still work (bob/ponytail/bangs/spikes — independent toggles)
- [ ] Save/load round-trips a creature spec correctly
- [ ] Shuffle button doesn't crash

---

## File path index (for quick reference during overnight run)

| Path | Purpose |
|---|---|
| `scaffolds/engine/src/character3d/mixamo_loader.ts` | Bone defs + primitive emission for all attachments |
| `scaffolds/engine/src/character3d/raymarch_renderer.ts` | SDF shader (type 23 with tipScale already added) |
| `scaffolds/engine/demos/skeleton_demo.ts` | Loadout, UI, runtime physics, anim cycling |
| `scaffolds/engine/demos/skeleton_demo.html` | UI panel CSS, sliders |
| `scaffolds/engine/public/anim_manifest.json` | Anim list (already updated with crawl/mutant_run) |
| `scaffolds/engine/public/mixamo_*.vat` | Animation binaries |
| `scaffolds/engine/scripts/bake_dae_vat.mjs` | DAE → VAT baker (used for new anims) |

---

## Stop conditions

Stop the overnight run if:
- TypeScript fails (npx tsc --noEmit) and can't be quickly fixed — leave a TODO comment, move to next task
- Vite dev server crashes — note the error, restart, continue
- A task takes 2× longer than estimated — drop it, mark "deferred to next session", move to next task
- All 6 tasks complete — wrap with a summary commit

## Session-end deliverable

A working creature builder demo where 6 preset buttons (human / spider / dragon / bird / horse / snake) instantly transform the character. Each composes from the existing humanoid rig + anim library + the new attachments + per-bone scale overrides. Foundation for the "1 million cosmetics" vision.

---

## v1 Completion Summary

All 6 plan tasks delivered. Commit chain on `main`:

| Commit | What |
|---|---|
| `64c6d65` | Iter 1-3: wings, hind retarget, extra-limb bones + per-frame world rotation copy. 5 mixamo VATs (mutant_run, crawling, crawl_backwards, running_crawl, standing_block). Plan doc. |
| `6d4d7a2` | Iter 3-6: snake-neck rig, 6 creature presets, bone-visibility filter, snake spine compression. |
| `abd85c2` | Iter 7-8: wing flap (sin-driven Y perturbation, 4Hz/8cm tip), snake-neck idle weave (peristaltic wave, 1Hz/5cm tip). |
| `d353866` | Iter 9: bone-visibility filter scaleY fix (was hiding nothing for collapsed limbs). |
| `b44bd9d` | Iter 11: procedural extra-limb phase offset (back legs sample at frame N + numFrames/2, anti-phase gait for spider). |

**What shipped:**
- Wings: 4-bone ribbon chain per side anchored to LeftShoulder/RightShoulder, type-23 ribbon emit with `tipScale: 0.15` (feathered), per-frame Y perturbation when `wingFlap: on`.
- Hind retarget: `loadout.quadrupedHind` collapses LeftLeg/RightLeg scaleY → foot lands at knee. Combine with `crawling` / `running_crawl` anim for dog/cat silhouette.
- Extra limbs (spider): 4 phantom limbs (FL/FR/BL/BR) on Hips. Front pair copies LeftArm/RightArm rotation at current frame; back pair copies LeftUpLeg/RightUpLeg rotation at frame `N + numFrames/2` (anti-phase). World matrix at offset frame computed via CPU-only hierarchy walk.
- Snake-neck: 5-bone chain forward from Neck (4 ribbon + 1 head ellipsoid). When `snakeNeck: on`, human Head bone scale collapses to 0.05 (face hides). Idle weave perturbs world X by phase-shifted sin → peristaltic motion.
- 6 creature presets: `human` / `spider` / `dragon` / `bird` / `horse` / `snake` — one-click loadout flag + per-bone scale overrides + default anim. UI button row.
- Cosmetic layers (independent toggles): bob (4-prim ensemble), ponytail, bangs L/R, spikes top/sideL/sideR/back. Length sliders for cape/hair/tail/strand. Spike-scale slider.
- Tail (Hips-anchored 4-bone ribbon, fur palette slot 19, blendGroup 15). Loadout toggle.
- Bone visibility filter: hides primitives whose bone has scaleY < 0.1 (limb chains are Y-aligned). Bird/snake collapsed-limb prims disappear cleanly instead of leaving 1-2cm stubs.
- 5 new VAT-baked anims tonight, manifest at 25 total. Snake / spider / horse use the crawl variants for proper quadruped/serpentine motion.

**Open v2 polish items (not blocking):**
- Phase offset uses a half-cycle offset for back legs only. Could parameterize per-limb (1/4, 1/8 cycle) for more variety.
- Wing flap uses Y-only translation perturbation. A proper rotational flap (rotate WingL0/R0 around shoulder axis, propagate to children via mat4 mul) would read better at high resolutions.
- No anim selection per-creature (presets set default anim, but the user can still cycle to any of the 25). Some anims look weird on certain creatures (e.g. backflip on snake).
- Wing palette uses `cape` slot (red by default). Adding a dedicated `feather` slot would let wings recolor independently.

**Known v2 architecture wins:**
- `simulateRibbonChain` helper now backs 5 chain types (cape, HairLong, side strands, tail, snake-neck). Wings could fold in with a small adapter (chain extends radially, not vertically).
- Per-bone visibility filter is general — same mechanism would hide Spine bones for "tube" creatures, Hips for "floating" creatures, etc.
- Creature spec format (`CreatureSpec` with bone scales + loadout flags + default anim) is JSON-serializable. Save/load already round-trips loadout flags; extending to creature presets is a small addition.
