/**
 * Skeleton Demo — VAT-binary shipping path only.
 *
 *   mixamo_walking.vat  →  fetch → GPUBuffer → render
 *
 * No FBX, no JSON, no procedural. One animation source, one render path.
 * Default: chibi body parts. Press C to toggle full skeleton for
 * diagnostic view. Z toggles rest pose (zero animation).
 */

import { initGPU, Camera, FrameLoop, colorPass } from '../src'
import {
  chibiRaymarchPrimitives,
  chibiMaterial,
  extendRigWithFace,
  extendLocalMatsWithFace,
  extendRigWithAnchors,
  extendLocalMatsWithAnchors,
  extendRigWithAccessories,
  extendLocalMatsWithAccessories,
  extendRigWithHair,
  extendLocalMatsWithHair,
  extendRigWithBodyParts,
  extendLocalMatsWithBodyParts,
  DEFAULT_CAPE_PARTS,
  DEFAULT_TAIL,
  DEFAULT_WINGS,
  DEFAULT_EXTRA_LIMBS,
  DEFAULT_SNAKE_NECK,
  DEFAULT_BOB_HAIR,
  DEFAULT_LONG_HAIR,
  DEFAULT_HAIR_STRANDS,
  DEFAULT_HAIR_STRAND_L,
  DEFAULT_HAIR_STRAND_R,
  DEFAULT_SPIKE_TOP,
  DEFAULT_SPIKE_SIDE_L,
  DEFAULT_SPIKE_SIDE_R,
  DEFAULT_SPIKE_BACK,
  DEFAULT_GRENADE_BELT,
  DEFAULT_FACE,
  DEFAULT_HAIR,
  DEFAULT_BODY_PARTS,
  DEFAULT_ACCESSORIES,
  CHIBI_CENTERED_SIZE,
  CHIBI_CENTERED_OFFSET,
  CHIBI_LIMB_THICKNESS,
} from '../src/character3d/mixamo_loader'
import {
  serializeCharacterSpec,
  parseCharacterSpec,
  stringifyCharacterSpec,
  type CharacterSpecV2,
  type CharacterArchetype,
} from '../src/character3d/character_spec'
import {
  loadVATBinary,
  createRetargetComposer,
  defaultCharacterParams,
} from '../src/character3d/glb_loader'
import { createOutlinePass } from '../src/character3d/outline'
import { WARDROBE, outfitToBodyParts } from '../src/character3d/wardrobe'
import { DEFAULT_ANATOMY, BUILD_PRESETS } from '../src/character3d/anatomy'
import { DEFAULT_ATTACHMENTS, HAND_LIBRARY, FOOT_LIBRARY } from '../src/character3d/attachments'
import {
  EYE_STYLES as FACE_EYE_DATA,
  MOUTH_STYLES as FACE_MOUTH_DATA,
  resolveSlot as resolveFaceSlot,
} from '../src/character3d/face_pixels'
import { createFacePixelEditor } from '../src/character3d/face_pixel_editor'
import { mat4 } from '../src/math/vec'
import { createRaymarchRenderer, expandMirrors, type RaymarchPrimitive } from '../src/character3d/raymarch_renderer'
import { VFXSystem } from '../src/character3d/vfx_system'
import {
  createNodeParticle,
  tickNodeParticle,
  type NodeParticle,
} from '../src/character3d/node_particle'
import {
  createSecondarySpring,
  tickSpring,
  type SecondarySpring,
} from '../src/character3d/secondary'

// Canvas IS the sprite. Each mode sizes the pixel buffer to its target
// sprite dimensions; CSS scales crisp-upscaled to fill the window.
// Same orthoSize everywhere — character fills the canvas height regardless
// of pixel resolution, so you see the final sprite at 1:1 pixel density.
// Sprite cells are SQUARE — at extreme rotations (arms swinging, running
// profile) horizontal extent can exceed the narrower vertical axis, and
// classic sprite atlases use a square max cell then record per-frame
// blank-pixel margins at pack time. Each mode's square side is max(w,h)
// of its canonical non-square reference (Link 24, chibi 32, Alucard 80,
// full 256).
const SPRITE_MODES = {
  sz24:  { label: '24² Zelda LTTP / small Mario',    w: 24,  h: 24  },
  sz32:  { label: '32² large Mario',                  w: 32,  h: 32  },
  sz48:  { label: '48² Chrono Trigger / Alucard',     w: 48,  h: 48  },
  debug: { label: '128² debug / SNES full',           w: 128, h: 128 },
} as const
type SpriteMode = keyof typeof SPRITE_MODES

const CHARACTER_HEIGHT_M = 1.8   // Mixamo Y Bot standing height
const ORTHO_HALF_H = CHARACTER_HEIGHT_M / 2 + 0.1  // character fills ~85% of canvas height

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const errorEl = document.getElementById('error')!

  try {
    const gpu = await initGPU(canvas)
    const { device, format } = gpu

    let spriteMode: SpriteMode = 'sz48'
    // Preview framing: 'scene' canvases at SNES full-res (256²) and
    // centers the sprite cell in it — you see the sprite at its pixel
    // size against screen context. 'framed' canvases match the cache
    // size so all render pixels are visible.
    type PreviewMode = 'scene' | 'framed'
    let previewMode: PreviewMode = 'framed'
    const SNES_SCREEN = 256
    // Animation overflow pad: raymarch cache is CELL + 2×PAD_PX per dim
    // so jump/crouch/reach animations can extend beyond the logical
    // sprite cell boundary without clipping. Character's relative render
    // size stays pinned to the cell; the pad is just extra room around.
    // User call: "keep same relative sprite size transforms, let it
    // escape the sprite boundary constraint."
    const PAD_PX = 8
    function cacheDimsFor(mode: SpriteMode): { w: number; h: number } {
      const cfg = SPRITE_MODES[mode]
      return { w: cfg.w + 2 * PAD_PX, h: cfg.h + 2 * PAD_PX }
    }
    function canvasSizeForMode(): number {
      if (previewMode === 'scene') return SNES_SCREEN
      const c = cacheDimsFor(spriteMode)
      return c.w   // framed = cache size (sprite fills canvas, pad included)
    }
    canvas.width = canvasSizeForMode()
    canvas.height = canvasSizeForMode()

    // Camera distance from target: sqrt(3² + 2.5² + 3²) ≈ 4.9m.
    // Tight near/far around the character gives ~128 uint8 levels of depth
    // across a ~1m span vs. ~10 with near=0.1/far=50 — the extra precision
    // is what makes the depth-step outline (D key) detect interior edges.
    const camera = new Camera({
      mode: 'orthographic',
      position: [3, 2.5, 3],
      target: [0, CHARACTER_HEIGHT_M / 2, 0],
      orthoSize: ORTHO_HALF_H,
      near: 2,
      far: 8,
      controls: 'orbit',
    })
    const cleanup = camera.bindToCanvas(canvas)
    // Aspect is based on the CACHE size (what the raymarch renders into),
    // which is cell + pad per side. Camera's projection maps to cache
    // pixels; blit centers cache in the scene canvas.
    {
      const c0 = cacheDimsFor(spriteMode)
      camera.setAspect(c0.w, c0.h)
    }
    // Kill wheel zoom — orthoSize is pinned per LOD by applySpriteMode /
    // applyPreset / fitCameraToCharacter. Sprite size on screen is a
    // function of the LOD, not user interaction. Capture the event before
    // the camera's own handler runs. CSS (image-rendering: pixelated)
    // still upscales the canvas to fill the viewport, so the rendered
    // sprite reads at whatever display size the browser gives it.
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault()
      e.stopImmediatePropagation()
    }, { capture: true, passive: false })

    // Animation manifest is generated at bake time (scripts/bake_dae_vat.mjs
     // produces mixamo_<tag>.vat + .meta.json per animation; the manifest
     // builder walks public/ and emits anim_manifest.json). Fetch it at
     // runtime — no demo edits needed when new animations are added.
    let ANIM_MANIFEST: { name: string; url: string }[] = []
    try {
      const mresp = await fetch('/anim_manifest.json')
      if (mresp.ok) {
        const m = await mresp.json()
        ANIM_MANIFEST = (m.anims as { tag: string; url: string }[]).map((a) => ({ name: a.tag, url: a.url }))
      }
    } catch { /* fall through to fallback */ }
    if (ANIM_MANIFEST.length === 0) {
      // Fallback so the demo still loads if manifest isn't present.
      ANIM_MANIFEST = [{ name: 'walk', url: '/mixamo_walking.vat' }]
    }
    type AnimEntry = {
      name: string
      vat: Awaited<ReturnType<typeof loadVATBinary>>
      composer: ReturnType<typeof createRetargetComposer> | null
    }
    const animations: AnimEntry[] = []
    for (const m of ANIM_MANIFEST) {
      try {
        const vat = await loadVATBinary(device, m.url)
        if (!vat.rig) continue
        // Append face + accessory virtual joints so the same composer
        // drives them. The VAT's GPU buffer was sized for all-frames ×
        // orig-joints but the composer only writes slot 0, so extras for
        // one frame still fit. Order matters when accessories ever want
        // to attach to face joints (not today, but leaving face first
        // preserves that option).
        if (vat.isLocal && vat.localMats) {
          vat.rig = extendRigWithFace(vat.rig)
          vat.localMats = extendLocalMatsWithFace(vat.localMats, vat.numFrames, vat.numJoints)
          vat.numJoints = vat.rig.length
          // Anatomy anchors — virtual joints on the head that anatomy
          // curves (jawline / brow / cheekbones) reference as bezier
          // control points. Position-only; no primitive emission.
          vat.rig = extendRigWithAnchors(vat.rig)
          vat.localMats = extendLocalMatsWithAnchors(vat.localMats, vat.numFrames, vat.numJoints)
          vat.numJoints = vat.rig.length
          // Bob hair shipped with the engine; characters can override by
          // passing a different list. Spring-driven jiggle applied below.
          const allHair = [
            ...DEFAULT_BOB_HAIR, ...DEFAULT_LONG_HAIR, ...DEFAULT_HAIR_STRANDS,
            ...DEFAULT_SPIKE_TOP, ...DEFAULT_SPIKE_SIDE_L, ...DEFAULT_SPIKE_SIDE_R, ...DEFAULT_SPIKE_BACK,
          ]
          vat.rig = extendRigWithHair(vat.rig, allHair)
          vat.localMats = extendLocalMatsWithHair(vat.localMats, vat.numFrames, vat.numJoints, allHair)
          vat.numJoints = vat.rig.length
          // Body parts + cape + grenades all share the BodyPart shape.
          // Cape gets node-particle chain motion; grenades get per-grenade
          // springs (jiggle on running); body parts (breasts/hippads) stay
          // rest-pose unless they get their own springs in a future tick.
          // Extend the rig with EVERY outfit's bones, not just knight.
          // The loadout panel can then swap outfits at runtime by toggling
          // which subset emits primitives — no rig regen needed. Each
          // outfit uses unique bone-name prefixes (WP_Mage_, WP_Light_,
          // etc.) so there are no name collisions.
          const allWardrobeParts = Object.values(WARDROBE)
            .flatMap((o) => outfitToBodyParts(o))
          const bodyAndExtras = [
            ...DEFAULT_BODY_PARTS,
            ...DEFAULT_CAPE_PARTS,
            ...DEFAULT_TAIL,
            ...DEFAULT_WINGS,
            ...DEFAULT_EXTRA_LIMBS,
            ...DEFAULT_SNAKE_NECK,
            ...DEFAULT_GRENADE_BELT,
            ...allWardrobeParts,
          ]
          vat.rig = extendRigWithBodyParts(vat.rig, bodyAndExtras)
          vat.localMats = extendLocalMatsWithBodyParts(vat.localMats, vat.numFrames, vat.numJoints, bodyAndExtras)
          vat.numJoints = vat.rig.length
          vat.rig = extendRigWithAccessories(vat.rig)
          vat.localMats = extendLocalMatsWithAccessories(vat.localMats, vat.numFrames, vat.numJoints)
          vat.numJoints = vat.rig.length
        }
        animations.push({
          name: m.name,
          vat,
          composer: vat.isLocal ? createRetargetComposer(device, vat) : null,
        })
        console.log(`Loaded ${m.name}: ${vat.numJoints} joints × ${vat.numFrames} frames, ${vat.durationSec.toFixed(2)}s`)
      } catch {
        console.log(`Skipped ${m.name} (not baked yet: ${m.url})`)
      }
    }
    if (animations.length === 0) throw new Error('No VAT animations found')
    let animIdx = 0
    let loadedVAT = animations[animIdx].vat
    let composer = animations[animIdx].composer
    const rig = loadedVAT.rig!   // rig is shared across all Mixamo anims — take from first

    // T-pose rest pose override. Bone OFFSETS alone don't define arm
    // direction (they're just lengths along local-Y for Mixamo); the
    // shoulder's LOCAL-MATRIX ROTATION is what orients the arm in world
    // space. So we need T-Pose.dae's frame-0 local matrices, NOT just
    // its bone offsets. Build a runtime-joint-indexed Float32Array
    // (numJoints × 16 floats) of local mats, defaulting to identity for
    // joints not present in the T-pose source (face/cape virtuals).
    let tposeLocalOverride: Float32Array | null = null
    try {
      const tposeVat = await loadVATBinary(device, '/mixamo_tpose.vat')
      if (tposeVat.isLocal && tposeVat.localMats && tposeVat.rig) {
        tposeLocalOverride = new Float32Array(loadedVAT.numJoints * 16)
        // Default all entries to identity.
        for (let j = 0; j < loadedVAT.numJoints; j++) {
          const o = j * 16
          tposeLocalOverride[o + 0] = 1; tposeLocalOverride[o + 5] = 1
          tposeLocalOverride[o + 10] = 1; tposeLocalOverride[o + 15] = 1
        }
        // For each runtime joint that exists by name in T-pose, copy
        // its frame-0 local mat into the runtime joint's slot.
        const tNameToIdx = new Map(tposeVat.rig.map((j, i) => [j.name, i] as const))
        let overrides = 0
        for (let j = 0; j < rig.length; j++) {
          const tIdx = tNameToIdx.get(rig[j].name)
          if (tIdx === undefined) continue
          const src = tIdx * 16
          const dst = j * 16
          for (let k = 0; k < 16; k++) tposeLocalOverride[dst + k] = tposeVat.localMats[src + k]
          overrides++
        }
        console.log(`T-pose locals: ${overrides}/${rig.length} joints overridden from /mixamo_tpose.vat`)
      }
    } catch (e) { console.warn('T-pose VAT fetch failed:', e) }

    const hipsIdx = rig.findIndex((j) => j.name === 'Hips')
    const characterParams = defaultCharacterParams(loadedVAT.numJoints)

    // --- Proportion system: group joints by body part, apply scale per group. ---
    // Groups mirror typical character-editor UI knobs. Each joint belongs to
    // exactly one group; scale propagates to its descendants via hierarchy
    // composition in the retarget composer.
    // Group regexes follow the rule: attachments inherit their parent
    // joint's group scale. So head-attached hair / helmets land in the
    // head group, arm-attached gauntlets in arms, leg-attached boots
    // in legs, etc. When the head scales 1.4×, every head-attached
    // attachment scales 1.4× too — no orphaned tiny hair on a giant
    // head, no oversized gauntlets on a chibi forearm.
    //
    // Suffix matching uses (^|_) so both bare role names (WP_Helmet,
    // legacy knight) and outfit-prefixed names (WP_Mage_Hood,
    // WP_Light_BootL) match the same role-suffix regex.
    const GROUP_PATTERNS: Record<string, RegExp> = {
      head: new RegExp(
        '^(' +
          'Head|HeadTop_End|Neck|LeftEye|RightEye|LeftPupil|RightPupil|Mouth|Nose|' +
          // Head-anchored hair: bob ensemble + ponytail + side strands.
          // All three sit on the cranium and follow head rotation +
          // head-proportion scale.
          'HairBob[A-Za-z0-9]*|HairLong[0-9]+|HairStrand[LR][0-9]+|HairSpike[0-9]+|' +
          'WP_Helmet|' +                                   // legacy knight head armor
          'WP_[A-Za-z]+_(Hood|Mask|Cap|Helmet)' +          // outfit-prefixed head armor
        ')$',
      ),
      torso: new RegExp(
        '^(' +
          'Spine|Spine1|Spine2|Hips|LeftShoulder|RightShoulder|' +
          'Cape[0-9]+|Tail[0-9]+|Grenade[LR]|' +           // body extras parented to spine/hips
          'WP_(ChestPlate|BackPlate|Belt|Pauldron[LR])|' + // legacy knight torso/shoulder armor
          'WP_[A-Za-z]+_(ChestPlate|BackPlate|Belt|Pauldron[LR]|RobeChest|RobeSkirt|Sash[LR]|LoinFront|LoinBack)' +
        ')$',
      ),
      arms: new RegExp(
        '(' +
          // Chain bones only — Hand and Weapon are terminal/attachment
          // bones whose meshes (hand sphere, weapon prop, gauntlet)
          // should keep their natural size. Chain shortening on
          // Arm/ForeArm already moves them inward; scaling the
          // attachment bones themselves squashes their hosted meshes.
          'LeftArm|RightArm|LeftForeArm|RightForeArm' +
        ')$',
      ),
      legs: new RegExp(
        '(' +
          // Chain bones only — Foot, Toe, and any boot/greave are
          // attachment bones; same rule as arms.
          'LeftUpLeg|LeftLeg|RightUpLeg|RightLeg' +
        ')$',
      ),
      // Secondary-sex-characteristic virtual joints; default slider = 0
      // so they're invisible unless a preset or slider enables them.
      bust:  /^(LeftBreast|RightBreast)$/,
      hips:  /^(LeftHipPad|RightHipPad)$/,
    }

    /** Apply a scale to every joint in a proportion group. Accepts a scalar
     *  (uniform scale) or a per-axis vec3 [sx, sy, sz]. Per-axis is the
     *  lever that produces chibi squash: legs with scale.y = 0.3 are
     *  short but keep their width, so they read as "stubby" rather than
     *  "tiny." Mixamo bone +Y is the bone's length direction, so
     *  scale.y = bone length, scale.x/z = cross-section thickness. */
    function applyGroupScale(group: keyof typeof GROUP_PATTERNS, s: number | [number, number, number]) {
      const pat = GROUP_PATTERNS[group]
      const v: [number, number, number] = typeof s === 'number' ? [s, s, s] : s
      for (let j = 0; j < rig.length; j++) {
        if (pat.test(rig[j].name)) characterParams.scales[j] = v
      }
    }

    // --- Camera auto-fit: keep the character inside the sprite cell. ---
    // Classic sprite convention (SotN, Zelda, SF2) — the cell is a MAX
    // envelope; per-frame extent varies inside it. We size the ortho cam so
    // the character's scaled rig fits with a safety margin for animation
    // (arm swing, leg lift) plus bone-cube thickness.
    //
    // Rest offsets alone are NOT world positions: Mixamo's leg/arm joints
    // have rotated local frames, so offset [0, 0.4, 0] can mean "0.4m down
    // the leg" — adding it as +Y would put the knee ABOVE the hip. We walk
    // the full local 4×4s (frame 0 of VAT) exactly like the composer so
    // bounds match what renders.
    const worldMatsTmp: Float32Array[] = Array.from({ length: rig.length }, () => new Float32Array(16))
    /** Simple rest-pose bounds — frame 0 of the first animation, current
     *  proportion scales applied. Every preset fits to its own rest pose,
     *  so the camera orthoSize adjusts to make chibi and realistic BOTH
     *  fill the cell similarly (shorter character → tighter zoom → still
     *  fills). Wild animations (backflip, defeated) may clip the frame
     *  momentarily; that's acceptable since we're not baking atlas cells. */
    function estimateBounds(): { minY: number; maxY: number; maxR: number; cx: number; cy: number; cz: number } {
      const lm = loadedVAT.localMats
      if (!lm) return { minY: 0, maxY: 1.8, maxR: 0.4, cx: 0, cy: CHARACTER_HEIGHT_M / 2, cz: 0 }
      const scaledLocal = new Float32Array(16)
      const nj = rig.length
      for (let j = 0; j < nj; j++) {
        const s = characterParams.scales[j]
        const src = j * 16
        const parent = rig[j].parent
        const isRoot = parent < 0
        for (let i = 0; i < 16; i++) scaledLocal[i] = lm[src + i]
        if (!isRoot) { scaledLocal[12] *= s[0]; scaledLocal[13] *= s[1]; scaledLocal[14] *= s[2] }
        const w = worldMatsTmp[j]
        if (isRoot) w.set(scaledLocal)
        else {
          const a = worldMatsTmp[parent]
          for (let col = 0; col < 4; col++) {
            for (let row = 0; row < 4; row++) {
              w[col * 4 + row] =
                a[row]      * scaledLocal[col * 4]     +
                a[row + 4]  * scaledLocal[col * 4 + 1] +
                a[row + 8]  * scaledLocal[col * 4 + 2] +
                a[row + 12] * scaledLocal[col * 4 + 3]
            }
          }
        }
      }
      let minY = Infinity, maxY = -Infinity, maxR = 0
      const hipsW = worldMatsTmp[hipsIdx >= 0 ? hipsIdx : 0]
      const hx = hipsW[12], hy = hipsW[13], hz = hipsW[14]
      for (let j = 0; j < nj; j++) {
        const w = worldMatsTmp[j]
        const dx = w[12] - hx, dy = w[13] - hy, dz = w[14] - hz
        if (dy < minY) minY = dy
        if (dy > maxY) maxY = dy
        const r = Math.hypot(dx, dz)
        if (r > maxR) maxR = r
      }
      return { minY, maxY, maxR, cx: hx, cy: hy, cz: hz }
    }

    function fitCameraToCharacter() {
      const b = estimateBounds()
      // Envelope is Hips-relative (minY/maxY are offsets from Hips, not
      // world positions). Margins cover primitive thickness + outline
      // ring only — no anim-safety slack needed, the envelope walks
      // every frame of every anim. Camera target = rest Hips (b.cx/cy/cz)
      // so the relative envelope centers in the frame.
      const topMargin = 0.08
      const bottomMargin = 0.08
      const radialMargin = 0.10
      const halfH = ((b.maxY + topMargin) - (b.minY - bottomMargin)) / 2
      const relCenter = ((b.maxY + topMargin) + (b.minY - bottomMargin)) / 2
      const sprite = SPRITE_MODES[spriteMode]
      const cache  = cacheDimsFor(spriteMode)
      const aspect = cache.w / cache.h
      const halfFromRadius = (b.maxR + radialMargin) / aspect
      // Cell-relative orthoSize first — character fills one cell tightly.
      const orthoSizeForCell = Math.max(halfH, halfFromRadius)
      // Scale up so the render target (cache) has pad around the cell-
      // worth of character. pxPerM stays constant (character keeps its
      // cell-sized render), extra cache pixels are animation overflow.
      camera.orthoSize = orthoSizeForCell * (cache.h / sprite.h)
      camera.target = [b.cx, b.cy + relCenter, b.cz]
    }

    const propGroups: (keyof typeof GROUP_PATTERNS)[] = ['head', 'torso', 'arms', 'legs', 'bust', 'hips']
    const currentScales: Record<string, number> = { head: 1, torso: 1, arms: 1, legs: 1, bust: 0, hips: 0 }
    // Hoisted: applyPreset (defined just below) reads currentExpression,
    // and the preset-driven initial apply would hit TDZ otherwise. The
    // full applyExpression() function lives later next to its UI wiring.
    let currentExpression = 'neutral'
    // Same reason: invalidateRaymarchCache() is called from applyPreset
    // during init. The cache framebuffer itself is created much later
    // (needs device, format, vatHandle), but the version counter can
    // live up here so invalidations accumulate safely. The check against
    // raymarchCacheApplied in the render loop treats any version>0 as
    // "needs to march," which is correct on first render anyway.
    let raymarchCacheVersion = 0
    let raymarchCacheApplied = -1
    function invalidateRaymarchCache() { raymarchCacheVersion++ }

    /** Eye glyphs per LOD — nested rects: pupil (inner dark), white
     *  (outer light). All in screen-pixel units from the head center.
     *  pupil = (eyeGap, eyeYOff, pupilHalfW, pupilHalfH)
     *  white = (whiteHalfW, whiteHalfH, _, _)   — 0 halfW disables whites
     *  Tuning the ladder matches the NES → SNES → CPS → SotN era spec:
     *    24²/32²: single dot, no white (sprite too small to fit white+pupil)
     *    80²:     1×1 dot with 1-pixel white ring (SotN)
     *    256²:    3×2 pupil with 2-pixel white ring (SF-tier) */
    const EYE_PUPIL: Record<SpriteMode, [number, number, number, number]> = {
      sz24:  [1,  -0.5, 0.4, 0.5],
      sz32:  [1,  -0.5, 0.4, 1.0],
      sz48:  [2,  -1.5, 0.4, 1.0],
      debug: [10, -8.0, 1.5, 1.0],
    }
    const EYE_WHITE: Record<SpriteMode, [number, number, number, number]> = {
      // Whites off across all LODs for now — pupil dots alone read cleaner
      // than a white ring that needs careful positioning to not break the
      // silhouette. Re-enable when we have the glyph-library work to
      // stamp the proper Mario-tier white+pupil+eyebrow stack at the
      // right positions per tier.
      sz24:  [0, 0, 0, 0],
      sz32:  [0, 0, 0, 0],
      sz48:  [0, 0, 0, 0],
      debug: [0, 0, 0, 0],
    }
    /** Mouth glyphs per LOD — single horizontal rect below the eyes.
     *  (yOff, halfW, halfH) all in screen pixels. yOff > 0 = below head
     *  center. halfW controls mouth width; halfH ~ 0.4 gives 1 pixel. */
    const MOUTH_GLYPH: Record<SpriteMode, [number, number, number, number]> = {
      sz24:  [2,  0.4, 0.4, 0],   // 1-pixel dot mouth
      sz32:  [2,  0.9, 0.4, 0],   // 2-pixel horizontal mouth
      sz48:  [4,  1.4, 0.4, 0],   // 3-pixel horizontal mouth
      debug: [14, 4,   0.6, 0],   // 8×1 wide mouth (SF-tier)
    }
    const PUPIL_COLOR: [number, number, number, number] = [0.10, 0.08, 0.20, 1.0]
    const WHITE_COLOR: [number, number, number, number] = [0.95, 0.92, 0.88, 1.0]
    const MOUTH_COLOR: [number, number, number, number] = [0.55, 0.20, 0.25, 1.0]

    /** Two canonical body archetypes. 'normal' is 1:1 Mixamo proportions
     *  (adult human, all sliders at 1, secondaries off). 'chibi' is the
     *  big-head / short-limb silhouette. Sliders are gone — these two
     *  presets ARE the proportion UI now; more archetypes land as more
     *  buttons rather than continuous axes. */
    type Scale = number | [number, number, number]
    type PresetKey = 'realistic' | 'stylized' | 'chibi'
    const BODY_PRESETS: Record<PresetKey, Record<string, Scale>> = {
      // Proportion presets dial HEAD (uniform), LEGS (Y-only), and ARMS
      // (Y-only). Torso always stays at identity — squashing the torso
      // bleeds the silhouette into distortion. Arms and legs scale
      // together so chibi reads as "short limbs all around" rather than
      // a kid with long monkey arms. Y-only on arms propagates through
      // the whole arm chain (UpperArm → ForeArm → Hand) just like legs
      // (UpLeg → Leg → Foot → Toe).
      realistic: {
        head:  [1.0, 1.0, 1.0],
        torso: [1.0, 1.0, 1.0],
        arms:  [1.0, 1.0, 1.0],
        legs:  [1.0, 1.0, 1.0],
        bust: 0.0, hips: 0.0,
      },
      stylized: {
        head:  [1.15, 1.15, 1.15],
        torso: [1.0, 1.0, 1.0],
        arms:  [1.0, 0.92, 1.0],   // arms stay closer to natural —
        legs:  [1.0, 0.85, 1.0],   // a subtle squash, not "short ape"
        bust: 0.0, hips: 0.0,
      },
      chibi: {
        head:  [1.40, 1.40, 1.40],
        torso: [1.0, 1.0, 1.0],
        arms:  [1.0, 0.75, 1.0],   // arms shorten less than legs so the
        legs:  [1.0, 0.55, 1.0],   // silhouette reads kid-like, not stubby
        bust: 0.0, hips: 0.0,
      },
    }
    function applyPreset(key: PresetKey) {
      currentProportion = key
      for (let j = 0; j < rig.length; j++) {
        characterParams.scales[j] = [1, 1, 1]
      }
      const p = BODY_PRESETS[key]
      for (const g of propGroups) {
        const v = p[g]
        currentScales[g] = typeof v === 'number' ? v : v[1]
        applyGroupScale(g, v)
      }
      if (currentExpression !== 'neutral') applyExpression(currentExpression)
      // Re-apply hind retarget AFTER preset (preset clobbers per-bone scales).
      applyHindRetarget()
      fitCameraToCharacter()
      invalidateRaymarchCache()
    }

    /** Per-creature bone-scale overrides. Runs AFTER applyPreset (which
     *  resets all scales). Each override zeroes specific bones to
     *  collapse them out of the silhouette without modifying the rig.
     *  Use 0.05 (not 0) to avoid degenerate columns in worldToLocal.
     *
     *  - quadrupedHind: zero shin scaleY → foot lands at knee.
     *  - snakeNeck: zero Head + Neck scaleY → human head hides; the
     *    snake-neck chain (parented to Neck) extends forward as the
     *    new head/face.
     *
     *  NOTE: applyPreset's init-time call runs before `loadout` is
     *  declared (TDZ). Guard via try/catch — first call no-ops, later
     *  calls (after loadout init) apply the overrides. */
    function applyHindRetarget() {
      let l: typeof loadout
      try { l = loadout } catch { return }
      const lLegIdx = rig.findIndex((j) => j.name === 'LeftLeg')
      const rLegIdx = rig.findIndex((j) => j.name === 'RightLeg')
      if (l.quadrupedHind) {
        if (lLegIdx >= 0) characterParams.scales[lLegIdx] = [1, 0.05, 1]
        if (rLegIdx >= 0) characterParams.scales[rLegIdx] = [1, 0.05, 1]
      }
      if (l.snakeNeck) {
        const headIdx2 = rig.findIndex((j) => j.name === 'Head')
        if (headIdx2 >= 0) characterParams.scales[headIdx2] = [0.05, 0.05, 0.05]
      }
      // When toggled OFF, applyPreset restores the original scale via
      // its full re-init pass, so no explicit "restore" needed here.
      invalidateRaymarchCache()
    }

    /** Proportion and resolution are independent axes. Same CT-class cell
     *  (48px) can hold a chibi child (Chrono Trigger) or a lean adult
     *  (Alucard) — historically both existed at 48. User picks. */
    let currentProportion: PresetKey = 'stylized'
    /** Animation frame rate per LOD tier. SNES sprites animated at 8-15
     *  fps regardless of display refresh; holding each pose for multiple
     *  render frames is both authentic pixel-art feel AND a cache win
     *  (AABBs don't change between ticks → raymarch holds, blit wins). */
    const SPRITE_MODE_ANIM_FPS: Record<SpriteMode, number> = {
      sz24:  8,    // NES/early-SNES sprite tick
      sz32:  10,   // SNES overworld feel (Chrono, Zelda)
      sz48:  12,   // mid-tier (CT battle, Alucard)
      debug: 24,   // near-film, for debug readability
    }
    applyPreset(currentProportion)
    // Proportion preset buttons — independent of resolution.
    for (const key of ['chibi', 'stylized', 'realistic'] as const) {
      const btn = document.getElementById(`preset-${key}`) as HTMLButtonElement | null
      if (btn) btn.onclick = () => applyPreset(key)
    }

    // Cape length scalar — multiplies the per-segment drop in cape physics.
    // 1.0 = default cape length, 0.4 = stubby, 2.0 = floor-dragger.
    let capeLengthScale = 1.0
    {
      const slider = document.getElementById('cape-length') as HTMLInputElement | null
      const valLabel = document.getElementById('cape-length-val') as HTMLElement | null
      if (slider) {
        slider.oninput = () => {
          capeLengthScale = parseFloat(slider.value)
          if (valLabel) valLabel.textContent = capeLengthScale.toFixed(2)
        }
      }
    }

    // Hair length scalar — multiplies the per-segment drop in long-hair chain.
    // 1.0 = default (5 segments × HAIR_SEG_DROP), 0.4 = bobbed, 2.0+ = floor-length.
    let hairLengthScale = 1.0
    {
      const slider = document.getElementById('hair-length') as HTMLInputElement | null
      const valLabel = document.getElementById('hair-length-val') as HTMLElement | null
      if (slider) {
        slider.oninput = () => {
          hairLengthScale = parseFloat(slider.value)
          if (valLabel) valLabel.textContent = hairLengthScale.toFixed(2)
        }
      }
    }

    // Tail length scalar — multiplies the per-segment drop in tail chain.
    // 1.0 = default (4 segments × TAIL_SEG_DROP ~32cm), 0.5 = stub, 2.5 = drag.
    let tailLengthScale = 1.0
    {
      const slider = document.getElementById('tail-length') as HTMLInputElement | null
      const valLabel = document.getElementById('tail-length-val') as HTMLElement | null
      if (slider) {
        slider.oninput = () => {
          tailLengthScale = parseFloat(slider.value)
          if (valLabel) valLabel.textContent = tailLengthScale.toFixed(2)
        }
      }
    }

    // Strand length scalar — multiplies STRAND_SEG_DROP for both side
    // strand chains. 1.0 = default (3 segments × 0.13m = ~39cm), 0.4 =
    // chin-length, 2.0+ = waist-length.
    let strandLengthScale = 1.0
    {
      const slider = document.getElementById('strand-length') as HTMLInputElement | null
      const valLabel = document.getElementById('strand-length-val') as HTMLElement | null
      if (slider) {
        slider.oninput = () => {
          strandLengthScale = parseFloat(slider.value)
          if (valLabel) valLabel.textContent = strandLengthScale.toFixed(2)
        }
      }
    }

    // Spike scale slider — uniform-scales every HairSpike* bone via the
    // proportion-style characterParams.scales[boneIdx]. The cone SDF
    // primitive's worldToLocal undoes bone scale, so a 1.5× bone scale
    // results in a 1.5× visible cone (without changing the cone's anchor
    // position on the head).
    let spikeScale = 1.0
    {
      const slider = document.getElementById('spike-scale') as HTMLInputElement | null
      const valLabel = document.getElementById('spike-scale-val') as HTMLElement | null
      const SPIKE_BONE_RE = /^HairSpike/
      const applySpikeScale = () => {
        for (let j = 0; j < rig.length; j++) {
          if (SPIKE_BONE_RE.test(rig[j].name)) {
            characterParams.scales[j] = [spikeScale, spikeScale, spikeScale]
          }
        }
        invalidateRaymarchCache()
      }
      if (slider) {
        slider.oninput = () => {
          spikeScale = parseFloat(slider.value)
          if (valLabel) valLabel.textContent = spikeScale.toFixed(2)
          applySpikeScale()
        }
      }
      applySpikeScale()   // initialize at 1.0 (no-op but lays the bones down right)
    }

    let vatHandle = {
      buffer: loadedVAT.buffer,
      numInstances: loadedVAT.numJoints,
      numFrames: loadedVAT.numFrames,
    }
    let elapsed = 0   // hoisted so switchAnimation can reset it
    // Track last sprite-anim tick for secondary motion (cape, springs):
    // they should update on the same cadence as the body animation, not
    // every render frame. Otherwise cape glides smoothly at 60Hz while
    // the sprite snaps at 8-12Hz, which reads as the cape "floating"
    // across body poses instead of moving in sync.
    let lastSecondaryFrame = -1
    let capeCollisionDebugged = false
    let capeDistDebugged = false
    let capeMatDebugged = false
    let capePtDebugged = false
    let lastSecondaryElapsed = 0
    let lastSecondaryRestPose = false

    const material = chibiMaterial(rig)

    // MRT offscreen: color (flat palette), normal, depth. Recreated when
    // the sprite mode changes (canvas pixel buffer resizes per mode).
    const SCENE_FORMAT: GPUTextureFormat = 'rgba8unorm'
    const targets = {
      sceneTex: null as GPUTexture | null,
      normalTex: null as GPUTexture | null,
      depthVizTex: null as GPUTexture | null,
      sceneDepth: null as GPUTexture | null,
      sceneView: null as GPUTextureView | null,
      normalView: null as GPUTextureView | null,
      depthVizView: null as GPUTextureView | null,
      sceneDepthView: null as GPUTextureView | null,
    }
    function makeTarget(label: string, w: number, h: number): GPUTexture {
      return device.createTexture({
        label,
        size: { width: w, height: h },
        format: SCENE_FORMAT,
        usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
      })
    }
    function recreateTargets(w: number, h: number) {
      targets.sceneTex?.destroy()
      targets.normalTex?.destroy()
      targets.depthVizTex?.destroy()
      targets.sceneDepth?.destroy()
      targets.sceneTex = makeTarget('scene-color', w, h)
      targets.normalTex = makeTarget('scene-normal', w, h)
      targets.depthVizTex = makeTarget('scene-depth-viz', w, h)
      targets.sceneDepth = device.createTexture({
        label: 'scene-depth-stencil',
        size: { width: w, height: h },
        format: 'depth24plus-stencil8',
        usage: GPUTextureUsage.RENDER_ATTACHMENT,
      })
      targets.sceneView = targets.sceneTex.createView()
      targets.normalView = targets.normalTex.createView()
      targets.depthVizView = targets.depthVizTex.createView()
      targets.sceneDepthView = targets.sceneDepth.createView()
    }
    recreateTargets(canvas.width, canvas.height)

    // --- Palette controls: one color picker per named slot. Edits hit
    // raymarch.setPaletteSlot() which writeBuffers the palette LUT — next
    // rendered frame reflects the new color, no pipeline rebind needed.
    // This is the LUT-palette-indirection doctrine's payoff: recolor
    // every joint bound to a slot instantly. ---
    function rgb01ToHex(r: number, g: number, b: number): string {
      const to255 = (x: number) => Math.max(0, Math.min(255, Math.round(x * 255)))
      return '#' + [r, g, b].map((c) => to255(c).toString(16).padStart(2, '0')).join('')
    }
    function hexToRgb01(hex: string): [number, number, number] {
      const h = hex.replace('#', '')
      return [
        parseInt(h.slice(0, 2), 16) / 255,
        parseInt(h.slice(2, 4), 16) / 255,
        parseInt(h.slice(4, 6), 16) / 255,
      ]
    }
    const paletteListEl = document.getElementById('palette-list')!
    // Per-slot pattern overrides set via UI controls. When set for a
    // slot, overrides per-primitive colorFunc / slotB / colorExtent
    // for primitives in that slot. PBR (metalness/roughness/AO) was
    // dumped — characters use only the tinted ambient + key + fill
    // light setup until those foundational lights are dialed in.
    type PatternOverride = { colorFunc?: number; paletteSlotB?: number; colorExtent?: number }
    const patternOverrides: Record<number, PatternOverride> = {}
    function applyOverridesToPrims() {
      for (const p of faceRaymarchPrims) {
        const pat = patternOverrides[p.paletteSlot]
        if (pat) {
          if (pat.colorFunc    !== undefined) p.colorFunc    = pat.colorFunc as 0 | 1 | 2 | 3
          if (pat.paletteSlotB !== undefined) p.paletteSlotB = pat.paletteSlotB
          if (pat.colorExtent  !== undefined) p.colorExtent  = pat.colorExtent
        }
      }
      raymarch.setPrimitives(faceRaymarchPrims)
      invalidateRaymarchCache()
    }
    function buildPaletteUI() {
      while (paletteListEl.firstChild) paletteListEl.removeChild(paletteListEl.firstChild)
      const slots = material.namedSlots
      for (const [name, slot] of Object.entries(slots)) {
        if (name === 'bg') continue   // always black; no point exposing
        const r = material.palette[slot * 4 + 0]
        const g = material.palette[slot * 4 + 1]
        const b = material.palette[slot * 4 + 2]
        const row = document.createElement('label')
        row.className = 'palette-row'
        const lbl = document.createElement('span')
        lbl.className = 'slot-lbl'
        lbl.textContent = name
        row.appendChild(lbl)
        const picker = document.createElement('input')
        picker.type = 'color'
        picker.value = rgb01ToHex(r, g, b)
        picker.oninput = () => {
          const [nr, ng, nb] = hexToRgb01(picker.value)
          material.palette[slot * 4 + 0] = nr
          material.palette[slot * 4 + 1] = ng
          material.palette[slot * 4 + 2] = nb
          raymarch.setPaletteSlot(slot, nr, ng, nb, 1)
          invalidateRaymarchCache()
        }
        row.appendChild(picker)
        // Pattern dropdown — colorFunc 0 (flat) / 4 (stripes) / 5 (dots)
        // / 6 (checker). Each preset hardcodes a sensible slotB (accent)
        // and extent so one-click applies a visible test pattern; finer
        // tuning is a follow-up. Skip for face slots that don't have
        // SDF primitives in the chibi build.
        const patternWrap = document.createElement('span')
        patternWrap.style.cssText = 'display:inline-flex;align-items:center;gap:2px;margin-left:6px;font-size:9px'
        const patLbl = document.createElement('span')
        patLbl.textContent = 'P'
        patternWrap.appendChild(patLbl)
        const patSel = document.createElement('select')
        patSel.style.cssText = 'font-size:9px;padding:0'
        const accentSlot = material.namedSlots.accent ?? 11
        const presets: Array<{ name: string; cfg: PatternOverride | null }> = [
          { name: 'flat',    cfg: { colorFunc: 0, paletteSlotB: slot, colorExtent: 0 } },
          { name: 'stripes', cfg: { colorFunc: 4, paletteSlotB: accentSlot, colorExtent: 8 } },
          { name: 'dots',    cfg: { colorFunc: 5, paletteSlotB: accentSlot, colorExtent: 0.04 } },
          { name: 'checker', cfg: { colorFunc: 6, paletteSlotB: accentSlot, colorExtent: 0.03 } },
        ]
        for (const p of presets) {
          const opt = document.createElement('option')
          opt.value = p.name
          opt.textContent = p.name
          patSel.appendChild(opt)
        }
        patSel.onchange = () => {
          const preset = presets.find((p) => p.name === patSel.value)
          if (!preset || !preset.cfg) return
          patternOverrides[slot] = preset.cfg
          applyOverridesToPrims()
        }
        patternWrap.appendChild(patSel)
        row.appendChild(patternWrap)
        paletteListEl.appendChild(row)
      }
    }
    // Initial buildPaletteUI() call deferred — needs faceRaymarchPrims +
    // raymarch (declared further down) to read PBR slider initial values
    // and push override changes to the GPU.

    // --- Expression blendshapes via per-axis scale.
    // Our composer's scales are vec3, so non-uniform axis scales on face
    // joints give us blendshape-ish control without actually morphing
    // verts. Each expression is a {jointName → [sx,sy,sz]} modifier that
    // multiplies on top of the head slider's uniform scale — a blink is
    // just "pupil Y → 0.1" while the head is still 1.8× in chibi mode.
    // Effects: blink collapses eyes + pupils in Y; smile stretches mouth
    // X and compresses Y; surprise opens mouth tall + eyes wide.
    const FACE_JOINTS_RE = /^(LeftEye|RightEye|LeftPupil|RightPupil|Mouth|Nose)$/
    const EXPRESSIONS: Record<string, Record<string, [number, number, number]>> = {
      neutral:  {},
      blink:    {
        LeftEye:    [1,    0.15, 1],
        RightEye:   [1,    0.15, 1],
        LeftPupil:  [1,    0.10, 1],
        RightPupil: [1,    0.10, 1],
      },
      smile:    {
        Mouth:      [1.40, 0.55, 1],
      },
      surprise: {
        Mouth:      [0.75, 1.80, 1],
        LeftEye:    [1.20, 1.30, 1],
        RightEye:   [1.20, 1.30, 1],
        LeftPupil:  [0.80, 1.20, 1],
        RightPupil: [0.80, 1.20, 1],
      },
      squint:   {
        LeftEye:    [1,    0.50, 1],
        RightEye:   [1,    0.50, 1],
        LeftPupil:  [1,    0.45, 1],
        RightPupil: [1,    0.45, 1],
      },
      crying:   {
        // Same closed-lid blendshape as blink; pixel stamp carries
        // the tear streams (see FACE_STYLES.crying → 'crying' eye).
        LeftEye:    [1,    0.15, 1],
        RightEye:   [1,    0.15, 1],
        LeftPupil:  [1,    0.10, 1],
        RightPupil: [1,    0.10, 1],
        Mouth:      [0.85, 0.55, 1],
      },
    }
    // currentExpression declared near the top of main() (hoisted so the
    // preset init call can read it). Defined here is the mutator + UI.
    function applyExpression(name: string) {
      currentExpression = name
      const mods = EXPRESSIONS[name] ?? {}
      const headS = currentScales.head
      for (let j = 0; j < rig.length; j++) {
        const jn = rig[j].name
        if (!FACE_JOINTS_RE.test(jn)) continue
        const mod = mods[jn] ?? [1, 1, 1]
        characterParams.scales[j] = [headS * mod[0], headS * mod[1], headS * mod[2]]
      }
      fitCameraToCharacter()
      invalidateRaymarchCache()
    }
    const expressionRowEl = document.getElementById('expression-row')!
    for (const name of Object.keys(EXPRESSIONS)) {
      const btn = document.createElement('button')
      btn.textContent = name
      btn.onclick = () => applyExpression(name)
      expressionRowEl.appendChild(btn)
    }

    // --- Character save/load: V2 CharacterSpec (see character_spec.ts).
    // Portable JSON capturing proportions, palette, AND the character's
    // face/hair/body/accessories + archetype base sizes. V1 files still
    // load (missing fields fall back to engine defaults). The baked VAT
    // + rig stay shared across characters; identity lives in this spec.
    // User-owned character files are the defense against vendor shutdown
    // (the RPM/Fuse pattern — research dict §12.7).
    const ARCHETYPE_CHIBI: CharacterArchetype = {
      centeredSizes:   CHIBI_CENTERED_SIZE,
      centeredOffsets: CHIBI_CENTERED_OFFSET,
      limbThickness:   CHIBI_LIMB_THICKNESS,
    }

    const nameInput = document.getElementById('char-name') as HTMLInputElement

    function serializeCharacter(): CharacterSpecV2 {
      const paletteEntries: Record<string, [number, number, number]> = {}
      for (const [slotName, slotIdx] of Object.entries(material.namedSlots)) {
        if (slotName === 'bg') continue
        paletteEntries[slotName] = [
          material.palette[slotIdx * 4 + 0],
          material.palette[slotIdx * 4 + 1],
          material.palette[slotIdx * 4 + 2],
        ]
      }
      // Pack the active hair geometry (driven by loadout.hair) into the
      // spec so a saved character is self-contained — even if the
      // module defaults change in a future engine version, this file
      // still re-creates the same silhouette.
      const activeHair = [
        ...(loadout.bob         ? DEFAULT_BOB_HAIR        : []),
        ...(loadout.ponytail    ? DEFAULT_LONG_HAIR       : []),
        ...(loadout.bangsL      ? DEFAULT_HAIR_STRAND_L   : []),
        ...(loadout.bangsR      ? DEFAULT_HAIR_STRAND_R   : []),
        ...(loadout.spikesTop   ? DEFAULT_SPIKE_TOP       : []),
        ...(loadout.spikesSideL ? DEFAULT_SPIKE_SIDE_L    : []),
        ...(loadout.spikesSideR ? DEFAULT_SPIKE_SIDE_R    : []),
        ...(loadout.spikesBack  ? DEFAULT_SPIKE_BACK      : []),
      ]
      // Pack the active armor outfit's pieces into bodyParts too so the
      // exported character is self-describing without needing the
      // engine to ship the same WARDROBE registry.
      const activeArmor = loadout.armor !== 'none' && WARDROBE[loadout.armor]
        ? outfitToBodyParts(WARDROBE[loadout.armor])
        : []
      return serializeCharacterSpec({
        name:        nameInput.value || 'unnamed',
        archetype:   ARCHETYPE_CHIBI,
        proportions: { ...currentScales },
        palette:     paletteEntries,
        face:        DEFAULT_FACE,
        hair:        activeHair,
        bodyParts:   [
          ...DEFAULT_BODY_PARTS,
          ...(loadout.cape     ? DEFAULT_CAPE_PARTS   : []),
          ...(loadout.tail     ? DEFAULT_TAIL         : []),
          ...(loadout.wings    ? DEFAULT_WINGS        : []),
          ...(loadout.extraLimbs ? DEFAULT_EXTRA_LIMBS : []),
          ...(loadout.snakeNeck  ? DEFAULT_SNAKE_NECK  : []),
          ...(loadout.grenades ? DEFAULT_GRENADE_BELT : []),
          ...activeArmor,
        ],
        accessories: DEFAULT_ACCESSORIES,
        // Loadout state — captured as opaque string tokens so saved
        // characters round-trip the test panel's selections (outfit,
        // hair style, cape pattern, expression).
        loadout: {
          armor:       loadout.armor,
          bob:         loadout.bob,
          ponytail:    loadout.ponytail,
          bangsL:      loadout.bangsL,
          bangsR:      loadout.bangsR,
          spikesTop:   loadout.spikesTop,
          spikesSideL: loadout.spikesSideL,
          spikesSideR: loadout.spikesSideR,
          spikesBack:  loadout.spikesBack,
          cape:        loadout.cape,
          tail:        loadout.tail,
          wings:       loadout.wings,
          wingFlap:    loadout.wingFlap,
          quadrupedHind: loadout.quadrupedHind,
          extraLimbs:    loadout.extraLimbs,
          snakeNeck:     loadout.snakeNeck,
          capePattern: loadout.capePattern,
          grenades:    loadout.grenades,
          expression:  currentExpression,
          proportion:  currentProportion,
          hands:       loadout.hands,
          feet:        loadout.feet,
          helm:        loadout.helm,
        },
        // Anatomy profile overrides — only emitted when at least one
        // entry is set, so default characters round-trip without a
        // bloated `profiles` block.
        ...((Object.keys(profiles.limbs).length > 0
             || Object.keys(profiles.anatomy).length > 0
             || Object.keys(profiles.torso).length > 0)
          ? { profiles: {
              ...(Object.keys(profiles.limbs).length   > 0 ? { limbs:   { ...profiles.limbs   } } : {}),
              ...(Object.keys(profiles.anatomy).length > 0 ? { anatomy: { ...profiles.anatomy } } : {}),
              ...(Object.keys(profiles.torso).length   > 0 ? { torso:   { ...profiles.torso   } } : {}),
            } }
          : {}),
      })
    }

    function applyCharacterSpec(spec: CharacterSpecV2) {
      nameInput.value = spec.name ?? 'unnamed'
      // Proportions: write directly into currentScales + apply per group.
      // Sliders are gone; these values live entirely in-memory now.
      for (const g of propGroups) {
        const v = spec.proportions?.[g]
        if (typeof v !== 'number') continue
        currentScales[g] = v
        applyGroupScale(g, v)
      }
      if (currentExpression !== 'neutral') applyExpression(currentExpression)
      fitCameraToCharacter()
      // Palette: set each known slot. Unknown slots ignored (forward-compat).
      for (const [slotName, slotIdx] of Object.entries(material.namedSlots)) {
        const rgb = spec.palette?.[slotName]
        if (!rgb) continue
        material.palette[slotIdx * 4 + 0] = rgb[0]
        material.palette[slotIdx * 4 + 1] = rgb[1]
        material.palette[slotIdx * 4 + 2] = rgb[2]
        raymarch.setPaletteSlot(slotIdx, rgb[0], rgb[1], rgb[2], 1)
      }
      invalidateRaymarchCache()
      buildPaletteUI()   // refresh color-picker swatches
      // V2 also carries face/hair/body/accessories arrays. Runtime rig-
      // extend hasn't been re-pluggable to consume them yet (next tick) —
      // log a note so the user knows the data parsed but is inert.
      const nonEmpty = spec.face.length + spec.hair.length + spec.bodyParts.length + spec.accessories.length
      if (nonEmpty > 0) {
        console.info(`[spec] ${spec.name}: ${spec.face.length} face / ${spec.hair.length} hair / ${spec.bodyParts.length} body / ${spec.accessories.length} accessories parsed (runtime override pending)`)
      }
      // Loadout — apply only those fields that match known enums; ignore
      // unknowns so older specs don't crash newer engines and v.v.
      if (spec.loadout) {
        const lo = spec.loadout
        if (typeof lo.armor === 'string' && (lo.armor === 'none' || lo.armor in WARDROBE)) {
          loadout.armor = lo.armor as typeof loadout.armor
        }
        // Hair: prefer the new per-layer booleans; fall back to legacy
        // 'hair' string mapping for older saved files.
        if (typeof lo.bob === 'boolean')         loadout.bob = lo.bob
        if (typeof lo.ponytail === 'boolean')    loadout.ponytail = lo.ponytail
        if (typeof lo.bangsL === 'boolean')      loadout.bangsL = lo.bangsL
        if (typeof lo.bangsR === 'boolean')      loadout.bangsR = lo.bangsR
        if (typeof lo.spikesTop === 'boolean')   loadout.spikesTop = lo.spikesTop
        if (typeof lo.spikesSideL === 'boolean') loadout.spikesSideL = lo.spikesSideL
        if (typeof lo.spikesSideR === 'boolean') loadout.spikesSideR = lo.spikesSideR
        if (typeof lo.spikesBack === 'boolean')  loadout.spikesBack = lo.spikesBack
        // Legacy compat — single 'bangs' / 'spikes' booleans light both sides
        // (bangs) or just the top set (spikes).
        if (typeof lo.bangs === 'boolean')       { loadout.bangsL = lo.bangs; loadout.bangsR = lo.bangs }
        if (typeof lo.spikes === 'boolean')      loadout.spikesTop = lo.spikes
        if (typeof lo.hair === 'string' &&
            ['none','bob','long','strands','bob+strands','long+strands'].includes(lo.hair) &&
            typeof lo.bob !== 'boolean' && typeof lo.ponytail !== 'boolean' && typeof lo.bangsL !== 'boolean' && typeof lo.bangsR !== 'boolean') {
          loadout.bob      = lo.hair === 'bob'  || lo.hair === 'bob+strands'
          loadout.ponytail = lo.hair === 'long' || lo.hair === 'long+strands'
          const bangsOn    = lo.hair === 'strands' || lo.hair === 'bob+strands' || lo.hair === 'long+strands'
          loadout.bangsL = bangsOn; loadout.bangsR = bangsOn
        }
        if (typeof lo.cape === 'boolean')      loadout.cape = lo.cape
        if (typeof lo.tail === 'boolean')      loadout.tail = lo.tail
        if (typeof lo.wings === 'boolean')     loadout.wings = lo.wings
        if (typeof lo.wingFlap === 'boolean')  loadout.wingFlap = lo.wingFlap
        if (typeof lo.quadrupedHind === 'boolean') loadout.quadrupedHind = lo.quadrupedHind
        if (typeof lo.extraLimbs === 'boolean')    loadout.extraLimbs = lo.extraLimbs
        if (typeof lo.snakeNeck === 'boolean')     loadout.snakeNeck = lo.snakeNeck
        if (typeof lo.grenades === 'boolean')  loadout.grenades = lo.grenades
        if (typeof lo.capePattern === 'string' && lo.capePattern in CAPE_PATTERNS) {
          loadout.capePattern = lo.capePattern as typeof loadout.capePattern
        }
        if (typeof lo.expression === 'string' && lo.expression in EXPRESSIONS) {
          applyExpression(lo.expression)
        }
        if (typeof lo.proportion === 'string' &&
            (lo.proportion === 'chibi' || lo.proportion === 'stylized' || lo.proportion === 'realistic')) {
          applyPreset(lo.proportion)
        }
        if (typeof lo.hands === 'string' && lo.hands in HAND_LIBRARY) {
          loadout.hands = lo.hands
        }
        if (typeof lo.feet === 'string' && lo.feet in FOOT_LIBRARY) {
          loadout.feet = lo.feet
        }
        if (typeof lo.helm === 'string' && (HELM_STYLES as readonly string[]).includes(lo.helm)) {
          loadout.helm = lo.helm as HelmStyle
        }
        rebuildPersistentPrims()
        buildLoadoutUI()   // refresh active-button highlights
      }
      // Anatomy profile overrides — partial maps. Validate each
      // entry is a 4-element numeric tuple before storing; reject
      // malformed without crashing.
      if (spec.profiles) {
        const isProfile = (v: unknown): v is ProfileTuple =>
          Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === 'number' && Number.isFinite(n))
        const isTorso = (v: unknown): v is [number, number, number] =>
          Array.isArray(v) && v.length === 3 && v.every((n) => typeof n === 'number' && Number.isFinite(n))
        // Reset before applying so a load fully replaces prior overrides.
        for (const k of Object.keys(profiles.limbs))   delete profiles.limbs[k]
        for (const k of Object.keys(profiles.anatomy)) delete profiles.anatomy[k]
        for (const k of Object.keys(profiles.torso))   delete profiles.torso[k]
        if (spec.profiles.limbs) {
          for (const [k, v] of Object.entries(spec.profiles.limbs)) {
            if (isProfile(v)) profiles.limbs[k] = [v[0], v[1], v[2], v[3]]
          }
        }
        if (spec.profiles.anatomy) {
          for (const [k, v] of Object.entries(spec.profiles.anatomy)) {
            if (isProfile(v)) profiles.anatomy[k] = [v[0], v[1], v[2], v[3]]
          }
        }
        if (spec.profiles.torso) {
          for (const [k, v] of Object.entries(spec.profiles.torso)) {
            if (isTorso(v)) profiles.torso[k] = [v[0], v[1], v[2]]
          }
        }
        rebuildPersistentPrims()
      }
    }

    const saveBtn = document.getElementById('save-char') as HTMLButtonElement
    saveBtn.onclick = () => {
      const spec = serializeCharacter()
      const blob = new Blob([stringifyCharacterSpec(spec)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${spec.name.replace(/[^\w]+/g, '_')}.character.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    const loadBtn = document.getElementById('load-char') as HTMLButtonElement
    const loadFileInput = document.getElementById('load-char-file') as HTMLInputElement
    loadBtn.onclick = () => loadFileInput.click()
    loadFileInput.onchange = async () => {
      const f = loadFileInput.files?.[0]
      if (!f) return
      try {
        const text = await f.text()
        const spec = parseCharacterSpec(text, ARCHETYPE_CHIBI)
        applyCharacterSpec(spec)
      } catch (err) {
        console.error('character load failed:', err)
      }
      loadFileInput.value = ''   // allow re-selecting same file
    }

    const outline = createOutlinePass(
      device, format,
      targets.sceneView!, targets.normalView!, targets.depthVizView!,
      canvas.width, canvas.height,
    )

    // --- Raymarch renderer: full chibi character as SDF primitives.
    const rightHandIdx = rig.findIndex((j) => j.name === 'RightHand')
    const headIdx = rig.findIndex((j) => j.name === 'Head')
    const spine2Idx = rig.findIndex((j) => j.name === 'Spine2')
    const spine1Idx = rig.findIndex((j) => j.name === 'Spine1')
    const lShoulderIdx = rig.findIndex((j) => j.name === 'LeftShoulder')
    const rShoulderIdx = rig.findIndex((j) => j.name === 'RightShoulder')
    const lFootIdx = rig.findIndex((j) => j.name === 'LeftFoot')
    const rFootIdx = rig.findIndex((j) => j.name === 'RightFoot')

    // Procedural extra-limb mapping: 4 phantom limbs that copy world
    // rotation from human limb chains. (sourceUp, sourceLow, dstUp,
    // dstLow, dstTip, lowOffsetY, tipOffsetY) — last two are bind-pose
    // offsets matching DEFAULT_EXTRA_LIMBS_*. Indices cached once.
    const EXTRA_LIMB_PAIRS: Array<{
      srcUpIdx: number; srcLowIdx: number;
      dstUpIdx: number; dstLowIdx: number; dstTipIdx: number;
      lowOffY: number; tipOffY: number;
      // Phase offset as a fraction 0..1 of the animation cycle. 0 = use
      // current frame (in sync with source); 0.5 = half-cycle delay
      // (anti-phase). Wave gait would be (0, 0.25, 0.5, 0.75); trot
      // (diagonal pairs) is (0, 0.5, 0.5, 0) — FL+BR vs FR+BL.
      phaseOffset: number
    }> = []
    // Default: trot gait — diagonal pairs (FL+BR, FR+BL) move together.
    // Reads as a natural alternating quadruped/spider walk on most anims
    // including cycle-driven crawls.
    for (const cfg of [
      { srcUp: 'LeftArm',     srcLow: 'LeftForeArm',  side: 'FL', phase: 0    },
      { srcUp: 'RightArm',    srcLow: 'RightForeArm', side: 'FR', phase: 0.5  },
      { srcUp: 'LeftUpLeg',   srcLow: 'LeftLeg',      side: 'BL', phase: 0.5  },
      { srcUp: 'RightUpLeg',  srcLow: 'RightLeg',     side: 'BR', phase: 0    },
    ]) {
      const srcUpIdx  = rig.findIndex((j) => j.name === cfg.srcUp)
      const srcLowIdx = rig.findIndex((j) => j.name === cfg.srcLow)
      const dstUpIdx  = rig.findIndex((j) => j.name === `Extra${cfg.side}_Up`)
      const dstLowIdx = rig.findIndex((j) => j.name === `Extra${cfg.side}_Low`)
      const dstTipIdx = rig.findIndex((j) => j.name === `Extra${cfg.side}_Tip`)
      if (srcUpIdx < 0 || srcLowIdx < 0 || dstUpIdx < 0 || dstLowIdx < 0 || dstTipIdx < 0) continue
      EXTRA_LIMB_PAIRS.push({
        srcUpIdx, srcLowIdx, dstUpIdx, dstLowIdx, dstTipIdx,
        lowOffY: -0.18, tipOffY: -0.16,
        phaseOffset: cfg.phase,
      })
    }
    // Snake-neck idle weave — perturb each chain bone's world X position
    // with a sin wave + per-bone phase offset, producing a peristaltic
    // wave along the snake body. Tip weaves more than root.
    const SNAKE_WEAVE_BONES: { idx: number; t: number; phase: number }[] = []
    {
      const names = ['SnakeNeck0', 'SnakeNeck1', 'SnakeNeck2', 'SnakeNeck3', 'SnakeNeckHead']
      for (let i = 0; i < names.length; i++) {
        const idx = rig.findIndex((j) => j.name === names[i])
        if (idx >= 0) SNAKE_WEAVE_BONES.push({ idx, t: i / (names.length - 1), phase: i * 0.6 })
      }
    }
    const applySnakeNeckWeave = () => {
      if (!composer || SNAKE_WEAVE_BONES.length === 0) return
      const wm = composer.worldMatrices
      // ~1.2Hz weave, ~5cm peak amplitude at the tip. Phase shift along
      // chain creates a wave that travels from root to tip.
      const baseT = elapsed * 2.0
      for (const b of SNAKE_WEAVE_BONES) {
        const offset = Math.sin(baseT + b.phase) * 0.05 * b.t
        wm[b.idx * 16 + 12] += offset    // perturb world X (side-to-side)
        device.queue.writeBuffer(vatHandle.buffer, b.idx * 64, wm.buffer, wm.byteOffset + b.idx * 16 * 4, 64)
      }
      invalidateRaymarchCache()
    }

    // Wing-flap bone indices — cached once. WingL1/L2/L3 + WingR1/R2/R3
    // (skip the L0/R0 ROOT bones; root stays anchored to the shoulder
    // bind-pose). The perturbation amplitude scales linearly with chain
    // position, so the tip flaps farther than the mid bone.
    // Wing chain bone indices, full chain per side (root + 3 children).
    // Root rotates around its bone-X axis by sin-driven flap angle;
    // children's world matrices recompose via parent × child.local each
    // frame. Reads better than the prior Y-translation hack because
    // the cross-section frame rotates WITH the bend (cols 0/1/2 update
    // through the chain) instead of staying at bind-pose orientation.
    const WING_CHAIN_L: number[] = []
    const WING_CHAIN_R: number[] = []
    for (let i = 0; i < 4; i++) {
      const lIdx = rig.findIndex((j) => j.name === `WingL${i}`)
      const rIdx = rig.findIndex((j) => j.name === `WingR${i}`)
      if (lIdx >= 0) WING_CHAIN_L.push(lIdx)
      if (rIdx >= 0) WING_CHAIN_R.push(rIdx)
    }
    // child.world = parent.world × child.local (composition path mirroring
    // composer.update — rot cols unchanged, col3 × scale).
    const propagateChildMat = (parentOff: number, childOff: number, localOff: number, scale: [number, number, number]): void => {
      const wm = composer!.worldMatrices
      const lm = loadedVAT.localMats!
      const c00 = lm[localOff + 0],  c01 = lm[localOff + 4],  c02 = lm[localOff + 8]
      const c10 = lm[localOff + 1],  c11 = lm[localOff + 5],  c12 = lm[localOff + 9]
      const c20 = lm[localOff + 2],  c21 = lm[localOff + 6],  c22 = lm[localOff + 10]
      const t0 = lm[localOff + 12] * scale[0]
      const t1 = lm[localOff + 13] * scale[1]
      const t2 = lm[localOff + 14] * scale[2]
      const p00 = wm[parentOff + 0],  p01 = wm[parentOff + 4],  p02 = wm[parentOff + 8]
      const p10 = wm[parentOff + 1],  p11 = wm[parentOff + 5],  p12 = wm[parentOff + 9]
      const p20 = wm[parentOff + 2],  p21 = wm[parentOff + 6],  p22 = wm[parentOff + 10]
      const p03 = wm[parentOff + 12], p13 = wm[parentOff + 13], p23 = wm[parentOff + 14]
      wm[childOff + 0]  = p00 * c00 + p01 * c10 + p02 * c20
      wm[childOff + 1]  = p10 * c00 + p11 * c10 + p12 * c20
      wm[childOff + 2]  = p20 * c00 + p21 * c10 + p22 * c20
      wm[childOff + 3]  = 0
      wm[childOff + 4]  = p00 * c01 + p01 * c11 + p02 * c21
      wm[childOff + 5]  = p10 * c01 + p11 * c11 + p12 * c21
      wm[childOff + 6]  = p20 * c01 + p21 * c11 + p22 * c21
      wm[childOff + 7]  = 0
      wm[childOff + 8]  = p00 * c02 + p01 * c12 + p02 * c22
      wm[childOff + 9]  = p10 * c02 + p11 * c12 + p12 * c22
      wm[childOff + 10] = p20 * c02 + p21 * c12 + p22 * c22
      wm[childOff + 11] = 0
      wm[childOff + 12] = p00 * t0 + p01 * t1 + p02 * t2 + p03
      wm[childOff + 13] = p10 * t0 + p11 * t1 + p12 * t2 + p13
      wm[childOff + 14] = p20 * t0 + p21 * t1 + p22 * t2 + p23
      wm[childOff + 15] = 1
    }
    const applyWingFlap = () => {
      if (!composer || !loadedVAT.localMats) return
      if (WING_CHAIN_L.length < 1 && WING_CHAIN_R.length < 1) return
      const wm = composer.worldMatrices
      const numJoints = loadedVAT.numJoints
      // Wing local matrices are time-invariant (added at extendLocalMats-
      // WithBodyParts; identity rotation + bind-pose translation per
      // frame). Sample frame 0.
      const localBase = 0
      // Flap: root rotates around its bone-X by sin angle. ~4Hz, ±0.4 rad
      // (~23°). For mirror symmetry, both wings flap the same direction
      // around their respective bone-local X axes — visually mirrored.
      const flapAngle = Math.sin(elapsed * 4) * 0.4
      const c = Math.cos(flapAngle), s = Math.sin(flapAngle)
      for (const chain of [WING_CHAIN_L, WING_CHAIN_R]) {
        if (chain.length < 1) continue
        const rootOff = chain[0] * 16
        // world × R_x(angle) — leaves col0 untouched, mixes col1+col2.
        const c10 = wm[rootOff + 4], c11 = wm[rootOff + 5], c12 = wm[rootOff + 6]
        const c20 = wm[rootOff + 8], c21 = wm[rootOff + 9], c22 = wm[rootOff + 10]
        wm[rootOff + 4]  =  c * c10 + s * c20
        wm[rootOff + 5]  =  c * c11 + s * c21
        wm[rootOff + 6]  =  c * c12 + s * c22
        wm[rootOff + 8]  = -s * c10 + c * c20
        wm[rootOff + 9]  = -s * c11 + c * c21
        wm[rootOff + 10] = -s * c12 + c * c22
        // Propagate to chain children (each child = parent × child.local)
        for (let i = 1; i < chain.length; i++) {
          const parentOff = chain[i - 1] * 16
          const childOff  = chain[i] * 16
          const childLocalOff = localBase * numJoints * 16 + chain[i] * 16
          const sChild = characterParams.scales[chain[i]] ?? [1, 1, 1]
          propagateChildMat(parentOff, childOff, childLocalOff, sChild as [number, number, number])
        }
        // Upload all chain bones
        for (const bIdx of chain) {
          device.queue.writeBuffer(vatHandle.buffer, bIdx * 64, wm.buffer, wm.byteOffset + bIdx * 16 * 4, 64)
        }
      }
      invalidateRaymarchCache()
    }
    // Phase-offset infrastructure: walk bone hierarchy at an arbitrary
    // frame to compute a source bone's world matrix without touching the
    // composer's current-frame state. Used for spider gait — back limbs
    // copy front limbs at frame N + numFrames/2 (anti-phase) so the 8
    // legs alternate instead of stepping in sync.
    const _phaseTmpA = new Float32Array(16)
    const _phaseTmpB = new Float32Array(16)
    const _phaseSrcWorld = new Float32Array(16)
    function mat4mulPh(out: Float32Array, a: Float32Array, b: Float32Array): void {
      for (let col = 0; col < 4; col++) {
        for (let row = 0; row < 4; row++) {
          out[col * 4 + row] =
            a[row]      * b[col * 4]     +
            a[row + 4]  * b[col * 4 + 1] +
            a[row + 8]  * b[col * 4 + 2] +
            a[row + 12] * b[col * 4 + 3]
        }
      }
    }
    // Pre-compute root → bone chains for each source we'll phase-offset.
    const SOURCE_BONE_CHAINS = new Map<number, number[]>()
    for (const sourceName of ['LeftArm', 'LeftForeArm', 'RightArm', 'RightForeArm',
                               'LeftUpLeg', 'LeftLeg', 'RightUpLeg', 'RightLeg']) {
      const sIdx = rig.findIndex((j) => j.name === sourceName)
      if (sIdx < 0) continue
      const chain: number[] = []
      let cur: number = sIdx
      while (cur >= 0) {
        chain.push(cur)
        cur = rig[cur].parent
      }
      chain.reverse()
      SOURCE_BONE_CHAINS.set(sIdx, chain)
    }
    function worldMatAtFrame(boneIdx: number, frame: number, dst: Float32Array): boolean {
      const chain = SOURCE_BONE_CHAINS.get(boneIdx)
      if (!chain) return false
      const localMats = loadedVAT.localMats
      if (!localMats) return false
      const numJoints = loadedVAT.numJoints
      const numFrames = loadedVAT.numFrames
      const f = ((frame % numFrames) + numFrames) % numFrames
      const base = f * numJoints * 16
      // Identity
      dst.fill(0); dst[0] = 1; dst[5] = 1; dst[10] = 1; dst[15] = 1
      // Walk root → leaf, accumulating composition matrices. Composition
      // = local with rotation cols unchanged + col3 (translation) × scale.
      // This mirrors composer.update's "no scale cascade" composition
      // path so children's world positions match.
      for (const bone of chain) {
        const localBase = base + bone * 16
        const s = characterParams.scales[bone] ?? [1, 1, 1]
        for (let i = 0; i < 12; i++) _phaseTmpA[i] = localMats[localBase + i]
        _phaseTmpA[12] = localMats[localBase + 12] * s[0]
        _phaseTmpA[13] = localMats[localBase + 13] * s[1]
        _phaseTmpA[14] = localMats[localBase + 14] * s[2]
        _phaseTmpA[15] = 1
        mat4mulPh(_phaseTmpB, dst, _phaseTmpA)
        for (let i = 0; i < 16; i++) dst[i] = _phaseTmpB[i]
      }
      // Apply leaf scale to columns (display path: composer scales col0/1/2
      // by leaf's own s for the matrix actually fed to the SDF).
      const sLeaf = characterParams.scales[boneIdx] ?? [1, 1, 1]
      dst[0] *= sLeaf[0]; dst[1] *= sLeaf[0]; dst[2] *= sLeaf[0]
      dst[4] *= sLeaf[1]; dst[5] *= sLeaf[1]; dst[6] *= sLeaf[1]
      dst[8] *= sLeaf[2]; dst[9] *= sLeaf[2]; dst[10] *= sLeaf[2]
      return true
    }
    const applyExtraLimbsCopy = (frameIdx: number) => {
      if (!composer) return
      const wm = composer.worldMatrices
      const numFrames = loadedVAT.numFrames
      for (const p of EXTRA_LIMB_PAIRS) {
        const su = p.srcUpIdx * 16, sl = p.srcLowIdx * 16
        const du = p.dstUpIdx * 16, dl = p.dstLowIdx * 16, dt = p.dstTipIdx * 16
        // Per-limb phase offset: phase 0 → use current frame (in sync with
        // source, no hierarchy walk needed). phase > 0 → sample source at
        // frameIdx + numFrames × phase for that limb's gait position.
        const offsetFrame = frameIdx + Math.floor(numFrames * p.phaseOffset)
        const usePhaseOffset = p.phaseOffset > 0.001
        let r0_0, r0_1, r0_2, r1_0, r1_1, r1_2, r2_0, r2_1, r2_2: number
        let l0_0, l0_1, l0_2, l1_0, l1_1, l1_2, l2_0, l2_1, l2_2: number
        if (usePhaseOffset && worldMatAtFrame(p.srcUpIdx, offsetFrame, _phaseSrcWorld)) {
          r0_0 = _phaseSrcWorld[0]; r0_1 = _phaseSrcWorld[1]; r0_2 = _phaseSrcWorld[2]
          r1_0 = _phaseSrcWorld[4]; r1_1 = _phaseSrcWorld[5]; r1_2 = _phaseSrcWorld[6]
          r2_0 = _phaseSrcWorld[8]; r2_1 = _phaseSrcWorld[9]; r2_2 = _phaseSrcWorld[10]
        } else {
          r0_0 = wm[su + 0]; r0_1 = wm[su + 1]; r0_2 = wm[su + 2]
          r1_0 = wm[su + 4]; r1_1 = wm[su + 5]; r1_2 = wm[su + 6]
          r2_0 = wm[su + 8]; r2_1 = wm[su + 9]; r2_2 = wm[su + 10]
        }
        if (usePhaseOffset && worldMatAtFrame(p.srcLowIdx, offsetFrame, _phaseSrcWorld)) {
          l0_0 = _phaseSrcWorld[0]; l0_1 = _phaseSrcWorld[1]; l0_2 = _phaseSrcWorld[2]
          l1_0 = _phaseSrcWorld[4]; l1_1 = _phaseSrcWorld[5]; l1_2 = _phaseSrcWorld[6]
          l2_0 = _phaseSrcWorld[8]; l2_1 = _phaseSrcWorld[9]; l2_2 = _phaseSrcWorld[10]
        } else {
          l0_0 = wm[sl + 0]; l0_1 = wm[sl + 1]; l0_2 = wm[sl + 2]
          l1_0 = wm[sl + 4]; l1_1 = wm[sl + 5]; l1_2 = wm[sl + 6]
          l2_0 = wm[sl + 8]; l2_1 = wm[sl + 9]; l2_2 = wm[sl + 10]
        }
        // Write to dst Up bone — translation untouched (composer set it).
        wm[du + 0] = r0_0; wm[du + 1] = r0_1; wm[du + 2] = r0_2
        wm[du + 4] = r1_0; wm[du + 5] = r1_1; wm[du + 6] = r1_2
        wm[du + 8] = r2_0; wm[du + 9] = r2_1; wm[du + 10] = r2_2
        // dst Low rotation
        wm[dl + 0] = l0_0; wm[dl + 1] = l0_1; wm[dl + 2] = l0_2
        wm[dl + 4] = l1_0; wm[dl + 5] = l1_1; wm[dl + 6] = l1_2
        wm[dl + 8] = l2_0; wm[dl + 9] = l2_1; wm[dl + 10] = l2_2
        // Recompute Low's translation: dst Up's translation + Up's Y axis × lowOffY.
        const upY0 = wm[du + 4], upY1 = wm[du + 5], upY2 = wm[du + 6]
        wm[dl + 12] = wm[du + 12] + upY0 * p.lowOffY
        wm[dl + 13] = wm[du + 13] + upY1 * p.lowOffY
        wm[dl + 14] = wm[du + 14] + upY2 * p.lowOffY
        wm[dl + 15] = 1
        // Tip: rotation = Low's, translation = Low + Low.Y axis × tipOffY.
        wm[dt + 0] = wm[dl + 0]; wm[dt + 1] = wm[dl + 1]; wm[dt + 2] = wm[dl + 2]
        wm[dt + 4] = wm[dl + 4]; wm[dt + 5] = wm[dl + 5]; wm[dt + 6] = wm[dl + 6]
        wm[dt + 8] = wm[dl + 8]; wm[dt + 9] = wm[dl + 9]; wm[dt + 10] = wm[dl + 10]
        const lwY0 = wm[dl + 4], lwY1 = wm[dl + 5], lwY2 = wm[dl + 6]
        wm[dt + 12] = wm[dl + 12] + lwY0 * p.tipOffY
        wm[dt + 13] = wm[dl + 13] + lwY1 * p.tipOffY
        wm[dt + 14] = wm[dl + 14] + lwY2 * p.tipOffY
        wm[dt + 15] = 1
        // Upload the 3 modified bones to the VAT.
        device.queue.writeBuffer(vatHandle.buffer, p.dstUpIdx  * 64, wm.buffer, wm.byteOffset + p.dstUpIdx  * 16 * 4, 64)
        device.queue.writeBuffer(vatHandle.buffer, p.dstLowIdx * 64, wm.buffer, wm.byteOffset + p.dstLowIdx * 16 * 4, 64)
        device.queue.writeBuffer(vatHandle.buffer, p.dstTipIdx * 64, wm.buffer, wm.byteOffset + p.dstTipIdx * 16 * 4, 64)
      }
      invalidateRaymarchCache()
    }
    // 5-segment cape over 6 bones (Cape0..Cape5).
    const capeBoneIndices: number[] = []
    for (let i = 0; i < 6; i++) {
      const idx = rig.findIndex((j) => j.name === `Cape${i}`)
      if (idx >= 0) capeBoneIndices.push(idx)
    }
    const CAPE_SEG_DROP = 0.1854   // matches DEFAULT_CAPE_PARTS spacing (+3%)
    const CAPE_HAS_FULL_CHAIN = capeBoneIndices.length === 6 && spine2Idx >= 0

    // Particle 0 is the LOCKED anchor at the shoulder (Spine2 + rotated
    // offset). Particles 1..4 chain via node-particle physics (one-frame-
    // stale parent reads + distance clamp). The first VISIBLE segment
    // spans particle[0] → particle[1] hanging DOWN from the shoulder
    // anchor, eliminating the awkward up-bend the previous architecture
    // had between Spine2 and Cape0.
    const capeChain: NodeParticle[] = !CAPE_HAS_FULL_CHAIN ? [] : [
      // Cape0 — locked anchor (read from Cape0 bone matrix, which is
      // Spine2 × bind-pose offset, every tick).
      createNodeParticle({
        parentRef: spine2Idx, parentKind: 'bone',
        restOffset: [0, 0.10, -0.20],
        restLength: 0.22,
      }),
      // Cape1..Cape5 — chain physics, hanging straight down from previous.
      createNodeParticle({ parentRef: 0, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 1, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 2, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 3, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 4, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
    ]

    // 5-segment long hair: HairLong0 (locked to back of head) → HairLong4
    // (tip). Cape architecture port — same locked-root + node-particle
    // chain. restOffset / restLength values match DEFAULT_LONG_HAIR so the
    // bind-pose chain geometry equals what the rig was set up with.
    const HAIR_ANCHOR_OFFSET: [number, number, number] = [0, 0.10, -0.13]   // Head → HairLong0 (upper back of cranium)
    const HAIR_SEG_DROP = 0.10                                              // Y drop per segment
    const hairBoneIndices: number[] = []
    for (let i = 0; i < 6; i++) {
      const idx = rig.findIndex((j) => j.name === `HairLong${i}`)
      if (idx >= 0) hairBoneIndices.push(idx)
    }
    const HAIR_HAS_FULL_CHAIN = hairBoneIndices.length === 6 && headIdx >= 0
    const hairChain: NodeParticle[] = !HAIR_HAS_FULL_CHAIN ? [] : [
      createNodeParticle({
        parentRef: headIdx, parentKind: 'bone',
        restOffset: HAIR_ANCHOR_OFFSET,
        restLength: Math.hypot(...HAIR_ANCHOR_OFFSET),
      }),
      createNodeParticle({ parentRef: 0, parentKind: 'particle', restOffset: [0, -HAIR_SEG_DROP, 0], restLength: HAIR_SEG_DROP }),
      createNodeParticle({ parentRef: 1, parentKind: 'particle', restOffset: [0, -HAIR_SEG_DROP, 0], restLength: HAIR_SEG_DROP }),
      createNodeParticle({ parentRef: 2, parentKind: 'particle', restOffset: [0, -HAIR_SEG_DROP, 0], restLength: HAIR_SEG_DROP }),
      createNodeParticle({ parentRef: 3, parentKind: 'particle', restOffset: [0, -HAIR_SEG_DROP, 0], restLength: HAIR_SEG_DROP }),
      createNodeParticle({ parentRef: 4, parentKind: 'particle', restOffset: [0, -HAIR_SEG_DROP, 0], restLength: HAIR_SEG_DROP }),
    ]

    // Hair strands (face-framing side bangs) — two 3-segment chains
    // anchored to Spine2 chest-front-shoulder (X=±0.10, Y=+0.10, Z=+0.13
    // local). Chain architecture mirrors HairLong: locked root particle
    // at Spine2 + offset, three more particles in chain physics with
    // rest target along world-down. Per-tick simulation runs as a sibling
    // block to the hair physics and uses the same torso SDF push.
    // Bangs anchor in HEAD-local: temple-line. Different "socket" from
    // the back hair (HairLong) which anchors at back of cranium — bangs
    // rotate around the temple, ponytail rotates around the back. Both
    // Head-parented so they share head rotation but pivot at distinct
    // positions on the cranium.
    const STRAND_ANCHOR_OFFSET_L: [number, number, number] = [-0.16, 0.15, 0.05]
    const STRAND_ANCHOR_OFFSET_R: [number, number, number] = [ 0.16, 0.15, 0.05]
    const STRAND_SEG_DROP = 0.13
    const findStrandIndices = (side: 'L' | 'R'): number[] => {
      const out: number[] = []
      for (let i = 0; i < 4; i++) {
        const idx = rig.findIndex((j) => j.name === `HairStrand${side}${i}`)
        if (idx >= 0) out.push(idx)
      }
      return out
    }
    const strandLBones = findStrandIndices('L')
    const strandRBones = findStrandIndices('R')
    const STRAND_L_FULL = strandLBones.length === 4 && headIdx >= 0
    const STRAND_R_FULL = strandRBones.length === 4 && headIdx >= 0
    const makeStrandChain = (anchor: [number, number, number]): NodeParticle[] => [
      createNodeParticle({
        parentRef: headIdx, parentKind: 'bone',
        restOffset: anchor, restLength: Math.hypot(...anchor),
      }),
      createNodeParticle({ parentRef: 0, parentKind: 'particle', restOffset: [0, -STRAND_SEG_DROP, 0], restLength: STRAND_SEG_DROP }),
      createNodeParticle({ parentRef: 1, parentKind: 'particle', restOffset: [0, -STRAND_SEG_DROP, 0], restLength: STRAND_SEG_DROP }),
      createNodeParticle({ parentRef: 2, parentKind: 'particle', restOffset: [0, -STRAND_SEG_DROP, 0], restLength: STRAND_SEG_DROP }),
    ]
    const strandLChain: NodeParticle[] = STRAND_L_FULL ? makeStrandChain(STRAND_ANCHOR_OFFSET_L) : []
    const strandRChain: NodeParticle[] = STRAND_R_FULL ? makeStrandChain(STRAND_ANCHOR_OFFSET_R) : []

    // Tail chain — Hips-anchored, 4-segment ribbon. Mirrors strand chain
    // structure but with own anchor offset + slightly tighter segDrop.
    // Only simulated when loadout.tail is on (otherwise the bones stay at
    // bind pose and no primitive is emitted).
    const TAIL_ANCHOR_OFFSET: [number, number, number] = [0, 0.00, -0.13]
    const TAIL_SEG_DROP = 0.08
    const tailBones: number[] = []
    for (let i = 0; i < 5; i++) {
      const idx = rig.findIndex((j) => j.name === `Tail${i}`)
      if (idx >= 0) tailBones.push(idx)
    }
    const TAIL_FULL = tailBones.length === 5 && hipsIdx >= 0
    const tailChain: NodeParticle[] = !TAIL_FULL ? [] : [
      createNodeParticle({
        parentRef: hipsIdx, parentKind: 'bone',
        restOffset: TAIL_ANCHOR_OFFSET, restLength: Math.hypot(...TAIL_ANCHOR_OFFSET),
      }),
      createNodeParticle({ parentRef: 0, parentKind: 'particle', restOffset: [0, -TAIL_SEG_DROP, 0], restLength: TAIL_SEG_DROP }),
      createNodeParticle({ parentRef: 1, parentKind: 'particle', restOffset: [0, -TAIL_SEG_DROP, 0], restLength: TAIL_SEG_DROP }),
      createNodeParticle({ parentRef: 2, parentKind: 'particle', restOffset: [0, -TAIL_SEG_DROP, 0], restLength: TAIL_SEG_DROP }),
      createNodeParticle({ parentRef: 3, parentKind: 'particle', restOffset: [0, -TAIL_SEG_DROP, 0], restLength: TAIL_SEG_DROP }),
    ]

    // Scratch mat4s for per-frame invViewProj computation (point lights).
    const scratchVP   = mat4.create()
    const scratchInvVP = mat4.create()

    // Spring-driven jiggle elements — bob hair (lighter, snappier) and
    // grenades on the belt (heavier, slower oscillation). Each spring's
    // restTarget is the bone's current world position from the composer
    // (i.e. wherever animation would have placed it). The spring lags
    // and overshoots; we override the bone's translation with the spring
    // position. Identity-style oscillation gives the bouncy "secondary"
    // feel without needing a chain.
    const grenadeLIdx = rig.findIndex((j) => j.name === 'GrenadeL')
    const grenadeRIdx = rig.findIndex((j) => j.name === 'GrenadeR')
    // Grenade pendulum chains — one NodeParticle per grenade, parented
    // to Hips with belt-relative rest offset. Each tick the particle
    // swings toward (Hips world position + rotated rest offset) with
    // one-frame-stale parent reads, then gets pushed out of the torso
    // SDF so it can't penetrate the hip / leg geometry. Replaces the
    // prior spring system which had no body collision.
    type GrenadeEntry = { boneIdx: number; particle: NodeParticle; restOffsetLocal: [number, number, number] }
    const grenadeEntries: GrenadeEntry[] = []
    const GRENADE_L_OFFSET: [number, number, number] = [ 0.110, -0.020, 0.090]
    const GRENADE_R_OFFSET: [number, number, number] = [-0.110, -0.020, 0.090]
    if (grenadeLIdx >= 0 && hipsIdx >= 0) {
      grenadeEntries.push({
        boneIdx: grenadeLIdx,
        particle: createNodeParticle({ parentRef: hipsIdx, parentKind: 'bone', restOffset: GRENADE_L_OFFSET, restLength: Math.hypot(...GRENADE_L_OFFSET) }),
        restOffsetLocal: GRENADE_L_OFFSET,
      })
    }
    if (grenadeRIdx >= 0 && hipsIdx >= 0) {
      grenadeEntries.push({
        boneIdx: grenadeRIdx,
        particle: createNodeParticle({ parentRef: hipsIdx, parentKind: 'bone', restOffset: GRENADE_R_OFFSET, restLength: Math.hypot(...GRENADE_R_OFFSET) }),
        restOffsetLocal: GRENADE_R_OFFSET,
      })
    }
    // Pass the SAME hair / bodyParts lists we used to extend the rig.
    // The emitter uses these to build its lookup maps; without them,
    // virtual joints (HairBob, Cape*, Grenade*) live in the rig but no
    // primitives emit for them — invisible cape + invisible hair.
    const bodyAndExtrasPrims = [
      ...DEFAULT_BODY_PARTS,
      ...DEFAULT_CAPE_PARTS,
      ...DEFAULT_TAIL,
      ...DEFAULT_WINGS,
      ...DEFAULT_EXTRA_LIMBS,
      ...DEFAULT_SNAKE_NECK,
      ...DEFAULT_GRENADE_BELT,
      ...outfitToBodyParts(WARDROBE.knight),
    ]
    const allHairPrims = [
      ...DEFAULT_BOB_HAIR, ...DEFAULT_LONG_HAIR, ...DEFAULT_HAIR_STRANDS,
      ...DEFAULT_SPIKE_TOP, ...DEFAULT_SPIKE_SIDE_L, ...DEFAULT_SPIKE_SIDE_R, ...DEFAULT_SPIKE_BACK,
    ]
    const faceRaymarchPrims: RaymarchPrimitive[] =
      chibiRaymarchPrimitives(
        rig, material,
        undefined,                 // face: stay default (empty)
        undefined,                 // accessories: stay default
        allHairPrims,
        bodyAndExtrasPrims,
      ) as RaymarchPrimitive[]
    if (rightHandIdx >= 0) {
      const baseSlot = material.namedSlots.fire_base ?? 12
      const tipSlot  = material.namedSlots.fire_tip  ?? 14
      faceRaymarchPrims.push({
        type: 7, paletteSlot: baseSlot, boneIdx: rightHandIdx,
        params: [0.05, 0.14, 0.03, 12.0],
        offsetInBone: [0, 0.18, 0],
        colorFunc: 1,
        paletteSlotB: tipSlot,
        colorExtent: 0.14,
        unlit: true,    // flame is its own glow — bypass cel shading
      })
    }
    const raymarch = createRaymarchRenderer(
      device, SCENE_FORMAT,
      faceRaymarchPrims,
      material.palette,
      vatHandle,
      { maxSteps: 64 },   // bumped from 32 to fix grazing-angle precision
                          // on the cape — thin shapes (cross-section
                          // ~9cm) return tiny SDF values when the ray
                          // skims along their length, so the marcher
                          // needs more steps to traverse a meter-long
                          // primitive at glancing angles.
    )
    // Cache is cell + pad × 2 per dimension — gives animation room.
    {
      const c0 = cacheDimsFor(spriteMode)
      raymarch.resizeCache(c0.w, c0.h)
    }

    // Build the palette / PBR UI now that faceRaymarchPrims + raymarch
    // exist (sliders read initial PBR values from prims, push updates
    // via raymarch.setPrimitives).
    buildPaletteUI()

    // Mount the face pixel editor widget. The editor takes ownership of
    // baking + uploading; on init it pushes the existing presets to the
    // GPU so visuals match the prior hardcoded shader switch. Edits in
    // the widget call onBake which re-uploads the buffer.
    const facePixelEditorEl = document.getElementById('face-pixel-editor')
    if (facePixelEditorEl) {
      createFacePixelEditor(facePixelEditorEl, (styles, pixels) => {
        outline.setFacePixelData(styles, pixels)
        invalidateRaymarchCache()
      })
    } else {
      // Fallback: bake presets directly without the editor (headless or
      // missing host element).
      const allStyles = [...FACE_EYE_DATA, ...FACE_MOUTH_DATA]
      const flat: number[] = []
      const styles = new Int32Array(16 * 4)
      const slotIdMap: Record<string, number> = {
        pupil: 0, eyewhite: 1, accent: 2, tear: 3, glow_core: 4, mouth: 5,
      }
      for (let s = 0; s < allStyles.length; s++) {
        const start = flat.length / 4
        for (const px of allStyles[s].pixels) {
          flat.push(px.dx, px.dy, slotIdMap[px.slot] ?? 0, 0)
        }
        styles[s * 4 + 0] = start
        styles[s * 4 + 1] = flat.length / 4 - start
      }
      outline.setFacePixelData(styles, new Int32Array(flat))
    }
    void resolveFaceSlot

    // Naked-man mode — override clothing/accessory slots with the skin
    // color so the silhouette reads as pure body. Lets us tune body
    // proportions per preset (chibi / stylized / realistic) without
    // clothing seams confusing the read. Toggle with K. material.palette
    // stays canonical (palette picker UI reflects true colors); we only
    // override the raymarch's palette LUT via setPaletteSlot.
    const NUDE_SLOTS = ['shirt', 'pants', 'shoes', 'hair', 'accent', 'weapon'] as const
    const nudeSnapshot: Array<[number, number, number]> = NUDE_SLOTS.map((name) => {
      const s = material.namedSlots[name]
      if (s === undefined) return [0, 0, 0]
      return [
        material.palette[s * 4 + 0],
        material.palette[s * 4 + 1],
        material.palette[s * 4 + 2],
      ]
    })
    let nudeMode = false
    function applyNudeMode() {
      const skinSlot = material.namedSlots.skin
      const sr = material.palette[skinSlot * 4 + 0]
      const sg = material.palette[skinSlot * 4 + 1]
      const sb = material.palette[skinSlot * 4 + 2]
      NUDE_SLOTS.forEach((name, i) => {
        const s = material.namedSlots[name]
        if (s === undefined) return
        if (nudeMode) {
          raymarch.setPaletteSlot(s, sr, sg, sb, 1)
        } else {
          const [r, g, b] = nudeSnapshot[i]
          raymarch.setPaletteSlot(s, r, g, b, 1)
        }
      })
      invalidateRaymarchCache()
    }
    applyNudeMode()

    // Face paint-on lives entirely in the outline shader (screen-space
    // sprite stamp). Eyes = Mario 2×3 pattern at CPU-projected anchors;
    // mouth = rect stamp. Bone-local face-mark buffer was tried and
    // abandoned: pixel-exact eye placement is the goal, so we work in
    // screen space where the grid is authoritative.

    // Cache version hoisted higher in the file — declared near top-of-main
    // so proportion-preset applies during init can fire invalidations
    // safely without TDZ.

    // --- VFX lifetime manager. Spawnable primitives (swipes, trails,
    // bursts) layer on top of the persistent character + flame primitive
    // list every frame. Space spawns a swipe + trail at the right hand;
    // press X for an impact star; press Z for a muzzle flash. All feed
    // the same raymarch renderer — no separate pipeline for VFX. ---
    const vfxSystem = new VFXSystem()
    const persistentPrims: RaymarchPrimitive[] = faceRaymarchPrims.slice()   // mutable; loadout swaps repopulate
    console.log(`Raymarch: ${persistentPrims.length} persistent primitives`)
    if (persistentPrims.length > 0) {
      console.log('  first:', persistentPrims[0])
      console.log('  last:', persistentPrims[persistentPrims.length - 1])
    }
    function currentAllPrims(now: number): RaymarchPrimitive[] {
      return persistentPrims.concat(vfxSystem.getPrimitives(now))
    }

    // ---- Loadout: which body extras + hair style emit primitives. ----
    // Bones for every group are already in the rig (extended once at init);
    // toggling loadout just changes which ones get raymarch primitives.
    // Existing data registries (DEFAULT_*, WARDROBE) are read as-is so the
    // UI doesn't fork from the canonical definitions — same pattern as the
    // face pixel editor reading EYE_STYLES / MOUTH_STYLES.
    type ArmorOutfit = 'none' | keyof typeof WARDROBE
    type HairStyle  = 'none' | 'bob'   | 'long' | 'strands' | 'bob+strands' | 'long+strands'
    // Cape patterns are colorFunc IDs in the raymarch shader. Lookup
    // table makes the UI labels stable while the IDs stay an internal
    // shader contract.
    const CAPE_PATTERNS = {
      solid:        0,
      stripes:      8,   // world-Y — tiles continuously across segments
      stripesLocal: 4,   // primitive-local Y — each segment self-centred
      chevron:      7,
      checker:      6,
      dots:         5,
    } as const
    type CapePattern = keyof typeof CAPE_PATTERNS
    type HelmStyle = 'none' | 'kettle' | 'horned' | 'pickelhaube' | 'greathelm' | 'sallet' | 'crested' | 'plumed'
    const HELM_STYLES: HelmStyle[] = ['none', 'kettle', 'horned', 'pickelhaube', 'greathelm', 'sallet', 'crested', 'plumed']
    // Isolation viewer — filters the prim list to a single category so
    // an accessory can be inspected alone in the canvas. When active,
    // animation is forced OFF (rest pose) so the piece floats statically
    // and the user can orbit-camera around it without limb motion.
    type IsolateCategory = 'none' | 'helm' | 'hands' | 'feet' | 'hair' | 'cape'
                         | 'grenades' | 'armor' | 'limbs' | 'anatomy' | 'body'
    const ISOLATE_CATEGORIES: IsolateCategory[] = [
      'none', 'helm', 'hands', 'feet', 'hair', 'cape', 'grenades',
      'armor', 'limbs', 'anatomy', 'body',
    ]
    interface Loadout {
      armor: ArmorOutfit
      // Hair layers — independent toggles. Each is its own additive layer
      // (distinct blendGroup) and can be mixed freely with the others.
      // 'hair' string is kept for legacy save/load only (mapped → booleans
      // on load, not authored anymore).
      hair:  HairStyle
      bob:        boolean
      ponytail:   boolean
      bangsL:     boolean
      bangsR:     boolean
      spikesTop:  boolean
      spikesSideL: boolean
      spikesSideR: boolean
      spikesBack: boolean
      cape: boolean
      tail: boolean
      wings: boolean
      wingFlap: boolean   // sin-driven up/down flap on wing chain bones
      grenades: boolean
      // Per-bone scale override: zero out shin scaleY so the foot lands
      // where the knee was → quadruped silhouette using humanoid rig.
      // Combine with `crawling` or `running_crawl` anim for dog/cat look.
      quadrupedHind: boolean
      // Procedural extra limbs (4 phantom legs on Hips) for spider /
      // insect silhouettes. Per-frame transform copy from the human
      // limbs makes them animate in sync.
      extraLimbs: boolean
      // Snake-neck rig: replaces the human Head with a chain extending
      // forward from Neck, tipped with a snake-head ellipsoid. When on,
      // the Head bone gets scale-collapsed so the human face hides.
      snakeNeck: boolean
      capePattern: CapePattern
      hands: string   // key into HAND_LIBRARY
      feet:  string   // key into FOOT_LIBRARY
      helm:  HelmStyle   // SUP + CHAMFER + mirrorYZ helmet (Tier-1 demo)
      isolate: IsolateCategory   // accessory inspector — filter to one category
    }
    const loadout: Loadout = {
      armor: 'knight',
      hair: 'bob',
      bob:         true,
      ponytail:    false,
      bangsL:      false,
      bangsR:      false,
      spikesTop:   false,
      spikesSideL: false,
      spikesSideR: false,
      spikesBack:  false,
      cape: true,
      tail: false,
      wings: false,
      wingFlap: true,    // default on so when wings turn on they animate
      grenades: true,
      quadrupedHind: false,
      extraLimbs: false,
      snakeNeck: false,
      capePattern: 'stripes',
      hands: 'skin',
      feet:  'shoe',
      helm:  'none',
      isolate: 'none' as IsolateCategory,
    }
    // Anatomy profile overrides — partial maps. Keyed by limb name
    // (LeftArm/RightArm/LeftUpLeg/RightUpLeg) for the base limb's
    // muscularity profile, and by AnatomyCurve.name for per-curve
    // sex-characteristic dials (pec/glute/hipFlare/...). Empty by
    // default; spec.profiles populates these on load.
    type ProfileTuple = [number, number, number, number]
    type TorsoTriple  = [number, number, number]
    const profiles: {
      limbs:   Record<string, ProfileTuple>
      anatomy: Record<string, ProfileTuple>
      torso:   Record<string, TorsoTriple>
    } = { limbs: {}, anatomy: {}, torso: {} }
    let currentBuild: string = 'standard'
    function applyBuildPreset(name: string) {
      const preset = BUILD_PRESETS[name]
      if (!preset) return
      currentBuild = name
      // Replace, don't merge — clearing first means switching from
      // "strong" to "skinny" actually drops the strong overrides.
      for (const k of Object.keys(profiles.limbs))   delete profiles.limbs[k]
      for (const k of Object.keys(profiles.anatomy)) delete profiles.anatomy[k]
      for (const k of Object.keys(profiles.torso))   delete profiles.torso[k]
      if (preset.limbs) {
        for (const [k, v] of Object.entries(preset.limbs)) {
          profiles.limbs[k] = [v[0], v[1], v[2], v[3]]
        }
      }
      if (preset.anatomy) {
        for (const [k, v] of Object.entries(preset.anatomy)) {
          profiles.anatomy[k] = [v[0], v[1], v[2], v[3]]
        }
      }
      if (preset.torso) {
        for (const [k, v] of Object.entries(preset.torso)) {
          profiles.torso[k] = [v[0], v[1], v[2]]
        }
      }
      rebuildPersistentPrims()
    }
    // localStorage persistence — every panel change rewrites this, so
    // reloads restore the last-used setup. Validates against the enums
    // on load so older saved data doesn't crash newer code (or vice-
    // versa). Same pattern as the face_pixel_editor's persistence.
    const LOADOUT_STORAGE_KEY = 'loadout.v1'
    function saveLoadoutToStorage() {
      try {
        if (typeof localStorage === 'undefined') return
        // Pack `currentBuild` alongside the loadout fields. The build
        // preset is conceptually loadout-adjacent — round-tripping it
        // means a reload restores the chosen body archetype, not just
        // the wardrobe / hair / cape selections.
        localStorage.setItem(LOADOUT_STORAGE_KEY,
          JSON.stringify({ ...loadout, build: currentBuild }))
      } catch { /* quota / private mode — ignore */ }
    }
    function loadLoadoutFromStorage() {
      try {
        if (typeof localStorage === 'undefined') return
        const raw = localStorage.getItem(LOADOUT_STORAGE_KEY)
        if (!raw) return
        const data = JSON.parse(raw) as Partial<Loadout>
        if (typeof data.armor === 'string' && (data.armor === 'none' || data.armor in WARDROBE)) {
          loadout.armor = data.armor as ArmorOutfit
        }
        // Hair: prefer the new per-layer booleans; fall back to legacy
        // 'hair' string mapping for older saved files.
        if (typeof data.bob === 'boolean')         loadout.bob = data.bob
        if (typeof data.ponytail === 'boolean')    loadout.ponytail = data.ponytail
        if (typeof data.bangsL === 'boolean')      loadout.bangsL = data.bangsL
        if (typeof data.bangsR === 'boolean')      loadout.bangsR = data.bangsR
        if (typeof data.spikesTop === 'boolean')   loadout.spikesTop = data.spikesTop
        if (typeof data.spikesSideL === 'boolean') loadout.spikesSideL = data.spikesSideL
        if (typeof data.spikesSideR === 'boolean') loadout.spikesSideR = data.spikesSideR
        if (typeof data.spikesBack === 'boolean')  loadout.spikesBack = data.spikesBack
        if (typeof data.bangs === 'boolean')       { loadout.bangsL = data.bangs; loadout.bangsR = data.bangs }
        if (typeof data.spikes === 'boolean')      loadout.spikesTop = data.spikes
        if (typeof data.hair === 'string' &&
            ['none','bob','long','strands','bob+strands','long+strands'].includes(data.hair) &&
            typeof data.bob !== 'boolean' && typeof data.ponytail !== 'boolean' && typeof data.bangsL !== 'boolean' && typeof data.bangsR !== 'boolean') {
          loadout.bob      = data.hair === 'bob'  || data.hair === 'bob+strands'
          loadout.ponytail = data.hair === 'long' || data.hair === 'long+strands'
          const bangsOn    = data.hair === 'strands' || data.hair === 'bob+strands' || data.hair === 'long+strands'
          loadout.bangsL = bangsOn; loadout.bangsR = bangsOn
        }
        if (typeof data.cape === 'boolean')     loadout.cape = data.cape
        if (typeof data.tail === 'boolean')     loadout.tail = data.tail
        if (typeof data.wings === 'boolean')    loadout.wings = data.wings
        if (typeof data.wingFlap === 'boolean') loadout.wingFlap = data.wingFlap
        if (typeof data.quadrupedHind === 'boolean') loadout.quadrupedHind = data.quadrupedHind
        if (typeof data.extraLimbs === 'boolean')    loadout.extraLimbs = data.extraLimbs
        if (typeof data.snakeNeck === 'boolean')     loadout.snakeNeck = data.snakeNeck
        if (typeof data.grenades === 'boolean') loadout.grenades = data.grenades
        if (typeof data.capePattern === 'string' && data.capePattern in CAPE_PATTERNS) {
          loadout.capePattern = data.capePattern as CapePattern
        }
        if (typeof data.hands === 'string' && data.hands in HAND_LIBRARY) loadout.hands = data.hands
        if (typeof data.feet  === 'string' && data.feet  in FOOT_LIBRARY) loadout.feet  = data.feet
        if (typeof data.helm  === 'string' && (HELM_STYLES as readonly string[]).includes(data.helm)) loadout.helm = data.helm as HelmStyle
        if (typeof data.isolate === 'string' && (ISOLATE_CATEGORIES as readonly string[]).includes(data.isolate)) loadout.isolate = data.isolate as IsolateCategory
        // Build preset — re-apply via applyBuildPreset so profiles
        // get re-populated, not just currentBuild bookkeeping.
        if (typeof (data as { build?: string }).build === 'string' &&
            (data as { build: string }).build in BUILD_PRESETS) {
          applyBuildPreset((data as { build: string }).build)
        }
      } catch { /* parse error — leave defaults */ }
    }
    loadLoadoutFromStorage()
    /** Classify an emitted primitive into a category for the isolate
     *  viewer. Heuristic: rig joint name + blendGroup + primitive type.
     *  Order matters — first match wins. Anything that doesn't match
     *  a specific category falls through to 'body' (head + torso +
     *  hips + neck centered ellipsoids). */
    function categoryOf(p: RaymarchPrimitive): IsolateCategory {
      const name = p.boneIdx >= 0 && p.boneIdx < rig.length ? rig[p.boneIdx].name : ''
      // Helm — uniquely identified by its dedicated blend group 14.
      if (p.blendGroup === 14) return 'helm'
      // Hands / feet — terminal limb attachments.
      if (name === 'LeftHand' || name === 'RightHand') return 'hands'
      if (name === 'LeftFoot' || name === 'RightFoot') return 'feet'
      // Hair — every hair variant (Bob, Long*, Strand*) starts with 'Hair'.
      if (/^Hair/.test(name)) return 'hair'
      // Cape segments + grenades — body extras, named by prefix.
      if (/^Cape/.test(name)) return 'cape'
      if (/^Grenade/.test(name)) return 'grenades'
      // Wardrobe pieces — WP_ prefix.
      if (/^WP_/.test(name)) return 'armor'
      // Bezier-profile capsules: chain-root names = limbs; everything
      // else (anatomy curves) = anatomy.
      if (p.type === 17 || p.type === 20) {
        if (name === 'LeftArm' || name === 'RightArm' ||
            name === 'LeftUpLeg' || name === 'RightUpLeg') return 'limbs'
        return 'anatomy'
      }
      // Centered-part fallback: head, spine, hips, neck, shoulders.
      return 'body'
    }
    function rebuildPersistentPrims() {
      const armorOutfit = loadout.armor !== 'none' ? WARDROBE[loadout.armor] : undefined
      const bodyAndExtras = [
        ...DEFAULT_BODY_PARTS,
        ...(loadout.cape     ? DEFAULT_CAPE_PARTS     : []),
        ...(loadout.tail     ? DEFAULT_TAIL           : []),
        ...(loadout.wings    ? DEFAULT_WINGS          : []),
        ...(loadout.extraLimbs ? DEFAULT_EXTRA_LIMBS  : []),
        ...(loadout.snakeNeck  ? DEFAULT_SNAKE_NECK   : []),
        ...(loadout.grenades ? DEFAULT_GRENADE_BELT   : []),
        ...(armorOutfit ? outfitToBodyParts(armorOutfit) : []),
      ]
      // Hair layers compose additively from the three booleans — bob,
      // ponytail, bangs — each with its own blendGroup so they don't
      // smin into each other. Mix freely.
      const hairList = [
        ...(loadout.bob         ? DEFAULT_BOB_HAIR        : []),
        ...(loadout.ponytail    ? DEFAULT_LONG_HAIR       : []),
        ...(loadout.bangsL      ? DEFAULT_HAIR_STRAND_L   : []),
        ...(loadout.bangsR      ? DEFAULT_HAIR_STRAND_R   : []),
        ...(loadout.spikesTop   ? DEFAULT_SPIKE_TOP       : []),
        ...(loadout.spikesSideL ? DEFAULT_SPIKE_SIDE_L    : []),
        ...(loadout.spikesSideR ? DEFAULT_SPIKE_SIDE_R    : []),
        ...(loadout.spikesBack  ? DEFAULT_SPIKE_BACK      : []),
      ]
      // Apply anatomy profile overrides — clone DEFAULT_ANATOMY with
      // any character-specific profile from `profiles.anatomy` substituted.
      // Partial maps; missing entries fall back to DEFAULT_ANATOMY's profile.
      const effectiveAnatomy = DEFAULT_ANATOMY.map((c) => {
        const o = profiles.anatomy[c.name]
        return o ? { ...c, profile: [o[0], o[1], o[2], o[3]] as ProfileTuple } : c
      })
      // Wardrobe → attachments: any wardrobe piece parented to a hand
      // or foot bone OCCLUDES the corresponding base attachment so
      // the gauntlet/boot replaces the hand/foot mesh rather than
      // emitting on top of it. Knight gauntlets cover the hand;
      // barbarian / light / knight boots cover the foot.
      const occludedJoints = new Set<string>()
      if (armorOutfit) {
        for (const piece of armorOutfit.pieces) {
          for (const part of piece.parts) {
            if (part.parentName === 'LeftHand'  || part.parentName === 'RightHand' ||
                part.parentName === 'LeftFoot'  || part.parentName === 'RightFoot') {
              occludedJoints.add(part.parentName)
            }
          }
        }
      }
      // Build the active attachment list from HAND_LIBRARY[loadout.hands]
      // + FOOT_LIBRARY[loadout.feet], then drop entries on occluded
      // joints. Library miss falls back to the 'skin'/'shoe' defaults.
      const handsList = HAND_LIBRARY[loadout.hands] ?? HAND_LIBRARY.skin
      const feetList  = FOOT_LIBRARY[loadout.feet]  ?? FOOT_LIBRARY.shoe
      const effectiveAttachments = [...handsList, ...feetList].filter(
        (a) => !occludedJoints.has(a.jointName),
      )
      const next = chibiRaymarchPrimitives(
        rig, material, undefined, undefined, hairList, bodyAndExtras,
        effectiveAnatomy, effectiveAttachments, loadout.helm,
      ) as RaymarchPrimitive[]
      // Apply limb profile overrides — chibiRaymarchPrimitives emits a
      // type-17 prim per chain root (LeftArm/RightArm/LeftUpLeg/RightUpLeg)
      // with rotation = profile. Walk the result, identify chain-root prims
      // by bone name, and swap rotation when the override is set.
      const limbBoneByIdx: Record<number, string> = {}
      for (const limbName of ['LeftArm', 'RightArm', 'LeftUpLeg', 'RightUpLeg']) {
        const idx = rig.findIndex((j) => j.name === limbName)
        if (idx >= 0) limbBoneByIdx[idx] = limbName
      }
      for (const p of next) {
        if (p.type !== 17) continue
        const limbName = limbBoneByIdx[p.boneIdx]
        if (!limbName) continue
        const o = profiles.limbs[limbName]
        if (o) p.rotation = [o[0], o[1], o[2], o[3]]
      }
      // Torso shape override — chibiRaymarchPrimitives emits a type-3
      // (ellipsoid) prim per sack-core bone (Hips/Spine/Spine1/Spine2)
      // with params = [hx, hy, hz, 0]. The build preset can override
      // those half-extents per bone to give skinny / strong / hourglass
      // distinct silhouettes (waist taper, shoulder breadth, hip flare)
      // instead of all reading as the same round potato.
      const torsoBoneByIdx: Record<number, string> = {}
      for (const torsoName of ['Hips', 'Spine', 'Spine1', 'Spine2']) {
        const idx = rig.findIndex((j) => j.name === torsoName)
        if (idx >= 0) torsoBoneByIdx[idx] = torsoName
      }
      for (const p of next) {
        if (p.type !== 3) continue
        const torsoName = torsoBoneByIdx[p.boneIdx]
        if (!torsoName) continue
        const o = profiles.torso[torsoName]
        if (o) p.params = [o[0], o[1], o[2], 0]
      }
      // Apply cape pattern override — find prims whose bone is a Cape
      // segment and rewrite their colorFunc. Default emission picked
      // colorFunc 8 (world-Y stripes); the loadout picker can swap in
      // any other pattern. Using the rig name as the routing key means
      // we don't have to thread the pattern through the chibi emitter.
      const capePatternFunc = CAPE_PATTERNS[loadout.capePattern]
      for (const p of next) {
        if (p.boneIdx >= 0 && p.boneIdx < rig.length && /^Cape/.test(rig[p.boneIdx].name)) {
          p.colorFunc = capePatternFunc as RaymarchPrimitive['colorFunc']
        }
      }
      if (rightHandIdx >= 0) {
        const baseSlot = material.namedSlots.fire_base ?? 12
        const tipSlot  = material.namedSlots.fire_tip  ?? 14
        next.push({
          type: 7, paletteSlot: baseSlot, boneIdx: rightHandIdx,
          params: [0.05, 0.14, 0.03, 12.0],
          offsetInBone: [0, 0.18, 0],
          colorFunc: 1,
          paletteSlotB: tipSlot,
          colorExtent: 0.14,
          unlit: true,
        })
      }
      // Mirror expansion — any prim with mirrorYZ:true gets a sibling
      // with X-flipped offsetInBone. Doubles the prim count for those
      // entries; lets authoring describe one side and get both. CPU
      // pass before upload, no shader-side cost.
      const expanded = expandMirrors(next)
      // Isolation filter — when active, drop every prim except those
      // matching the selected category. Camera + raymarch unchanged;
      // the accessory floats alone in the canvas. Animation is forced
      // off elsewhere (see restPose override) so the piece doesn't
      // limb-flop while you orbit around it.
      const isolated = loadout.isolate === 'none'
        ? expanded
        : expanded.filter((p) => categoryOf(p) === loadout.isolate)
      // Bone-visibility filter — drop any primitive whose bone has been
      // collapsed along its primary (Y, length) axis. Used for creature
      // presets that zero out limb chains. Most chain primitives in this
      // engine (capsules, arm/leg ellipsoids, ribbon chains) are Y-aligned;
      // their length comes from scale.y. Bird preset sets arm scale to
      // [1, 0.05, 1] — scaleY < threshold → hide. Snake preset compresses
      // spine X+Z to [0.35, 1, 0.35] — scaleY stays 1 → visible (we want
      // the spine to read as the snake's body). Hides if the bone is
      // collapsed in ALL three axes too (universal "really gone" case).
      const SCALE_HIDE_THRESHOLD = 0.1
      const visible = isolated.filter((p) => {
        if (p.boneIdx < 0 || p.boneIdx >= characterParams.scales.length) return true
        const s = characterParams.scales[p.boneIdx]
        const ax = Math.abs(s[0]), ay = Math.abs(s[1]), az = Math.abs(s[2])
        // Hide if Y-axis (length) collapsed OR if all three axes are tiny.
        return ay >= SCALE_HIDE_THRESHOLD && Math.max(ax, ay, az) >= SCALE_HIDE_THRESHOLD
      })
      persistentPrims.length = 0
      for (const p of visible) persistentPrims.push(p)
      // Persist the new loadout — every panel toggle / shuffle / load
      // funnels through here, so this is the canonical save site.
      saveLoadoutToStorage()
      invalidateRaymarchCache()
    }

    // Loadout UI — single-select rows for armor + hair, toggle pills for
    // cape + grenades. Buttons auto-style the active option so the user
    // can read the current loadout at a glance.
    function buildLoadoutUI() {
      const host = document.getElementById('loadout-panel')
      if (!host) return
      while (host.firstChild) host.removeChild(host.firstChild)

      function makeRow(
        label: string,
        opts: { value: string; text: string }[],
        getActive: () => string,
        setActive: (v: string) => void,
      ) {
        const row = document.createElement('div')
        row.style.cssText = 'display:flex; gap:4px; align-items:center; flex-wrap:wrap;'
        const lbl = document.createElement('span')
        lbl.textContent = label
        lbl.style.cssText = 'width:54px; color:#9ab; font-size:11px;'
        row.appendChild(lbl)
        const buttons: HTMLButtonElement[] = []
        for (const o of opts) {
          const b = document.createElement('button')
          b.textContent = o.text
          b.dataset.value = o.value
          b.style.fontSize = '11px'
          b.onclick = () => {
            setActive(o.value)
            for (const bb of buttons) {
              bb.style.background = bb.dataset.value === o.value ? '#2a4070' : '#1a2b4a'
            }
            rebuildPersistentPrims()
          }
          buttons.push(b)
          row.appendChild(b)
        }
        const active = getActive()
        for (const bb of buttons) {
          bb.style.background = bb.dataset.value === active ? '#2a4070' : '#1a2b4a'
        }
        host.appendChild(row)
      }

      // Armor — list every outfit in WARDROBE plus 'none'.
      const armorOpts: { value: string; text: string }[] = [{ value: 'none', text: 'none' }]
      for (const k of Object.keys(WARDROBE) as ArmorOutfit[]) armorOpts.push({ value: k, text: k })
      makeRow('armor', armorOpts, () => loadout.armor, (v) => { loadout.armor = v as ArmorOutfit })
      makeRow('bob',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.bob ? 'on' : 'off', (v) => { loadout.bob = v === 'on' },
      )
      makeRow('ponytail',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.ponytail ? 'on' : 'off', (v) => { loadout.ponytail = v === 'on' },
      )
      makeRow('bangL',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.bangsL ? 'on' : 'off', (v) => { loadout.bangsL = v === 'on' },
      )
      makeRow('bangR',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.bangsR ? 'on' : 'off', (v) => { loadout.bangsR = v === 'on' },
      )
      makeRow('spkTop',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.spikesTop ? 'on' : 'off', (v) => { loadout.spikesTop = v === 'on' },
      )
      makeRow('spkSdL',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.spikesSideL ? 'on' : 'off', (v) => { loadout.spikesSideL = v === 'on' },
      )
      makeRow('spkSdR',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.spikesSideR ? 'on' : 'off', (v) => { loadout.spikesSideR = v === 'on' },
      )
      makeRow('spkBack',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.spikesBack ? 'on' : 'off', (v) => { loadout.spikesBack = v === 'on' },
      )
      makeRow('cape',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.cape ? 'on' : 'off', (v) => { loadout.cape = v === 'on' },
      )
      makeRow('pattern',
        (Object.keys(CAPE_PATTERNS) as CapePattern[]).map((p) => ({ value: p, text: p })),
        () => loadout.capePattern, (v) => { loadout.capePattern = v as CapePattern },
      )
      makeRow('tail',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.tail ? 'on' : 'off', (v) => { loadout.tail = v === 'on' },
      )
      makeRow('wings',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.wings ? 'on' : 'off', (v) => { loadout.wings = v === 'on' },
      )
      makeRow('quad',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.quadrupedHind ? 'on' : 'off',
        (v) => { loadout.quadrupedHind = v === 'on'; applyPreset(currentProportion) },
      )
      makeRow('extras',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.extraLimbs ? 'on' : 'off', (v) => { loadout.extraLimbs = v === 'on' },
      )
      makeRow('snake',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.snakeNeck ? 'on' : 'off',
        (v) => { loadout.snakeNeck = v === 'on'; applyPreset(currentProportion) },
      )
      makeRow('grenades',
        [{ value: 'on', text: 'on' }, { value: 'off', text: 'off' }],
        () => loadout.grenades ? 'on' : 'off', (v) => { loadout.grenades = v === 'on' },
      )
      // Hand / foot library pickers — values come from HAND_LIBRARY +
      // FOOT_LIBRARY keys, so adding a new variant in attachments.ts
      // surfaces here automatically without UI plumbing.
      makeRow('hands',
        Object.keys(HAND_LIBRARY).map((k) => ({ value: k, text: k })),
        () => loadout.hands, (v) => { loadout.hands = v },
      )
      makeRow('feet',
        Object.keys(FOOT_LIBRARY).map((k) => ({ value: k, text: k })),
        () => loadout.feet, (v) => { loadout.feet = v },
      )
      // Helm picker — Tier-1 extractions demo (SUP + CHAMFER + mirrorYZ).
      //   kettle      = crown + chamfered brim
      //   horned      = same + mirrored horn pair
      //   pickelhaube = same + chamfered spike on top
      makeRow('helm',
        HELM_STYLES.map((k) => ({ value: k, text: k })),
        () => loadout.helm, (v) => { loadout.helm = v as HelmStyle },
      )
      // Isolation viewer — show only the prims of one category, hide
      // everything else. Animation auto-pauses (forced rest pose) so
      // the piece floats statically; the camera still orbits.
      makeRow('iso',
        ISOLATE_CATEGORIES.map((k) => ({ value: k, text: k })),
        () => loadout.isolate, (v) => { loadout.isolate = v as IsolateCategory },
      )

      // Build preset row — copies a named bundle of (limbs, anatomy)
      // profiles into runtime state. Spec round-trip already covers
      // it from earlier ticks, so saved characters remember the build.
      // makeRow's onSelect calls rebuildPersistentPrims indirectly; here
      // we route through applyBuildPreset to actually copy the values.
      const buildRow = document.createElement('div')
      buildRow.style.cssText = 'display:flex; gap:4px; align-items:center; flex-wrap:wrap;'
      const buildLbl = document.createElement('span')
      buildLbl.textContent = 'build'
      buildLbl.style.cssText = 'width:54px; color:#9ab; font-size:11px;'
      buildRow.appendChild(buildLbl)
      const buildKeys = Object.keys(BUILD_PRESETS)
      const buildButtons: HTMLButtonElement[] = []
      for (const key of buildKeys) {
        const b = document.createElement('button')
        b.textContent = key
        b.dataset.value = key
        b.style.fontSize = '11px'
        b.onclick = () => {
          applyBuildPreset(key)
          for (const bb of buildButtons) {
            bb.style.background = bb.dataset.value === key ? '#2a4070' : '#1a2b4a'
          }
        }
        buildButtons.push(b)
        buildRow.appendChild(b)
      }
      for (const bb of buildButtons) {
        bb.style.background = bb.dataset.value === currentBuild ? '#2a4070' : '#1a2b4a'
      }
      host.appendChild(buildRow)

      // Animation switcher — surface the M-key cycle behaviour as a
      // dropdown so the panel can drive it without focus on the canvas.
      // animations[] is populated during demo init (well before the panel
      // builds) so the names are stable here.
      if (animations.length > 1) {
        const animRow = document.createElement('div')
        animRow.style.cssText = 'display:flex; gap:4px; align-items:center; flex-wrap:wrap;'
        const animLbl = document.createElement('span')
        animLbl.textContent = 'anim'
        animLbl.style.cssText = 'width:54px; color:#9ab; font-size:11px;'
        animRow.appendChild(animLbl)
        const animSel = document.createElement('select')
        animSel.style.cssText = 'font-size:11px; flex:1;'
        animations.forEach((a, i) => {
          const o = document.createElement('option')
          o.value = String(i); o.textContent = a.name
          animSel.appendChild(o)
        })
        animSel.value = String(animIdx)
        animSel.onchange = () => {
          switchAnimation(parseInt(animSel.value, 10) || 0)
        }
        animRow.appendChild(animSel)
        host.appendChild(animRow)
        // Expose the select so applyCreaturePreset can dim incompatible
        // anim options as a soft UI hint without preventing manual picks.
        ;(window as unknown as { __animSel?: HTMLSelectElement }).__animSel = animSel
      }

      // Creature presets — one-click silhouette transforms. Each preset
      // composes loadout flags + bone-scale overrides + default anim.
      // The whole creature builder reduces to these 7 button picks.
      type ScaleVec = [number, number, number]
      type CreatureSpec = {
        bob?: boolean; ponytail?: boolean; bangsL?: boolean; bangsR?: boolean
        spikesTop?: boolean; spikesSideL?: boolean; spikesSideR?: boolean; spikesBack?: boolean
        cape?: boolean; tail?: boolean; wings?: boolean; grenades?: boolean
        quadrupedHind?: boolean; extraLimbs?: boolean; snakeNeck?: boolean
        defaultAnim?: string
        // Per-bone scale overrides (applied after applyPreset).
        boneScales?: Record<string, ScaleVec>
        // Anims that look reasonable for this creature. Used purely for
        // soft UI hint — incompatible anims are dimmed in the anim
        // dropdown when this creature is active. User can still pick any.
        compatibleAnims?: string[]
      }
      const CREATURE_PRESETS: Record<string, CreatureSpec> = {
        human: {
          bob: true, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: false,
          cape: true, tail: false, wings: false, grenades: true,
          quadrupedHind: false, extraLimbs: false, snakeNeck: false,
          defaultAnim: 'idle',
        },
        spider: {
          bob: false, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: false,
          cape: false, tail: false, wings: false, grenades: false,
          quadrupedHind: true, extraLimbs: true, snakeNeck: false,
          defaultAnim: 'crawl_backwards',
          compatibleAnims: ['crawl_backwards', 'crawling', 'running_crawl', 'mutant_run'],
        },
        dragon: {
          bob: false, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: true,
          cape: false, tail: true, wings: true, grenades: false,
          quadrupedHind: true, extraLimbs: false, snakeNeck: true,
          defaultAnim: 'crawling',
          compatibleAnims: ['crawling', 'running_crawl', 'crawl_backwards', 'mutant_run'],
        },
        bird: {
          bob: false, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: false,
          cape: false, tail: true, wings: true, grenades: false,
          quadrupedHind: false, extraLimbs: false, snakeNeck: false,
          defaultAnim: 'idle',
          // Bird: arms become wings — collapse human arm chains.
          boneScales: {
            LeftArm: [1, 0.05, 1], RightArm: [1, 0.05, 1],
            LeftForeArm: [1, 0.05, 1], RightForeArm: [1, 0.05, 1],
          },
          compatibleAnims: ['idle', 'jumping', 'standing_torch_idle_01', 'great_sword_idle', 'rifle_idle', 'ninja_idle'],
        },
        horse: {
          bob: true, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: false,
          cape: false, tail: true, wings: false, grenades: false,
          quadrupedHind: true, extraLimbs: false, snakeNeck: false,
          defaultAnim: 'running_crawl',
          compatibleAnims: ['running_crawl', 'crawling', 'crawl_backwards', 'mutant_run'],
        },
        snake: {
          bob: false, ponytail: false, bangsL: false, bangsR: false,
          spikesTop: false, spikesSideL: false, spikesSideR: false, spikesBack: false,
          cape: false, tail: true, wings: false, grenades: false,
          quadrupedHind: false, extraLimbs: false, snakeNeck: true,
          defaultAnim: 'crawling',
          compatibleAnims: ['crawling', 'crawl_backwards'],
          // Snake: no limbs, AND compress the spine + hips ellipsoid
          // cross-section so the humanoid spine reads as a long thin
          // snake body. The crawling anim puts the spine roughly
          // horizontal, so combined with snake-neck (forward) and tail
          // (back), the total silhouette is one long serpentine body.
          // X+Z dimensions go to 30-40%; Y (length) stays full.
          boneScales: {
            LeftArm: [1, 0.05, 1], RightArm: [1, 0.05, 1],
            LeftForeArm: [1, 0.05, 1], RightForeArm: [1, 0.05, 1],
            LeftUpLeg: [1, 0.05, 1], RightUpLeg: [1, 0.05, 1],
            LeftLeg: [1, 0.05, 1], RightLeg: [1, 0.05, 1],
            Hips:   [0.40, 1, 0.40],
            Spine:  [0.35, 1, 0.35],
            Spine1: [0.35, 1, 0.35],
            Spine2: [0.35, 1, 0.35],
            Neck:   [0.40, 1, 0.40],
          },
        },
      }
      function applyCreaturePreset(name: string) {
        const p = CREATURE_PRESETS[name]
        if (!p) return
        // Loadout flags
        const flagKeys = ['bob','ponytail','bangsL','bangsR','spikesTop','spikesSideL','spikesSideR','spikesBack','cape','tail','wings','grenades','quadrupedHind','extraLimbs','snakeNeck'] as const
        for (const k of flagKeys) {
          if (typeof p[k] === 'boolean') (loadout as Record<string, unknown>)[k] = p[k]
        }
        // Reset proportions to current preset (clears stale per-bone scales),
        // then apply creature-specific bone overrides on top.
        applyPreset(currentProportion)
        if (p.boneScales) {
          for (const [boneName, scale] of Object.entries(p.boneScales)) {
            const idx = rig.findIndex((j) => j.name === boneName)
            if (idx >= 0) characterParams.scales[idx] = scale
          }
        }
        // Default animation
        if (p.defaultAnim) {
          const idx = animations.findIndex((a) => a.name === p.defaultAnim)
          if (idx >= 0) switchAnimation(idx)
        }
        // Soft anim-compat hint: dim incompatible anims in the dropdown
        // (style.color), but leave them selectable. compatibleAnims is
        // an allowlist; anims NOT in it get reduced contrast. If unset,
        // treat all as compatible.
        const animSel = (window as unknown as { __animSel?: HTMLSelectElement }).__animSel
        if (animSel) {
          const compat = p.compatibleAnims
          for (let i = 0; i < animSel.options.length; i++) {
            const opt = animSel.options[i]
            const animName = animations[i]?.name
            const isCompat = !compat || (animName !== undefined && compat.indexOf(animName) >= 0)
            opt.style.color = isCompat ? '' : '#557'
          }
        }
        rebuildPersistentPrims()
        buildLoadoutUI()
        invalidateRaymarchCache()
      }
      const creatureRow = document.createElement('div')
      creatureRow.style.cssText = 'display:flex; gap:3px; flex-wrap:wrap; margin-top:4px;'
      const creatureLbl = document.createElement('span')
      creatureLbl.textContent = 'creature'
      creatureLbl.style.cssText = 'width:54px; color:#9ab; font-size:11px;'
      creatureRow.appendChild(creatureLbl)
      for (const name of Object.keys(CREATURE_PRESETS)) {
        const btn = document.createElement('button')
        btn.textContent = name
        btn.style.cssText = 'font-size:10px; padding:2px 5px; background:#1a2b4a; color:#cde; border:1px solid #345; border-radius:3px; cursor:pointer;'
        btn.onclick = () => applyCreaturePreset(name)
        creatureRow.appendChild(btn)
      }
      host.appendChild(creatureRow)

      // Shuffle + reset buttons — drive the panel state from the data
      // registries directly so the random values are always valid (no
      // out-of-enum picks). Reset matches the initial Loadout literal.
      const actionRow = document.createElement('div')
      actionRow.style.cssText = 'display:flex; gap:4px; margin-top:4px;'
      const shuffleBtn = document.createElement('button')
      shuffleBtn.textContent = 'shuffle'
      shuffleBtn.style.fontSize = '11px'
      shuffleBtn.onclick = () => {
        const armorKeys: ArmorOutfit[] = ['none', ...(Object.keys(WARDROBE) as Array<keyof typeof WARDROBE>)]
        const patternKeys              = Object.keys(CAPE_PATTERNS) as CapePattern[]
        const proportionKeys: PresetKey[] = ['chibi', 'stylized', 'realistic']
        const expressionKeys           = Object.keys(EXPRESSIONS)
        const pick = <T>(arr: readonly T[]): T => arr[Math.floor(Math.random() * arr.length)]
        loadout.armor       = pick(armorKeys)
        loadout.bob         = Math.random() < 0.6
        loadout.ponytail    = Math.random() < 0.5
        loadout.bangsL      = Math.random() < 0.5
        loadout.bangsR      = Math.random() < 0.5
        loadout.spikesTop   = Math.random() < 0.3
        loadout.spikesSideL = Math.random() < 0.2
        loadout.spikesSideR = Math.random() < 0.2
        loadout.spikesBack  = Math.random() < 0.2
        loadout.cape        = Math.random() < 0.7
        loadout.capePattern = pick(patternKeys)
        loadout.tail        = Math.random() < 0.2
        loadout.wings       = Math.random() < 0.15
        loadout.quadrupedHind = Math.random() < 0.15
        loadout.extraLimbs  = Math.random() < 0.10
        loadout.snakeNeck   = Math.random() < 0.10
        loadout.grenades    = Math.random() < 0.5
        applyPreset(pick(proportionKeys))
        if (expressionKeys.length > 0) applyExpression(pick(expressionKeys))
        rebuildPersistentPrims()
        buildLoadoutUI()
      }
      const resetBtn = document.createElement('button')
      resetBtn.textContent = 'reset'
      resetBtn.style.fontSize = '11px'
      resetBtn.onclick = () => {
        loadout.armor       = 'knight'
        loadout.bob         = true
        loadout.ponytail    = false
        loadout.bangsL      = false
        loadout.bangsR      = false
        loadout.spikesTop   = false
        loadout.spikesSideL = false
        loadout.spikesSideR = false
        loadout.spikesBack  = false
        loadout.cape        = true
        loadout.capePattern = 'stripes'
        loadout.tail        = false
        loadout.wings       = false
        loadout.quadrupedHind = false
        loadout.extraLimbs  = false
        loadout.snakeNeck   = false
        loadout.grenades    = true
        applyPreset(currentProportion)   // restores per-bone scales after retarget reset
        rebuildPersistentPrims()
        buildLoadoutUI()
      }
      actionRow.appendChild(shuffleBtn)
      actionRow.appendChild(resetBtn)
      host.appendChild(actionRow)
    }
    buildLoadoutUI()

    function switchAnimation(idx: number) {
      animIdx = ((idx % animations.length) + animations.length) % animations.length
      const entry = animations[animIdx]
      loadedVAT = entry.vat
      composer = entry.composer
      vatHandle = {
        buffer: loadedVAT.buffer,
        numInstances: loadedVAT.numJoints,
        numFrames: loadedVAT.numFrames,
      }
      // Raymarch renderer reads from the VAT buffer; without this rebind
      // an anim switch reads stale matrices from the previous animation's
      // buffer (invisible character).
      raymarch.rebind(vatHandle)
      invalidateRaymarchCache()
      elapsed = 0
    }

    function applySpriteMode(mode: SpriteMode) {
      spriteMode = mode
      const cfg = SPRITE_MODES[mode]
      // Canvas size tracks preview mode. In 'framed' mode the sprite
      // fills the canvas; in 'scene' mode the sprite sits in a 256² SNES
      // viewport. Camera + cache always bind to the sprite cell.
      const canvasSize = canvasSizeForMode()
      if (canvas.width !== canvasSize || canvas.height !== canvasSize) {
        canvas.width = canvasSize
        canvas.height = canvasSize
        gpu.context.configure({ device, format, alphaMode: 'premultiplied' })
        recreateTargets(canvasSize, canvasSize)
        outline.rebindSources(targets.sceneView!, targets.normalView!, targets.depthVizView!, canvasSize, canvasSize)
      }
      const c = cacheDimsFor(mode)
      camera.setAspect(c.w, c.h)
      fitCameraToCharacter()
      raymarch.resizeCache(c.w, c.h)
      invalidateRaymarchCache()
    }
    function togglePreviewMode() {
      previewMode = previewMode === 'scene' ? 'framed' : 'scene'
      applySpriteMode(spriteMode)   // re-run to resize canvas + rebind sources
    }

    type ViewMode = 'color' | 'normal' | 'depth'
    let viewMode: ViewMode = 'color'
    let depthOutlineOn = false
    // 0 = off (flat unlit), 1 = on (ambient + key directional + active
    // point lights). VFX adds transient point lights for muzzle flashes
    // etc. on top of directional in mode 1.
    let lightingMode: 0 | 1 = 0
    // Rest pose: freezes animation and poses the rig at identity local
    // rotations — a stable reference for iterating on proportion sliders.
    // Toggle with T.
    let restPose = false

    // --- Face-style registry — drives the outline shader's pixel stamp
    // based on the currently-selected expression (the existing expression
    // buttons: neutral/blink/smile/surprise/squint). Each expression maps
    // to an (eye, mouth) pair + optional eye-accent colour. The style IDs
    // match the shader switch in outline.ts: eyes 0..5, mouth 0..5.
    const EYE_STYLES = ['mario', 'dot', 'round', 'goggles', 'glowing', 'closed', 'crying'] as const
    type EyeStyle = typeof EYE_STYLES[number]
    const MOUTH_STYLES = ['off', 'line', 'smile', 'open_o', 'frown', 'pout'] as const
    type MouthStyle = typeof MOUTH_STYLES[number]
    const FACE_STYLES: Record<string, { eye: EyeStyle; mouth: MouthStyle; accent?: [number, number, number] }> = {
      neutral:  { eye: 'mario',  mouth: 'off'    },
      blink:    { eye: 'closed', mouth: 'off'    },    // sticky closed-eye pose
      smile:    { eye: 'mario',  mouth: 'smile'  },
      surprise: { eye: 'round',  mouth: 'open_o' },
      squint:   { eye: 'dot',    mouth: 'off'    },
      crying:   { eye: 'crying', mouth: 'frown'  },
    }
    // Half-distance (pixels) of each eye anchor from the projected face
    // centre, along the head-right screen axis. Default 1 ⇒ 2-px anchor
    // separation ⇒ 1-px gap between eye blocks.
    let eyeSpacingPx = 1
    // Manual style overrides (J cycles eye, . / , cycle mouth). When
    // non-null, override replaces the expression's authored style on
    // that axis — lets us preview every shape against any emotion
    // without adding a button per (style × emotion) pair. null = follow
    // FACE_STYLES for that axis.
    let eyeStyleOverride: EyeStyle | null = null
    let mouthStyleOverride: MouthStyle | null = null
    // Time-driven auto-blink (between intentional expression clicks).
    const BLINK_PERIOD = 3.8
    const BLINK_DURATION = 0.12
    let blinkTimer = 0

    function cycleViewMode() {
      viewMode = viewMode === 'color' ? 'normal' : viewMode === 'normal' ? 'depth' : 'color'
      outline.setViewMode(viewMode)
    }

    window.addEventListener('keydown', (e) => {
      if (e.key === '1') applySpriteMode('sz24')
      if (e.key === '2') applySpriteMode('sz32')
      if (e.key === '3') applySpriteMode('sz48')
      if (e.key === '4') applySpriteMode('debug')
      if (e.key === 'v' || e.key === 'V') cycleViewMode()
      if (e.key === 'm' || e.key === 'M') switchAnimation(animIdx + 1)
      if (e.key === 'd' || e.key === 'D') {
        depthOutlineOn = !depthOutlineOn
        outline.setDepthOutline(depthOutlineOn)
      }
      if (e.key === 'l' || e.key === 'L') {
        lightingMode = (lightingMode === 0 ? 1 : 0) as 0 | 1
        outline.setLighting(lightingMode)
      }
      if (e.key === 't' || e.key === 'T') {
        restPose = !restPose
        invalidateRaymarchCache()
      }
      if (e.key === 'k' || e.key === 'K') {
        nudeMode = !nudeMode
        applyNudeMode()
      }
      // Eye spacing: [ narrower, ] wider. Clamp to [0, 4] px half-offset.
      if (e.key === '[') eyeSpacingPx = Math.max(0, eyeSpacingPx - 1)
      if (e.key === ']') eyeSpacingPx = Math.min(4, eyeSpacingPx + 1)
      // J: cycle eye-style override (null → mario → dot → round → goggles →
      // glowing → closed → null). Null = follow the expression's authored
      // eye. Shift+J goes backward through the ring.
      if (e.key === 'j' || e.key === 'J') {
        const ring: (EyeStyle | null)[] = [null, ...EYE_STYLES]
        const idx = ring.indexOf(eyeStyleOverride)
        const next = e.shiftKey
          ? ring[(idx - 1 + ring.length) % ring.length]
          : ring[(idx + 1) % ring.length]
        eyeStyleOverride = next
      }
      // . / , : cycle mouth-style override forward / back. null = follow
      // the expression's authored mouth. Ring: null → off → line →
      // smile → open_o → frown → pout → null.
      if (e.key === '.' || e.key === ',') {
        const ring: (MouthStyle | null)[] = [null, ...MOUTH_STYLES]
        const idx = ring.indexOf(mouthStyleOverride)
        const step = e.key === '.' ? 1 : -1
        mouthStyleOverride = ring[(idx + step + ring.length) % ring.length]
      }
      if (e.key === 'f' || e.key === 'F') togglePreviewMode()
      // VFX spawn keys — gameplay-like triggers to validate the lifetime
      // manager. All anchor at RightHand (where the flame sits) so the
      // effects read as "attack originating from the hand."
      if (rightHandIdx >= 0) {
        const slot = material.namedSlots
        if (e.key === ' ') {
          e.preventDefault()
          vfxSystem.spawnSwipe(elapsed, rightHandIdx, [0, 0.15, 0],
            slot.fire_base ?? 12, slot.fire_tip ?? 14)
          vfxSystem.spawnTrail(elapsed, rightHandIdx, [0, 0.15, 0],
            slot.fire_mid ?? 13, { duration: 0.5 })
        }
        if (e.key === 'x' || e.key === 'X') {
          vfxSystem.spawnImpactStar(elapsed, rightHandIdx, [0, 0.2, 0],
            slot.fire_tip ?? 14)
        }
        if (e.key === 'z' || e.key === 'Z') {
          vfxSystem.spawnMuzzleFlash(elapsed, rightHandIdx, [0, 0.2, 0],
            slot.fire_mid ?? 13, slot.fire_tip ?? 14)
        }
        if (e.key === 'n' || e.key === 'N') {
          vfxSystem.spawnLightning(elapsed, rightHandIdx, [0, 0.2, 0],
            slot.fire_tip ?? 14, slot.eyewhite ?? 6)
        }
        if (e.key === 'b' || e.key === 'B') {
          vfxSystem.spawnBeam(elapsed, rightHandIdx, [0, 0.2, 0],
            slot.fire_mid ?? 13, slot.fire_tip ?? 14)
        }
      }
    })

    const loop = new FrameLoop()

    loop.onUpdate = (stats) => {
      elapsed += stats.dt
      // camera.update() + pixel-snap moved into onRender so they see the
      // live Hips target set after composer.update — otherwise the
      // character-tracking lagged by one frame.
    }

    // Per-primitive world AABB tracking — the robust cache invalidation
    // signal the user asked for. Each frame we compute each primitive's
    // world-space bounding sphere (center + radius) from its bone matrix
    // times its local offset + conservative param-sum radius. Any primitive
    // that moved beyond epsilon invalidates the cache. This catches:
    //
    //   - Animation (bones moved)
    //   - Proportion sliders (bone scale changed)
    //   - Primitive add/remove (array size differs)
    //   - Expression changes (face joints moved)
    //   - Anim switch (whole rig pose changed)
    //
    // It does NOT catch: camera motion, palette edits, lighting changes —
    // those feed separate fingerprints (camera view matrix + explicit
    // invalidations on palette/lighting actions).
    //
    // Dual purpose: same AABB data is a natural seed for a future BVH
    // spatial index. When the scene has hundreds of primitives, group
    // AABBs feed culling queries. For now (~30 prims) the linear diff is
    // fast enough to run every frame.
    type WorldSphere = { cx: number; cy: number; cz: number; r: number }
    const lastAabbs: WorldSphere[] = []
    const lastAabbView = new Float32Array(16)
    let lastAabbOrtho = -1
    const AABB_EPSILON = 1e-4   // meters — ~0.1mm; below this, treat as unchanged

    /** Compute world-space bounding sphere for a raymarch primitive using
     *  the composer's CPU-side world matrix mirror. Mirrors the shader's
     *  per-primitive occlusion bound (sum-of-abs-params + margin × max
     *  bone scale) so the invalidation signal agrees with the cull test. */
    function primWorldSphere(p: RaymarchPrimitive): WorldSphere {
      // Fallback if we don't have the composer (VAT1 path): radius-only
      // bound in bone-local space is fine; center just the offset. Rare
      // path in practice.
      if (!composer) {
        const r = Math.abs(p.params[0]) + Math.abs(p.params[1]) + Math.abs(p.params[2]) + Math.abs(p.params[3]) + 0.05
        return { cx: p.offsetInBone[0], cy: p.offsetInBone[1], cz: p.offsetInBone[2], r }
      }
      const base = p.boneIdx * 16
      const m = composer.worldMatrices
      const c0x = m[base + 0],  c0y = m[base + 1],  c0z = m[base + 2]
      const c1x = m[base + 4],  c1y = m[base + 5],  c1z = m[base + 6]
      const c2x = m[base + 8],  c2y = m[base + 9],  c2z = m[base + 10]
      const tx  = m[base + 12], ty  = m[base + 13], tz  = m[base + 14]
      const [ox, oy, oz] = p.offsetInBone
      const aX = c0x * ox + c1x * oy + c2x * oz + tx
      const aY = c0y * ox + c1y * oy + c2y * oz + ty
      const aZ = c0z * ox + c1z * oy + c2z * oz + tz
      // Type 17 (bezier limb): bound across joints A, B, C.
      // params[0], [1] are bone indices; profile rgba live in `rotation`.
      if (p.type === 17 || p.type === 20) {
        const jointBIdx = p.params[0]
        const jointCIdx = p.params[1]
        const bX = m[jointBIdx * 16 + 12], bY = m[jointBIdx * 16 + 13], bZ = m[jointBIdx * 16 + 14]
        const cX = m[jointCIdx * 16 + 12], cY = m[jointCIdx * 16 + 13], cZ = m[jointCIdx * 16 + 14]
        const cx = (aX + bX + cX) / 3, cy = (aY + bY + cY) / 3, cz = (aZ + bZ + cZ) / 3
        const dA = Math.hypot(cx - aX, cy - aY, cz - aZ)
        const dB = Math.hypot(cx - bX, cy - bY, cz - bZ)
        const dC = Math.hypot(cx - cX, cy - cY, cz - cZ)
        const prof = p.rotation ?? [0, 0, 0, 0]
        const maxR = Math.max(prof[0], prof[1], prof[2], prof[3])
        const r = Math.max(dA, dB, dC) + maxR + Math.abs(p.blendRadius ?? 0) + 0.05
        return { cx, cy, cz, r }
      }
      // Type 15 (line capsule): bound the segment from A to B.
      if (p.type === 15) {
        const jointBIdx = p.params[2]
        const bX = m[jointBIdx * 16 + 12], bY = m[jointBIdx * 16 + 13], bZ = m[jointBIdx * 16 + 14]
        const cx = (aX + bX) * 0.5, cy = (aY + bY) * 0.5, cz = (aZ + bZ) * 0.5
        const segHalf = Math.hypot(aX - bX, aY - bY, aZ - bZ) * 0.5
        const maxR = Math.max(Math.abs(p.params[0]), Math.abs(p.params[1]))
        const r = segHalf + maxR + Math.abs(p.blendRadius ?? 0) + 0.05
        return { cx, cy, cz, r }
      }
      // Single-bone fallback.
      const s0 = Math.sqrt(c0x * c0x + c0y * c0y + c0z * c0z)
      const s1 = Math.sqrt(c1x * c1x + c1y * c1y + c1z * c1z)
      const s2 = Math.sqrt(c2x * c2x + c2y * c2y + c2z * c2z)
      const maxScale = Math.max(s0, s1, s2)
      const rLocal = Math.abs(p.params[0]) + Math.abs(p.params[1]) + Math.abs(p.params[2]) + Math.abs(p.params[3]) + 0.05
      const r = rLocal * maxScale + Math.abs(p.blendRadius ?? 0)
      return { cx: aX, cy: aY, cz: aZ, r }
    }

    /** Compare current primitive AABBs + camera ROTATION to last frame's
     *  snapshot. Camera TRANSLATION is intentionally excluded — pan shifts
     *  the blit offset, not the cached pixels. Pixel-copy invariant means
     *  the silhouette is byte-identical for any camera translation as
     *  long as rotation/zoom/pose don't change. */
    function raymarchSceneChanged(prims: RaymarchPrimitive[]): boolean {
      if (prims.length !== lastAabbs.length) return true
      if (camera.orthoSize !== lastAabbOrtho) return true
      // Rotation columns only — indices 0..2, 4..6, 8..10. Skip 12..14
      // (translation) — that's the pan-invariant axis.
      for (const i of [0, 1, 2, 4, 5, 6, 8, 9, 10]) {
        if (camera.view[i] !== lastAabbView[i]) return true
      }
      for (let i = 0; i < prims.length; i++) {
        const s = primWorldSphere(prims[i])
        const prev = lastAabbs[i]
        if (Math.abs(s.cx - prev.cx) > AABB_EPSILON) return true
        if (Math.abs(s.cy - prev.cy) > AABB_EPSILON) return true
        if (Math.abs(s.cz - prev.cz) > AABB_EPSILON) return true
        if (Math.abs(s.r  - prev.r ) > AABB_EPSILON) return true
      }
      return false
    }

    /** Capture current primitive AABBs + camera as the new snapshot. Copies
     *  ALL of camera.view so we can compute pan deltas against it each
     *  frame even while rotation comparisons use only the rotation cols. */
    function snapshotRaymarchScene(prims: RaymarchPrimitive[]) {
      lastAabbs.length = prims.length
      for (let i = 0; i < prims.length; i++) {
        lastAabbs[i] = primWorldSphere(prims[i])
      }
      lastAabbOrtho = camera.orthoSize
      for (let i = 0; i < 16; i++) lastAabbView[i] = camera.view[i]
    }

    loop.onRender = (stats) => {
      // Quantize elapsed time to the LOD tier's animation fps BEFORE mapping
      // to a VAT frame. Between pose ticks the derived frameIdx stays the
      // same → AABBs don't shift → raymarch cache holds → blit. The
      // animation still plays at its authored duration (elapsed progresses
      // normally); we just sample it at a lower rate. Gives both the
      // pixel-art-authentic held-pose feel AND an N× cache-hit multiplier
      // where N = renderFps / animFps.
      const animFps = SPRITE_MODE_ANIM_FPS[spriteMode]
      const tickSec = 1 / animFps
      // Cap every animation to MAX_LOOP_FRAMES distinct poses regardless
      // of native VAT length. Source frames are sampled evenly across
      // the original — a 32-frame walk plays as 16 frames spaced at
      // every 2nd source. At 12fps this gives a 1.33s loop. Animations
      // shorter than the cap play their full source — the min() handles
      // that case.
      const MAX_LOOP_FRAMES = 16
      const effectiveFrames = Math.min(loadedVAT.numFrames, MAX_LOOP_FRAMES)
      const tickIndex = Math.floor(elapsed / tickSec)
      const loopTick = ((tickIndex % effectiveFrames) + effectiveFrames) % effectiveFrames
      const frameIdx = Math.floor((loopTick * loadedVAT.numFrames) / effectiveFrames) % loadedVAT.numFrames

      // Retargeting compose: overwrite vat.buffer's FIRST frame slot with
      // the current frame's composed world matrices (local × scale →
      // parent-chained world). Renderer then reads from slot 0.
      // Rest-pose mode (T key) bypasses the animation and writes the
      // rig's structural pose instead — stable reference for tuning
      // proportions across the body.
      // Update animation → update physics → draw, Unreal-style. Both
      // anim (composer) and physics (cape, springs) tick on the same
      // sprite-FPS cadence; render runs free at display refresh. Skip
      // composer + secondary on non-tick frames so the GPU keeps the
      // last-tick state and the cape doesn't appear to update faster
      // than the body.
      // Isolation viewer forces rest pose so the accessory floats
      // statically while the user orbits the camera around it. Use the
      // EFFECTIVE rest-pose flag for both the tick gate AND the
      // dispatch — otherwise toggling isolate while animating doesn't
      // re-trigger the composer and cape/spring physics keep reading
      // animated joints into a rest-pose body.
      const effectiveRestPose = restPose || loadout.isolate !== 'none'
      const tickShouldRun =
        frameIdx !== lastSecondaryFrame ||
        effectiveRestPose !== lastSecondaryRestPose
      const tickDt = tickShouldRun ? Math.max(elapsed - lastSecondaryElapsed, 1 / 60) : 0
      if (composer && tickShouldRun) {
        if (effectiveRestPose) {
          if (tposeLocalOverride) composer.applyPoseFromLocals(tposeLocalOverride, characterParams)
          else                    composer.applyRestPose(characterParams)
        } else {
          composer.update(frameIdx, characterParams)
        }
        // Procedural extra limb sync — overrides world rotation columns
        // of each Extra*_Up / Extra*_Low bone to match its source
        // humanoid limb (LeftArm/RightArm/LeftUpLeg/RightUpLeg). Then
        // recomputes child translations along the rotated bone's Y
        // axis so the chain composes correctly. Result: 4 phantom legs
        // bend in sync with the human limbs.
        if (loadout.extraLimbs && composer) applyExtraLimbsCopy(frameIdx)
        if (loadout.wings && loadout.wingFlap && composer) applyWingFlap()
        if (loadout.snakeNeck && composer) applySnakeNeckWeave()
      }

      // Cape secondary motion — node particles drive cape bone positions
      // and orientations. Each segment is centered at the midpoint between
      // its endpoint joints (top = parent particle / Spine2; bottom = this
      // particle), with its bone +Y axis pointing toward the top. That
      // makes the roundedBox primitive (whose long axis is +Y) align along
      // the chain direction so the cape reads as bent fabric.
      if (composer && CAPE_HAS_FULL_CHAIN && tickShouldRun) {
        const wm = composer.worldMatrices
        const getBoneWorldPos = (boneIdx: number): [number, number, number] => [
          wm[boneIdx * 16 + 12],
          wm[boneIdx * 16 + 13],
          wm[boneIdx * 16 + 14],
        ]
        // YAW-ONLY rotation reference. Read Hips' forward axis but
        // project onto the world horizontal plane and renormalize —
        // strips out pitch, roll, AND upper-body twist. The cape's
        // "behind" axis becomes a function of horizontal facing only
        // (which way the character is pointed in the world), so spine
        // twists, body lean, and animation tumbles don't reorient the
        // cape. Up = world +Y, Right = up × forward (right-hand rule).
        // Falls back to identity if hips axis is degenerate vertical.
        const sRotIdx = (hipsIdx >= 0 ? hipsIdx : (spine1Idx >= 0 ? spine1Idx : spine2Idx))
        const s2 = sRotIdx * 16
        let fwdHX = wm[s2 + 8]
        let fwdHZ = wm[s2 + 10]
        let fwdHLen = Math.hypot(fwdHX, fwdHZ)
        if (fwdHLen < 1e-4) { fwdHX = 0; fwdHZ = 1; fwdHLen = 1 }
        fwdHX /= fwdHLen; fwdHZ /= fwdHLen
        const sX: [number, number, number] = [ fwdHZ, 0, -fwdHX ]   // right = up × forward
        const sY: [number, number, number] = [ 0, 1, 0 ]            // up = world Y
        const sZ: [number, number, number] = [ fwdHX, 0, fwdHZ ]    // forward (horizontal)
        const rotByS2 = (v: [number, number, number]): [number, number, number] => [
          v[0] * sX[0] + v[1] * sY[0] + v[2] * sZ[0],
          v[0] * sX[1] + v[1] * sY[1] + v[2] * sZ[1],
          v[0] * sX[2] + v[1] * sY[2] + v[2] * sZ[2],
        ]

        // Cape length scales with the character's body Y. Without this,
        // the chibi preset (torso 0.55, legs 0.3) keeps a full-length
        // 0.9m cape on a ~0.7m body — overshoots the feet. Use the
        // average of torso + legs scale because the cape spans both.
        // Smin between segments smoothly fuses the now-overlapping
        // chunks into one continuous shorter cape.
        const bodyYScale = (currentScales.torso + currentScales.legs) * 0.5
        const segDrop    = CAPE_SEG_DROP * bodyYScale * capeLengthScale
        // Each particle has min/maxLength constraints baked at creation
        // time (originally ±5% of CAPE_SEG_DROP = 0.18m). At runtime when
        // capeLengthScale or bodyYScale change, those constraints would
        // clamp the chain back to the original spacing — so even with
        // larger restOffset targets the cape stays bunched up. Re-derive
        // them every tick so the chain physics actually reaches the new
        // segDrop. Skip the locked root (i=0) — it doesn't use these.
        for (let i = 1; i < capeChain.length; i++) {
          capeChain[i].minLength = segDrop * 0.95
          capeChain[i].maxLength = segDrop * 1.05
        }

        // Wind disabled — keep cape physics minimal (just gravity +
        // torso SDF collision + ground clamp) until cape behavior is
        // dialed in. Re-enable later with a windStrength slider if
        // breeze sway is desired.
        const windX = 0
        const windZ = 0

        // ROOT (i=0): LOCKED. Read Cape0's bone WORLD position directly.
        // Cape0 is rigged as a child of Spine2 with a local offset of
        // [0, 0.10, -0.28] (set in DEFAULT_CAPE_PARTS), so its world
        // matrix is automatically Spine2.world × Cape0.local — it
        // RIDES with the chest's full transform (yaw, pitch, roll).
        // When the character hunches forward, the anchor follows the
        // chest forward; when they lean back, the anchor follows back.
        // No manual offset math, no shoulder-midpoint averaging — same
        // architecture the plate armor uses.
        {
          const cape0Bone = capeBoneIndices[0] * 16
          const ax = wm[cape0Bone + 12]
          const ay = wm[cape0Bone + 13]
          const az = wm[cape0Bone + 14]
          capeChain[0].position[0] = ax
          capeChain[0].position[1] = ay
          capeChain[0].position[2] = az
          capeChain[0].prevParentPos[0] = ax
          capeChain[0].prevParentPos[1] = ay
          capeChain[0].prevParentPos[2] = az
          capeChain[0].initialised = true
        }

        // MID + TIP: chain physics with rest target along Cape0's
        // (= Spine2's) local -Y axis, NOT world-down. When the body
        // bends forward, Cape0's -Y rotates forward too, so the chain
        // hangs from the chest along the spine axis instead of going
        // straight down through the bent-forward body. This is what
        // makes the cape behave like it's actually rigged to the spine
        // bone — same as the user's plate-armor reference. Without it
        // the chain rest is world-down from a moving anchor, which
        // drags particles through the body whenever the spine bends.
        const cape0Mat = capeBoneIndices[0] * 16
        const c0X: [number, number, number] = [wm[cape0Mat + 0], wm[cape0Mat + 1], wm[cape0Mat + 2]]
        const c0Y: [number, number, number] = [wm[cape0Mat + 4], wm[cape0Mat + 5], wm[cape0Mat + 6]]
        const c0Z: [number, number, number] = [wm[cape0Mat + 8], wm[cape0Mat + 9], wm[cape0Mat + 10]]
        // Normalize Cape0 basis (in case Spine2 has scale baked in).
        const c0XL = Math.hypot(...c0X) || 1
        const c0YL = Math.hypot(...c0Y) || 1
        const c0ZL = Math.hypot(...c0Z) || 1
        const c0Xn = [c0X[0]/c0XL, c0X[1]/c0XL, c0X[2]/c0XL] as [number, number, number]
        const c0Yn = [c0Y[0]/c0YL, c0Y[1]/c0YL, c0Y[2]/c0YL] as [number, number, number]
        const c0Zn = [c0Z[0]/c0ZL, c0Z[1]/c0ZL, c0Z[2]/c0ZL] as [number, number, number]
        const rotByCape0 = (v: [number, number, number]): [number, number, number] => [
          v[0] * c0Xn[0] + v[1] * c0Yn[0] + v[2] * c0Zn[0],
          v[0] * c0Xn[1] + v[1] * c0Yn[1] + v[2] * c0Zn[1],
          v[0] * c0Xn[2] + v[1] * c0Yn[2] + v[2] * c0Zn[2],
        ]
        for (let i = 1; i < capeChain.length; i++) {
          const baseOff = capeChain[i].restOffset
          // Rest offset in Cape0's local frame (= Spine2's frame). Top
          // of chain follows body axis; tail blends toward world-down
          // for natural drape — long capes that just point along the
          // bent spine read as stiff. Drape factor ramps from 0 at
          // the anchor to ~0.6 at the tail, so the tail particles
          // gravitationally relax even when the body bends forward.
          const yScaled = (baseOff[1] / CAPE_SEG_DROP) * segDrop
          const bodyOff = rotByCape0([baseOff[0], yScaled, baseOff[2]])
          const worldOff: [number, number, number] = [0, yScaled, 0]
          const drape = Math.min(0.85, (i / capeChain.length) * 1.0)
          const rotatedOff: [number, number, number] = [
            bodyOff[0] * (1 - drape) + worldOff[0] * drape,
            bodyOff[1] * (1 - drape) + worldOff[1] * drape,
            bodyOff[2] * (1 - drape) + worldOff[2] * drape,
          ]
          const k = (i + 1) / capeChain.length
          const offsetWithWind: [number, number, number] = [
            rotatedOff[0] + windX * k,
            rotatedOff[1],
            rotatedOff[2] + windZ * k,
          ]
          tickNodeParticle(capeChain[i], capeChain, getBoneWorldPos, offsetWithWind)
        }

        // Body collision — REAL SDF query against the torso's actual
        // primitives. Walk the persistent prim list, filter to blend
        // group 6 (torso sack-core: Hips/Spine/Spine1/Spine2 ellipsoids
        // + LeftShoulder/RightShoulder spheres), and smin them together
        // exactly like the shader does. Push each cape particle outward
        // along the SDF gradient until distance >= BODY_BUFFER. This
        // tracks any body shape change (proportions, archetypes, future
        // segment-bezier torso) without re-authoring colliders, and
        // handles the shoulder/upper-body region the spheres missed.
        // Buffer is larger than naive cape-radius-from-body because the
        // cape SEGMENT ellipsoid extends ±halfZ (0.025m) along its
        // forward axis, which points into the body when the cape is
        // hanging straight down behind. Different blend groups hard-min
        // with no smoothing, so any geometric overlap reads as a clip.
        // 0.12m = 0.025 cape thickness + 0.095 visible clearance. Looks
        // generous but the torso ellipsoids' max half-extents are big
        // (Spine1 Z = 0.156) so the cape needs real distance to clear.
        const BODY_BUFFER = 0.075
        const TORSO_BLEND_GROUP = 6
        const torsoCollisionPrims = persistentPrims.filter(
          p => p.blendGroup === TORSO_BLEND_GROUP &&
               (p.type === 0 || p.type === 1 || p.type === 3),
        )
        // One-time debug — see what prims are getting picked up so we can
        // diagnose if collision isn't firing. Logs once per second of
        // elapsed sim time so the console doesn't spam.
        if (!capeCollisionDebugged && torsoCollisionPrims.length > 0) {
          console.log(`[cape-collision] ${torsoCollisionPrims.length} torso prims:`,
            torsoCollisionPrims.map(p => ({
              type: p.type, bone: rig[p.boneIdx]?.name, params: Array.from(p.params),
              br: p.blendRadius,
            })))
          capeCollisionDebugged = true
        }
        // worldToLocal — JS port of the shader function. Returns p in
        // bone-local where each axis is normalized by its world basis
        // magnitude (so non-unit scale on the bone is undone).
        const worldToLocalJS = (boneMatStart: number, wx: number, wy: number, wz: number): [number, number, number] => {
          const c0x = wm[boneMatStart],     c0y = wm[boneMatStart + 1], c0z = wm[boneMatStart + 2]
          const c1x = wm[boneMatStart + 4], c1y = wm[boneMatStart + 5], c1z = wm[boneMatStart + 6]
          const c2x = wm[boneMatStart + 8], c2y = wm[boneMatStart + 9], c2z = wm[boneMatStart + 10]
          const tx  = wm[boneMatStart + 12], ty  = wm[boneMatStart + 13], tz  = wm[boneMatStart + 14]
          const s0sq = Math.max(c0x*c0x + c0y*c0y + c0z*c0z, 1e-10)
          const s1sq = Math.max(c1x*c1x + c1y*c1y + c1z*c1z, 1e-10)
          const s2sq = Math.max(c2x*c2x + c2y*c2y + c2z*c2z, 1e-10)
          const dx = wx - tx, dy = wy - ty, dz = wz - tz
          return [
            (c0x * dx + c0y * dy + c0z * dz) / s0sq,
            (c1x * dx + c1y * dy + c1z * dz) / s1sq,
            (c2x * dx + c2y * dy + c2z * dz) / s2sq,
          ]
        }
        // Polynomial smin matching shader's smin_k.
        const smin_k = (a: number, b: number, k: number): number => {
          const kk = Math.max(k, 1e-6)
          const h = Math.max(0, Math.min(1, 0.5 + 0.5 * (b - a) / kk))
          return (b * (1 - h) + a * h) - kk * h * (1 - h)
        }
        // SDF eval at a world point. Returns distance to torso surface
        // (negative inside, positive outside).
        const torsoSDF = (wx: number, wy: number, wz: number): number => {
          let d = 1e9
          for (const p of torsoCollisionPrims) {
            const baseM = p.boneIdx * 16
            const lp = worldToLocalJS(baseM, wx, wy, wz)
            const off = p.offsetInBone
            const lx = lp[0] - off[0], ly = lp[1] - off[1], lz = lp[2] - off[2]
            let primD: number
            if (p.type === 0) {
              // Sphere: params[0] = radius
              primD = Math.hypot(lx, ly, lz) - p.params[0]
            } else if (p.type === 1) {
              // Box: params[0..2] = half-extents
              const qx = Math.abs(lx) - p.params[0]
              const qy = Math.abs(ly) - p.params[1]
              const qz = Math.abs(lz) - p.params[2]
              const outX = Math.max(qx, 0), outY = Math.max(qy, 0), outZ = Math.max(qz, 0)
              const outerLen = Math.hypot(outX, outY, outZ)
              const inner = Math.min(Math.max(qx, qy, qz), 0)
              primD = outerLen + inner
            } else {
              // Ellipsoid (type 3, IQ bound). The exact IQ formula
              // k0*(k0-1)/k1 is NaN at p=origin (both k0 and k1 go to 0).
              // Use the simpler bound (k0 - 1) * min(r) — slightly less
              // tight at very oblong shapes but always finite.
              const rx = Math.max(p.params[0], 1e-4)
              const ry = Math.max(p.params[1], 1e-4)
              const rz = Math.max(p.params[2], 1e-4)
              const k0 = Math.hypot(lx / rx, ly / ry, lz / rz)
              primD = (k0 - 1) * Math.min(rx, ry, rz)
            }
            // Use each prim's OWN blendRadius so the smin matches what
            // the shader is computing. Falls back to 0.07 if missing.
            const br = (p.blendRadius && p.blendRadius > 0) ? p.blendRadius : 0.07
            d = smin_k(d, primD, br)
          }
          return d
        }
        // Skip root (i=0) — it's already locked to a sensible position.
        if (torsoCollisionPrims.length > 0) {
          const eps = 0.005
          // One-shot debug — log SDF distance for each cape particle so
          // we can see if (a) particles are clipping (d < buffer) or
          // (b) the SDF is returning wrong values.
          if (!capeDistDebugged) {
            const dists: number[] = []
            for (let i = 0; i < capeChain.length; i++) {
              const cp = capeChain[i].position
              dists.push(torsoSDF(cp[0], cp[1], cp[2]))
            }
            console.log('[cape-collision] particle distances to torso SDF:',
              dists.map((d, i) => `[${i}]=${d.toFixed(3)}m @ (${capeChain[i].position.map(v => v.toFixed(2)).join(',')})`).join(' '))
            capeDistDebugged = true
          }
          for (let i = 1; i < capeChain.length; i++) {
            const cp = capeChain[i].position
            // 2 push iterations — one query+gradient is usually enough,
            // but a second pass cleans up cases where the first push
            // landed on the buffer boundary at an oblique angle.
            for (let iter = 0; iter < 2; iter++) {
              const d = torsoSDF(cp[0], cp[1], cp[2])
              if (d >= BODY_BUFFER) break
              // Finite-difference gradient
              const dxp = torsoSDF(cp[0] + eps, cp[1], cp[2])
              const dxn = torsoSDF(cp[0] - eps, cp[1], cp[2])
              const dyp = torsoSDF(cp[0], cp[1] + eps, cp[2])
              const dyn = torsoSDF(cp[0], cp[1] - eps, cp[2])
              const dzp = torsoSDF(cp[0], cp[1], cp[2] + eps)
              const dzn = torsoSDF(cp[0], cp[1], cp[2] - eps)
              let gx = dxp - dxn, gy = dyp - dyn, gz = dzp - dzn
              const gLen = Math.hypot(gx, gy, gz)
              if (gLen < 1e-6) break
              gx /= gLen; gy /= gLen; gz /= gLen
              // Anti-tunneling: only reflect the gradient when the
              // particle is on the FRONT side of the anchor plane —
              // i.e., it has actually tunneled through the body.
              // Particles correctly behind the body have anchorFwd < 0
              // and skip reflection, so the cape falls naturally with
              // gravity. Reflecting on every forward-pointing gradient
              // (regardless of which side the particle is on) caused
              // small sideways/down nudges that compounded into a curl-
              // under-body artifact.
              const anchorFwd = (cp[0] - capeChain[0].position[0]) * sZ[0]
                              + (cp[1] - capeChain[0].position[1]) * sZ[1]
                              + (cp[2] - capeChain[0].position[2]) * sZ[2]
              if (anchorFwd > 0) {
                const dotFwd = gx * sZ[0] + gy * sZ[1] + gz * sZ[2]
                if (dotFwd > 0) {
                  gx -= 2 * dotFwd * sZ[0]
                  gy -= 2 * dotFwd * sZ[1]
                  gz -= 2 * dotFwd * sZ[2]
                  const gLen2 = Math.hypot(gx, gy, gz)
                  if (gLen2 > 1e-6) { gx /= gLen2; gy /= gLen2; gz /= gLen2 }
                }
              }
              // Push outward by exactly the deficit so we land on the buffer surface.
              const push = BODY_BUFFER - d
              cp[0] += gx * push
              cp[1] += gy * push
              cp[2] += gz * push
            }
          }
        }
        // HINGE constraint — confine all cape particles to the body's
        // vertical plane perpendicular to sX (body's right axis). With
        // halfW along R = body's right, this means the cape can only
        // bend in the (forward, up) plane perpendicular to its width,
        // which makes the cross-section's wide axis ALWAYS the hinge
        // axis. Result: pure hinge motion at every joint, no twisting.
        // Real fabric only folds along its thin axis — this matches.
        {
          const anchorPos = capeChain[0].position
          for (let i = 1; i < capeChain.length; i++) {
            const cp = capeChain[i].position
            const dx = cp[0] - anchorPos[0]
            const dy = cp[1] - anchorPos[1]
            const dz = cp[2] - anchorPos[2]
            const dotR = dx * sX[0] + dy * sX[1] + dz * sX[2]
            cp[0] -= dotR * sX[0]
            cp[1] -= dotR * sX[1]
            cp[2] -= dotR * sX[2]
          }
        }
        // Ground-plane collision — cape can't sink below the character's
        // local ground. Use the lower of the two feet's world Y (or 0
        // if feet are missing) as the floor; clamp particles to >= floor.
        // When the cape is long enough to drag, this is what makes it
        // pile up at the feet instead of disappearing into the floor.
        {
          const lFootY = lFootIdx >= 0 ? wm[lFootIdx * 16 + 13] : 0
          const rFootY = rFootIdx >= 0 ? wm[rFootIdx * 16 + 13] : 0
          const groundY = Math.min(lFootY, rFootY) + 0.01   // 1cm above sole
          for (let i = 1; i < capeChain.length; i++) {
            const cp = capeChain[i].position
            if (cp[1] < groundY) cp[1] = groundY
          }
        }
        // Parallel-transport R down the chain so adjacent cape bones share
        // the same R/F frame at their shared vertex (no twist around the
        // tangent axis). Without parallel transport, each bone projects
        // sX independently → adjacent bones' R values differ by the
        // segment-tangent angle, producing visible kinks where rotated
        // boxes meet at vertices. Parallel transport propagates R via
        // minimum rotation between consecutive tangents (Rodrigues), so
        // the chain "arcs only, never twists" — exactly the geometric
        // constraint we want for cloth.
        let prevTang_x = 0, prevTang_y = -1, prevTang_z = 0
        let prevR_x = sX[0], prevR_y = sX[1], prevR_z = sX[2]
        for (let i = 0; i < capeBoneIndices.length; i++) {
          const boneIdx = capeBoneIndices[i]
          const off = boneIdx * 16
          const here: [number, number, number] = capeChain[i].position
          const next: [number, number, number] = (i + 1 < capeChain.length)
            ? capeChain[i + 1].position
            : [here[0], here[1] - segDrop, here[2]]
          let uy0 = next[0] - here[0]
          let uy1 = next[1] - here[1]
          let uy2 = next[2] - here[2]
          const ulen = Math.hypot(uy0, uy1, uy2) || 1
          uy0 /= ulen; uy1 /= ulen; uy2 /= ulen

          let rx0: number, rx1: number, rx2: number
          if (i === 0) {
            // First bone: project sX perpendicular to tangent.
            const upDotR = uy0 * sX[0] + uy1 * sX[1] + uy2 * sX[2]
            rx0 = sX[0] - uy0 * upDotR
            rx1 = sX[1] - uy1 * upDotR
            rx2 = sX[2] - uy2 * upDotR
            let rlen = Math.hypot(rx0, rx1, rx2)
            if (rlen < 0.05) {
              const upDotF = uy0 * sZ[0] + uy1 * sZ[1] + uy2 * sZ[2]
              rx0 = sZ[0] - uy0 * upDotF
              rx1 = sZ[1] - uy1 * upDotF
              rx2 = sZ[2] - uy2 * upDotF
              rlen = Math.hypot(rx0, rx1, rx2) || 1
            }
            rx0 /= rlen; rx1 /= rlen; rx2 /= rlen
          } else {
            // Parallel-transport prevR from prevTang to current tangent.
            // Rodrigues: R' = R*c + (axis × R)*s + axis*(axis · R)*(1-c)
            const cosA = prevTang_x * uy0 + prevTang_y * uy1 + prevTang_z * uy2
            if (cosA > 0.9999) {
              // Tangent unchanged — keep R.
              rx0 = prevR_x; rx1 = prevR_y; rx2 = prevR_z
            } else {
              const ax = prevTang_y * uy2 - prevTang_z * uy1
              const ay = prevTang_z * uy0 - prevTang_x * uy2
              const az = prevTang_x * uy1 - prevTang_y * uy0
              const aLen = Math.hypot(ax, ay, az) || 1
              const axn = ax / aLen, ayn = ay / aLen, azn = az / aLen
              const sinA = aLen   // |cross(unit, unit)| = sin(angle)
              const dotAR = axn * prevR_x + ayn * prevR_y + azn * prevR_z
              const crX = ayn * prevR_z - azn * prevR_y
              const crY = azn * prevR_x - axn * prevR_z
              const crZ = axn * prevR_y - ayn * prevR_x
              const oneMC = 1 - cosA
              rx0 = prevR_x * cosA + crX * sinA + axn * dotAR * oneMC
              rx1 = prevR_y * cosA + crY * sinA + ayn * dotAR * oneMC
              rx2 = prevR_z * cosA + crZ * sinA + azn * dotAR * oneMC
              // Renormalize against tiny numerical drift.
              const rlen2 = Math.hypot(rx0, rx1, rx2) || 1
              rx0 /= rlen2; rx1 /= rlen2; rx2 /= rlen2
            }
          }
          prevTang_x = uy0; prevTang_y = uy1; prevTang_z = uy2
          prevR_x = rx0; prevR_y = rx1; prevR_z = rx2
          // Forward (Z axis) = right × up — perpendicular to both.
          const fz0 = rx1 * uy2 - rx2 * uy1
          const fz1 = rx2 * uy0 - rx0 * uy2
          const fz2 = rx0 * uy1 - rx1 * uy0
          // Translation = `here` (this joint's world position). For
          // type-16, the segment spans bone[i].translation → bone[i+1]
          // .translation; encoding the joint at the particle position
          // makes that span correct automatically. Length is derived
          // from the actual particle-to-particle distance, so the
          // capeLengthScale slider works through segDrop alone — no
          // bone-axis stretch needed (which was a hack for the old
          // ellipsoid emission).
          // Debug: log first 3 bones' R values to verify parallel transport.
          // R values should be smoothly related (rotated together with tangent)
          // not independently projected.
          if (!capePtDebugged && i < 4) {
            console.log(
              `[cape-pt] bone${i} tang=(${uy0.toFixed(3)},${uy1.toFixed(3)},${uy2.toFixed(3)}) ` +
              `R=(${rx0.toFixed(3)},${rx1.toFixed(3)},${rx2.toFixed(3)}) ` +
              `R·tang=${(rx0 * uy0 + rx1 * uy1 + rx2 * uy2).toFixed(4)}`
            )
            if (i === 3) capePtDebugged = true
          }
          // Column-major mat4: col0=right, col1=up, col2=forward, col3=here.
          wm[off + 0]  = rx0; wm[off + 1]  = rx1; wm[off + 2]  = rx2; wm[off + 3]  = 0
          wm[off + 4]  = uy0; wm[off + 5]  = uy1; wm[off + 6]  = uy2; wm[off + 7]  = 0
          wm[off + 8]  = fz0; wm[off + 9]  = fz1; wm[off + 10] = fz2; wm[off + 11] = 0
          wm[off + 12] = here[0]; wm[off + 13] = here[1]; wm[off + 14] = here[2]; wm[off + 15] = 1
        }
        // Re-upload the contiguous cape-bone range. Cape0..N are appended
        // in order to the rig so their world matrices live in consecutive
        // slots in the matrix buffer.
        const cape0Idx = capeBoneIndices[0]
        const startFloat = cape0Idx * 16
        // DEBUG one-shot: dump every cape bone's translation column to
        // verify what the GPU buffer contains. Compare to where the cape
        // visually appears.
        if (!capeMatDebugged) {
          for (let k = 0; k < capeBoneIndices.length; k++) {
            const bi = capeBoneIndices[k]
            const o = bi * 16
            console.log(
              `[cape-mat] bone${k} idx=${bi} pos=(` +
              `${wm[o + 12].toFixed(3)},${wm[o + 13].toFixed(3)},${wm[o + 14].toFixed(3)}) ` +
              `X=(${wm[o + 0].toFixed(2)},${wm[o + 1].toFixed(2)},${wm[o + 2].toFixed(2)}) ` +
              `Y=(${wm[o + 4].toFixed(2)},${wm[o + 5].toFixed(2)},${wm[o + 6].toFixed(2)})`
            )
          }
          // Also log Spine2 for comparison.
          if (spine2Idx >= 0) {
            const o = spine2Idx * 16
            console.log(
              `[cape-mat] Spine2 idx=${spine2Idx} pos=(` +
              `${wm[o + 12].toFixed(3)},${wm[o + 13].toFixed(3)},${wm[o + 14].toFixed(3)})`
            )
          }
          capeMatDebugged = true
        }
        device.queue.writeBuffer(
          vatHandle.buffer,
          cape0Idx * 64,
          wm.buffer,
          wm.byteOffset + startFloat * 4,
          16 * capeBoneIndices.length * 4,
        )
        invalidateRaymarchCache()
      }

      // Long hair secondary motion — same architecture as the cape, but
      // anchored to Head and using the head's rotation columns to place
      // segment offsets. Body collision pushes hair particles out of a
      // head sphere + two shoulder spheres so the chain doesn't tunnel
      // through the cranium when the head whips around.
      if (composer && HAIR_HAS_FULL_CHAIN && tickShouldRun) {
        const wm = composer.worldMatrices
        const getBoneWorldPos = (boneIdx: number): [number, number, number] => [
          wm[boneIdx * 16 + 12],
          wm[boneIdx * 16 + 13],
          wm[boneIdx * 16 + 14],
        ]
        // Head rotation columns — transform local-frame offsets into world.
        const h0 = headIdx * 16
        const hX: [number, number, number] = [wm[h0 + 0], wm[h0 + 1], wm[h0 + 2]]
        const hY: [number, number, number] = [wm[h0 + 4], wm[h0 + 5], wm[h0 + 6]]
        const hZ: [number, number, number] = [wm[h0 + 8], wm[h0 + 9], wm[h0 + 10]]
        const rotByHead = (v: [number, number, number]): [number, number, number] => [
          v[0] * hX[0] + v[1] * hY[0] + v[2] * hZ[0],
          v[0] * hX[1] + v[1] * hY[1] + v[2] * hZ[1],
          v[0] * hX[2] + v[1] * hY[2] + v[2] * hZ[2],
        ]

        // Body-forward axis (yaw-only horizontal) — same construction as
        // the cape's sZ. Used for anti-tunneling in the torso SDF push:
        // hair particles correctly behind the body project negatively
        // onto this axis (relative to a body-anchor origin), and the SDF
        // push lets gravity drape them naturally. Particles that have
        // tunneled to the FRONT of the body project positively, and we
        // reflect the gradient sideways to wrap them back around instead
        // of letting the chest-front gradient push them further forward.
        const bodyRotIdx = (hipsIdx >= 0 ? hipsIdx : (spine1Idx >= 0 ? spine1Idx : spine2Idx))
        let bodyFwdX = 0, bodyFwdZ = 1
        if (bodyRotIdx >= 0) {
          const bm = bodyRotIdx * 16
          bodyFwdX = wm[bm + 8]
          bodyFwdZ = wm[bm + 10]
          const bLen = Math.hypot(bodyFwdX, bodyFwdZ)
          if (bLen < 1e-4) { bodyFwdX = 0; bodyFwdZ = 1 } else { bodyFwdX /= bLen; bodyFwdZ /= bLen }
        }
        const bodyFwd: [number, number, number] = [bodyFwdX, 0, bodyFwdZ]

        // Wind: weaker than the cape (hair is lighter but closer to head,
        // so big sideways drift looks wrong). Slight DOWN bias keeps the
        // strands flowing earthward instead of flying horizontal.
        const hairWindStrength = 0.025
        const hairWindAngle = elapsed * 0.85 + Math.sin(elapsed * 0.5) * 0.4
        const hairWindX = Math.cos(hairWindAngle) * hairWindStrength
        const hairWindZ = Math.sin(hairWindAngle) * hairWindStrength

        // Per-tick segment drop. Auto-scales with head proportion so chibi
        // characters don't get adult-length hair, then user overrides via
        // the hair-length slider. Re-derive minLength/maxLength every tick
        // so the chain physics actually reaches the new spacing (otherwise
        // the original constraints clamp it back to default — same gotcha
        // the cape hit, see CAPE_SEG_DROP scaling above).
        const headYScale = currentScales.head
        const hairSegDrop = HAIR_SEG_DROP * headYScale * hairLengthScale
        for (let i = 1; i < hairChain.length; i++) {
          hairChain[i].minLength = hairSegDrop * 0.95
          hairChain[i].maxLength = hairSegDrop * 1.05
        }

        // ROOT: lock HairLong0 to Head world position + head-rotated offset.
        {
          const headPos = getBoneWorldPos(headIdx)
          const rotatedOff = rotByHead(HAIR_ANCHOR_OFFSET)
          hairChain[0].position[0] = headPos[0] + rotatedOff[0]
          hairChain[0].position[1] = headPos[1] + rotatedOff[1]
          hairChain[0].position[2] = headPos[2] + rotatedOff[2]
          hairChain[0].prevParentPos[0] = headPos[0]
          hairChain[0].prevParentPos[1] = headPos[1]
          hairChain[0].prevParentPos[2] = headPos[2]
          hairChain[0].initialised = true
        }

        // MID + TIP: chain physics with head-rotated offsets + wind.
        // Rest direction has a backward (-Z head-local) bias so the chain
        // pokes OUT from the back of the cranium instead of dangling
        // straight down through it. Tip drape blends toward world-down so
        // the strand tips always relax with gravity (mirrors cape drape):
        // when the head looks up sharply, root segments still hug the
        // skull but distal segments fall earthward instead of trailing
        // horizontally back. Together with head-SDF push-out below, the
        // chain naturally fans around the cranium curve.
        const HAIR_BACK_TILT_COS = 0.94      // cos(20°) — gentle back-tilt
        const HAIR_BACK_TILT_SIN = 0.34      // sin(20°)
        for (let i = 1; i < hairChain.length; i++) {
          const baseOff = hairChain[i].restOffset
          const yScaled = (baseOff[1] / HAIR_SEG_DROP) * hairSegDrop
          const headLocalOff: [number, number, number] = [
            baseOff[0],
            yScaled * HAIR_BACK_TILT_COS,
            -hairSegDrop * HAIR_BACK_TILT_SIN,
          ]
          const bodyOff = rotByHead(headLocalOff)
          const drape = Math.min(0.7, (i / hairChain.length) * 0.85)
          const worldOff: [number, number, number] = [0, yScaled, 0]
          const rotatedOff: [number, number, number] = [
            bodyOff[0] * (1 - drape) + worldOff[0] * drape,
            bodyOff[1] * (1 - drape) + worldOff[1] * drape,
            bodyOff[2] * (1 - drape) + worldOff[2] * drape,
          ]
          const k = (i + 1) / hairChain.length
          const offsetWithWind: [number, number, number] = [
            rotatedOff[0] + hairWindX * k,
            rotatedOff[1],
            rotatedOff[2] + hairWindZ * k,
          ]
          tickNodeParticle(hairChain[i], hairChain, getBoneWorldPos, offsetWithWind)
        }

        // Head collision — single sphere attached to the Head bone, with
        // its center lifted in head-local Y to sit at the cranium center
        // rather than at the bone origin (mixamo's Head joint sits roughly
        // at chin/jaw level). Lifting it puts the cranium ball where it
        // belongs and lets the chin/jaw be handled by gravity + the torso
        // SDF below. Cheaper than a multi-prim head SDF and tracks
        // proportion presets via headYScale-modulated radius.
        const HEAD_COL_LIFT_LOCAL = 0.05
        const HEAD_COL_RADIUS = 0.18 * headYScale
        {
          const headPos = getBoneWorldPos(headIdx)
          const lift = rotByHead([0, HEAD_COL_LIFT_LOCAL, 0])
          const cx = headPos[0] + lift[0]
          const cy = headPos[1] + lift[1]
          const cz = headPos[2] + lift[2]
          for (let i = 1; i < hairChain.length; i++) {
            const cp = hairChain[i].position
            const dx = cp[0] - cx
            const dy = cp[1] - cy
            const dz = cp[2] - cz
            const dist = Math.hypot(dx, dy, dz)
            if (dist > 1e-6 && dist < HEAD_COL_RADIUS) {
              const k2 = HEAD_COL_RADIUS / dist
              cp[0] = cx + dx * k2
              cp[1] = cy + dy * k2
              cp[2] = cz + dz * k2
            }
          }
        }

        // Torso SDF push-out for long hair — same architecture as the
        // cape's body collision, but with a THICKER buffer so the hair
        // sits OUTSIDE the cape rather than coinciding with it. Cape
        // buffer is 0.075 (particle 7.5cm from torso surface), cape
        // geometry extends ±0.025 along its Z axis, so cape outer face
        // is at +0.10m. Hair half-cross-section is ~0.045 + visible
        // clearance ~0.015 → HAIR_BODY_BUFFER = 0.16. Shoulders live
        // in blend group 6 so this push handles over-shoulder draping
        // for long hair without needing separate shoulder spheres.
        const HAIR_BODY_BUFFER = 0.16
        const TORSO_GROUP = 6
        const torsoCollPrims = persistentPrims.filter(
          p => p.blendGroup === TORSO_GROUP &&
               (p.type === 0 || p.type === 1 || p.type === 3),
        )
        const worldToLocalH = (boneMatStart: number, wx: number, wy: number, wz: number): [number, number, number] => {
          const c0x = wm[boneMatStart],     c0y = wm[boneMatStart + 1], c0z = wm[boneMatStart + 2]
          const c1x = wm[boneMatStart + 4], c1y = wm[boneMatStart + 5], c1z = wm[boneMatStart + 6]
          const c2x = wm[boneMatStart + 8], c2y = wm[boneMatStart + 9], c2z = wm[boneMatStart + 10]
          const tx  = wm[boneMatStart + 12], ty  = wm[boneMatStart + 13], tz  = wm[boneMatStart + 14]
          const s0sq = Math.max(c0x*c0x + c0y*c0y + c0z*c0z, 1e-10)
          const s1sq = Math.max(c1x*c1x + c1y*c1y + c1z*c1z, 1e-10)
          const s2sq = Math.max(c2x*c2x + c2y*c2y + c2z*c2z, 1e-10)
          const dx = wx - tx, dy = wy - ty, dz = wz - tz
          return [
            (c0x * dx + c0y * dy + c0z * dz) / s0sq,
            (c1x * dx + c1y * dy + c1z * dz) / s1sq,
            (c2x * dx + c2y * dy + c2z * dz) / s2sq,
          ]
        }
        const sminH = (a: number, b: number, k: number): number => {
          const kk = Math.max(k, 1e-6)
          const h = Math.max(0, Math.min(1, 0.5 + 0.5 * (b - a) / kk))
          return (b * (1 - h) + a * h) - kk * h * (1 - h)
        }
        const torsoSDFForHair = (wx: number, wy: number, wz: number): number => {
          let d = 1e9
          for (const p of torsoCollPrims) {
            const baseM = p.boneIdx * 16
            const lp = worldToLocalH(baseM, wx, wy, wz)
            const off = p.offsetInBone
            const lx = lp[0] - off[0], ly = lp[1] - off[1], lz = lp[2] - off[2]
            let primD: number
            if (p.type === 0) {
              primD = Math.hypot(lx, ly, lz) - p.params[0]
            } else if (p.type === 1) {
              const qx = Math.abs(lx) - p.params[0]
              const qy = Math.abs(ly) - p.params[1]
              const qz = Math.abs(lz) - p.params[2]
              const outX = Math.max(qx, 0), outY = Math.max(qy, 0), outZ = Math.max(qz, 0)
              primD = Math.hypot(outX, outY, outZ) + Math.min(Math.max(qx, qy, qz), 0)
            } else {
              const rx = Math.max(p.params[0], 1e-4)
              const ry = Math.max(p.params[1], 1e-4)
              const rz = Math.max(p.params[2], 1e-4)
              const k0 = Math.hypot(lx / rx, ly / ry, lz / rz)
              primD = (k0 - 1) * Math.min(rx, ry, rz)
            }
            const br = (p.blendRadius && p.blendRadius > 0) ? p.blendRadius : 0.07
            d = sminH(d, primD, br)
          }
          return d
        }
        if (torsoCollPrims.length > 0) {
          const eps = 0.005
          const anchorPos = hairChain[0].position
          for (let i = 1; i < hairChain.length; i++) {
            const cp = hairChain[i].position
            for (let iter = 0; iter < 2; iter++) {
              const d = torsoSDFForHair(cp[0], cp[1], cp[2])
              if (d >= HAIR_BODY_BUFFER) break
              const dxp = torsoSDFForHair(cp[0] + eps, cp[1], cp[2])
              const dxn = torsoSDFForHair(cp[0] - eps, cp[1], cp[2])
              const dyp = torsoSDFForHair(cp[0], cp[1] + eps, cp[2])
              const dyn = torsoSDFForHair(cp[0], cp[1] - eps, cp[2])
              const dzp = torsoSDFForHair(cp[0], cp[1], cp[2] + eps)
              const dzn = torsoSDFForHair(cp[0], cp[1], cp[2] - eps)
              let gx = dxp - dxn, gy = dyp - dyn, gz = dzp - dzn
              const gLen = Math.hypot(gx, gy, gz)
              if (gLen < 1e-6) break
              gx /= gLen; gy /= gLen; gz /= gLen
              // Anti-tunneling — same as cape. If the particle has crossed
              // to the FRONT side of the back-of-head anchor (anchorFwd > 0)
              // and the SDF gradient also points forward (dotFwd > 0), the
              // particle has tunneled through the body and the chest-front
              // gradient would push it further forward forever. Reflect the
              // gradient across the body-forward axis so the push wraps
              // sideways instead, returning the particle to the back of
              // the body. Particles legitimately behind the body have
              // anchorFwd < 0 and skip reflection — gravity drape works.
              const anchorFwd = (cp[0] - anchorPos[0]) * bodyFwd[0]
                              + (cp[1] - anchorPos[1]) * bodyFwd[1]
                              + (cp[2] - anchorPos[2]) * bodyFwd[2]
              if (anchorFwd > 0) {
                const dotFwd = gx * bodyFwd[0] + gy * bodyFwd[1] + gz * bodyFwd[2]
                if (dotFwd > 0) {
                  gx -= 2 * dotFwd * bodyFwd[0]
                  gy -= 2 * dotFwd * bodyFwd[1]
                  gz -= 2 * dotFwd * bodyFwd[2]
                  const gLen2 = Math.hypot(gx, gy, gz)
                  if (gLen2 > 1e-6) { gx /= gLen2; gy /= gLen2; gz /= gLen2 }
                }
              }
              const push = HAIR_BODY_BUFFER - d
              cp[0] += gx * push
              cp[1] += gy * push
              cp[2] += gz * push
            }
          }
        }

        // Hinge constraint — confine hair particles to the plane
        // perpendicular to the head's right axis so hair only swings
        // forward/back/up/down, never sideways. Pure hinge motion at
        // each joint (same architecture as cape).
        {
          const anchorPos = hairChain[0].position
          const hXLen = Math.hypot(hX[0], hX[1], hX[2]) || 1
          const hXn: [number, number, number] = [hX[0]/hXLen, hX[1]/hXLen, hX[2]/hXLen]
          for (let i = 1; i < hairChain.length; i++) {
            const cp = hairChain[i].position
            const dx = cp[0] - anchorPos[0]
            const dy = cp[1] - anchorPos[1]
            const dz = cp[2] - anchorPos[2]
            const dotR = dx * hXn[0] + dy * hXn[1] + dz * hXn[2]
            cp[0] -= dotR * hXn[0]
            cp[1] -= dotR * hXn[1]
            cp[2] -= dotR * hXn[2]
          }
        }
        // Joint-frame encoding (matching cape ribbon-chain): each bone's
        // matrix has translation = particle position, Y axis = direction
        // to next particle, X axis = parallel-transported R.
        const hXLen = Math.hypot(hX[0], hX[1], hX[2]) || 1
        const hXn: [number, number, number] = [hX[0]/hXLen, hX[1]/hXLen, hX[2]/hXLen]
        let prevTangH_x = 0, prevTangH_y = -1, prevTangH_z = 0
        let prevRH_x = hXn[0], prevRH_y = hXn[1], prevRH_z = hXn[2]
        for (let i = 0; i < hairBoneIndices.length; i++) {
          const boneIdx = hairBoneIndices[i]
          const off = boneIdx * 16
          const here: [number, number, number] = hairChain[i].position
          const next: [number, number, number] = (i + 1 < hairChain.length)
            ? hairChain[i + 1].position
            : [here[0], here[1] - hairSegDrop, here[2]]
          let uy0 = next[0] - here[0]
          let uy1 = next[1] - here[1]
          let uy2 = next[2] - here[2]
          const ulen = Math.hypot(uy0, uy1, uy2) || 1
          uy0 /= ulen; uy1 /= ulen; uy2 /= ulen
          let rx0: number, rx1: number, rx2: number
          if (i === 0) {
            const upDotR = uy0 * hXn[0] + uy1 * hXn[1] + uy2 * hXn[2]
            rx0 = hXn[0] - uy0 * upDotR
            rx1 = hXn[1] - uy1 * upDotR
            rx2 = hXn[2] - uy2 * upDotR
            const rlen = Math.hypot(rx0, rx1, rx2) || 1
            rx0 /= rlen; rx1 /= rlen; rx2 /= rlen
          } else {
            const cosA = prevTangH_x * uy0 + prevTangH_y * uy1 + prevTangH_z * uy2
            if (cosA > 0.9999) {
              rx0 = prevRH_x; rx1 = prevRH_y; rx2 = prevRH_z
            } else {
              const ax = prevTangH_y * uy2 - prevTangH_z * uy1
              const ay = prevTangH_z * uy0 - prevTangH_x * uy2
              const az = prevTangH_x * uy1 - prevTangH_y * uy0
              const aLen = Math.hypot(ax, ay, az) || 1
              const axn = ax / aLen, ayn = ay / aLen, azn = az / aLen
              const sinA = aLen
              const dotAR = axn * prevRH_x + ayn * prevRH_y + azn * prevRH_z
              const crX = ayn * prevRH_z - azn * prevRH_y
              const crY = azn * prevRH_x - axn * prevRH_z
              const crZ = axn * prevRH_y - ayn * prevRH_x
              const oneMC = 1 - cosA
              rx0 = prevRH_x * cosA + crX * sinA + axn * dotAR * oneMC
              rx1 = prevRH_y * cosA + crY * sinA + ayn * dotAR * oneMC
              rx2 = prevRH_z * cosA + crZ * sinA + azn * dotAR * oneMC
              const rlen2 = Math.hypot(rx0, rx1, rx2) || 1
              rx0 /= rlen2; rx1 /= rlen2; rx2 /= rlen2
            }
          }
          prevTangH_x = uy0; prevTangH_y = uy1; prevTangH_z = uy2
          prevRH_x = rx0; prevRH_y = rx1; prevRH_z = rx2
          const fz0 = rx1 * uy2 - rx2 * uy1
          const fz1 = rx2 * uy0 - rx0 * uy2
          const fz2 = rx0 * uy1 - rx1 * uy0
          wm[off + 0]  = rx0; wm[off + 1]  = rx1; wm[off + 2]  = rx2; wm[off + 3]  = 0
          wm[off + 4]  = uy0; wm[off + 5]  = uy1; wm[off + 6]  = uy2; wm[off + 7]  = 0
          wm[off + 8]  = fz0; wm[off + 9]  = fz1; wm[off + 10] = fz2; wm[off + 11] = 0
          wm[off + 12] = here[0]; wm[off + 13] = here[1]; wm[off + 14] = here[2]; wm[off + 15] = 1
        }
        // HairLong0..4 are appended contiguously at extendRigWithHair time.
        const hair0Idx = hairBoneIndices[0]
        device.queue.writeBuffer(
          vatHandle.buffer,
          hair0Idx * 64,
          wm.buffer,
          wm.byteOffset + hair0Idx * 16 * 4,
          16 * hairBoneIndices.length * 4,
        )
        invalidateRaymarchCache()
      }

      // Ribbon-chain physics — generic chain simulator used for both
      // side strands and the tail. Locked root + chain particles + torso
      // SDF push (with anti-tunneling) + hinge + parallel transport +
      // VAT upload. Anchor bone, anchor offset, segment drop, and ground
      // clamp are per-call. Body-fwd / torso-SDF state is built once
      // and shared across calls.
      const tailActive = TAIL_FULL && loadout.tail
      if (composer && (STRAND_L_FULL || STRAND_R_FULL || tailActive) && tickShouldRun) {
        const wm = composer.worldMatrices
        const getBoneWorldPos = (boneIdx: number): [number, number, number] => [
          wm[boneIdx * 16 + 12], wm[boneIdx * 16 + 13], wm[boneIdx * 16 + 14],
        ]
        // Body-forward axis from Hips (yaw-only horizontal) — same as cape.
        const bodyRotIdx = (hipsIdx >= 0 ? hipsIdx : (spine1Idx >= 0 ? spine1Idx : spine2Idx))
        let bodyFwdX = 0, bodyFwdZ = 1
        if (bodyRotIdx >= 0) {
          const bm = bodyRotIdx * 16
          bodyFwdX = wm[bm + 8]; bodyFwdZ = wm[bm + 10]
          const bLen = Math.hypot(bodyFwdX, bodyFwdZ)
          if (bLen < 1e-4) { bodyFwdX = 0; bodyFwdZ = 1 } else { bodyFwdX /= bLen; bodyFwdZ /= bLen }
        }
        const bodyFwd: [number, number, number] = [bodyFwdX, 0, bodyFwdZ]
        const bodyRight: [number, number, number] = [bodyFwdZ, 0, -bodyFwdX]   // up × forward

        // (Per-anchor rotation columns are built inside simulateRibbonChain
        // from the call's anchorBoneIdx — no need to pre-compute here.)

        // Torso SDF — shared between all chains in this block. Build
        // once per tick. Per-call body buffer is passed into the helper.
        const TORSO_GROUP = 6
        const torsoCollPrims = persistentPrims.filter(
          p => p.blendGroup === TORSO_GROUP &&
               (p.type === 0 || p.type === 1 || p.type === 3),
        )
        const worldToLocalS = (boneMatStart: number, wx: number, wy: number, wz: number): [number, number, number] => {
          const c0x = wm[boneMatStart],     c0y = wm[boneMatStart + 1], c0z = wm[boneMatStart + 2]
          const c1x = wm[boneMatStart + 4], c1y = wm[boneMatStart + 5], c1z = wm[boneMatStart + 6]
          const c2x = wm[boneMatStart + 8], c2y = wm[boneMatStart + 9], c2z = wm[boneMatStart + 10]
          const tx  = wm[boneMatStart + 12], ty  = wm[boneMatStart + 13], tz  = wm[boneMatStart + 14]
          const s0sq = Math.max(c0x*c0x + c0y*c0y + c0z*c0z, 1e-10)
          const s1sq = Math.max(c1x*c1x + c1y*c1y + c1z*c1z, 1e-10)
          const s2sq = Math.max(c2x*c2x + c2y*c2y + c2z*c2z, 1e-10)
          const dx = wx - tx, dy = wy - ty, dz = wz - tz
          return [
            (c0x * dx + c0y * dy + c0z * dz) / s0sq,
            (c1x * dx + c1y * dy + c1z * dz) / s1sq,
            (c2x * dx + c2y * dy + c2z * dz) / s2sq,
          ]
        }
        const sminS = (a: number, b: number, k: number): number => {
          const kk = Math.max(k, 1e-6)
          const h = Math.max(0, Math.min(1, 0.5 + 0.5 * (b - a) / kk))
          return (b * (1 - h) + a * h) - kk * h * (1 - h)
        }
        const torsoSDF = (wx: number, wy: number, wz: number): number => {
          let d = 1e9
          for (const p of torsoCollPrims) {
            const baseM = p.boneIdx * 16
            const lp = worldToLocalS(baseM, wx, wy, wz)
            const off = p.offsetInBone
            const lx = lp[0] - off[0], ly = lp[1] - off[1], lz = lp[2] - off[2]
            let primD: number
            if (p.type === 0) {
              primD = Math.hypot(lx, ly, lz) - p.params[0]
            } else if (p.type === 1) {
              const qx = Math.abs(lx) - p.params[0]
              const qy = Math.abs(ly) - p.params[1]
              const qz = Math.abs(lz) - p.params[2]
              const outX = Math.max(qx, 0), outY = Math.max(qy, 0), outZ = Math.max(qz, 0)
              primD = Math.hypot(outX, outY, outZ) + Math.min(Math.max(qx, qy, qz), 0)
            } else {
              const rx = Math.max(p.params[0], 1e-4)
              const ry = Math.max(p.params[1], 1e-4)
              const rz = Math.max(p.params[2], 1e-4)
              const k0 = Math.hypot(lx / rx, ly / ry, lz / rz)
              primD = (k0 - 1) * Math.min(rx, ry, rz)
            }
            const br = (p.blendRadius && p.blendRadius > 0) ? p.blendRadius : 0.07
            d = sminS(d, primD, br)
          }
          return d
        }

        // Generic ribbon-chain simulator. Anchor bone determines the
        // rotation source for rest-offset rotation; ground-clamp Y is
        // null for floating chains (strands) or a world-Y floor for
        // ground-aware chains (tail dragging). bodyBuffer is per-call
        // because tail must clear the cape (larger), while strands hang
        // in front of cape (smaller). anchorOnBack flips the
        // anti-tunneling test: cape/tail anchor behind body so tunneled
        // = forward (anchorFwd > 0); strand anchor in front so tunneled
        // = backward (anchorFwd < 0).
        const simulateRibbonChain = (
          chain: NodeParticle[], bones: number[],
          anchorOffset: [number, number, number],
          anchorBoneIdx: number,
          segDrop: number,
          bodyBuffer: number,
          anchorOnBack: boolean,
          groundClampY: number | null,
          extraSphere: { boneIdx: number; radius: number; offsetLocal: [number, number, number] } | null,
          // Back-tilt of the rest direction in anchor-local frame. 0 = pure
          // -Y (straight down). Positive value tilts the rest direction
          // toward anchor-local -Z (away from face) so the chain "pokes
          // outward" instead of dangling against the back of the head.
          restTiltSin: number,
          // Optional wind. World-space X/Z offset applied to each chain
          // particle's rest target, scaled by chain index (tip gets the
          // most drift). Pass {x: 0, z: 0} or null for no wind.
          wind: { x: number; z: number } | null,
        ) => {
          if (chain.length === 0 || anchorBoneIdx < 0) return
          // Per-tick segDrop rebuild — without this the chain's min/max
          // length constraints clamp particles to their original spacing,
          // and the length slider's segDrop change has no effect (same
          // gotcha cape + HairLong solved earlier).
          for (let i = 1; i < chain.length; i++) {
            chain[i].minLength = segDrop * 0.95
            chain[i].maxLength = segDrop * 1.05
          }
          // Build rotation columns for the anchor bone — used to rotate
          // rest offsets from anchor-local into world.
          const am = anchorBoneIdx * 16
          const aX: [number, number, number] = [wm[am + 0], wm[am + 1], wm[am + 2]]
          const aY: [number, number, number] = [wm[am + 4], wm[am + 5], wm[am + 6]]
          const aZ: [number, number, number] = [wm[am + 8], wm[am + 9], wm[am + 10]]
          const rotByAnchor = (v: [number, number, number]): [number, number, number] => [
            v[0] * aX[0] + v[1] * aY[0] + v[2] * aZ[0],
            v[0] * aX[1] + v[1] * aY[1] + v[2] * aZ[1],
            v[0] * aX[2] + v[1] * aY[2] + v[2] * aZ[2],
          ]
          // Anchor lock — anchor bone position + rotated offset every frame.
          const anchorBonePos = getBoneWorldPos(anchorBoneIdx)
          const rotatedAnchor = rotByAnchor(anchorOffset)
          chain[0].position[0] = anchorBonePos[0] + rotatedAnchor[0]
          chain[0].position[1] = anchorBonePos[1] + rotatedAnchor[1]
          chain[0].position[2] = anchorBonePos[2] + rotatedAnchor[2]
          chain[0].prevParentPos[0] = anchorBonePos[0]
          chain[0].prevParentPos[1] = anchorBonePos[1]
          chain[0].prevParentPos[2] = anchorBonePos[2]
          chain[0].initialised = true

          // Mid+tip — rest target rotated by anchor-bone frame, blended
          // toward world-down at the tip so quick body lean doesn't fling
          // segments horizontally.
          // restTiltSin = 0 → straight down (default). Positive value
          // tilts the rest direction toward anchor-local -Z (back-tilt
          // for ponytails so they poke outward from the cranium).
          const tiltSin = restTiltSin
          const tiltCos = Math.sqrt(Math.max(0, 1 - tiltSin * tiltSin))
          for (let i = 1; i < chain.length; i++) {
            const baseOff = chain[i].restOffset
            // Apply tilt: y component scaled by cos, add -Z component
            // proportional to |y| × sin. baseOff usually [0, -segDrop, 0].
            const tiltedOff: [number, number, number] = tiltSin > 1e-4
              ? [baseOff[0], baseOff[1] * tiltCos, baseOff[2] - Math.abs(baseOff[1]) * tiltSin]
              : baseOff
            const bodyOff = rotByAnchor(tiltedOff)
            const drape = Math.min(0.6, (i / chain.length) * 0.75)
            const worldOff: [number, number, number] = [0, baseOff[1], 0]
            let rx = bodyOff[0] * (1 - drape) + worldOff[0] * drape
            let ry = bodyOff[1] * (1 - drape) + worldOff[1] * drape
            let rz = bodyOff[2] * (1 - drape) + worldOff[2] * drape
            if (wind) {
              const k = (i + 1) / chain.length
              rx += wind.x * k
              rz += wind.z * k
            }
            tickNodeParticle(chain[i], chain, getBoneWorldPos, [rx, ry, rz])
          }

          // Torso SDF push-out + anti-tunneling. Anchor reference uses
          // chain[0] (chest-front), so particles legitimately in front of
          // the body have anchorFwd ≈ 0 and skip reflection — only when
          // they wrap PAST the body (anchorFwd > 0 in body-forward sense
          // from chain[0]) does the reflect activate.
          if (torsoCollPrims.length > 0) {
            const eps = 0.005
            const anchorPos = chain[0].position
            for (let i = 1; i < chain.length; i++) {
              const cp = chain[i].position
              for (let iter = 0; iter < 2; iter++) {
                const d = torsoSDF(cp[0], cp[1], cp[2])
                if (d >= bodyBuffer) break
                const dxp = torsoSDF(cp[0] + eps, cp[1], cp[2])
                const dxn = torsoSDF(cp[0] - eps, cp[1], cp[2])
                const dyp = torsoSDF(cp[0], cp[1] + eps, cp[2])
                const dyn = torsoSDF(cp[0], cp[1] - eps, cp[2])
                const dzp = torsoSDF(cp[0], cp[1], cp[2] + eps)
                const dzn = torsoSDF(cp[0], cp[1], cp[2] - eps)
                let gx = dxp - dxn, gy = dyp - dyn, gz = dzp - dzn
                const gLen = Math.hypot(gx, gy, gz)
                if (gLen < 1e-6) break
                gx /= gLen; gy /= gLen; gz /= gLen
                // Tunneling test depends on anchor side. anchorOnBack
                // (cape/tail): tunneled = forward of back = anchorFwd > 0;
                // gradient sign reversal triggers when grad pushes further
                // forward (dotFwd > 0). !anchorOnBack (strands at chest-
                // front): tunneled = behind front = anchorFwd < 0; reflect
                // when grad pushes further backward.
                const anchorFwd = (cp[0] - anchorPos[0]) * bodyFwd[0]
                                + (cp[1] - anchorPos[1]) * bodyFwd[1]
                                + (cp[2] - anchorPos[2]) * bodyFwd[2]
                const tunneled = anchorOnBack ? (anchorFwd > 0) : (anchorFwd < 0)
                if (tunneled) {
                  const dotFwd = gx * bodyFwd[0] + gy * bodyFwd[1] + gz * bodyFwd[2]
                  const wrongDir = anchorOnBack ? (dotFwd > 0) : (dotFwd < 0)
                  if (wrongDir) {
                    gx -= 2 * dotFwd * bodyFwd[0]
                    gy -= 2 * dotFwd * bodyFwd[1]
                    gz -= 2 * dotFwd * bodyFwd[2]
                    const gLen2 = Math.hypot(gx, gy, gz)
                    if (gLen2 > 1e-6) { gx /= gLen2; gy /= gLen2; gz /= gLen2 }
                  }
                }
                const push = bodyBuffer - d
                cp[0] += gx * push; cp[1] += gy * push; cp[2] += gz * push
              }
            }
          }

          // Optional supplementary sphere collider — used for bangs to
          // push out of the head when the head turns (the torso SDF
          // doesn't catch the cranium). offsetLocal is in the sphere
          // bone's local frame; multiplied by the bone rotation columns
          // each frame so the sphere center tracks the bone.
          if (extraSphere && extraSphere.boneIdx >= 0) {
            const ebm = extraSphere.boneIdx * 16
            // Column-major: col0=X axis, col1=Y axis, col2=Z axis.
            const cX: [number, number, number] = [wm[ebm + 0], wm[ebm + 1], wm[ebm + 2]]
            const cY: [number, number, number] = [wm[ebm + 4], wm[ebm + 5], wm[ebm + 6]]
            const cZ: [number, number, number] = [wm[ebm + 8], wm[ebm + 9], wm[ebm + 10]]
            const ePos = getBoneWorldPos(extraSphere.boneIdx)
            const off = extraSphere.offsetLocal
            const sx = ePos[0] + off[0] * cX[0] + off[1] * cY[0] + off[2] * cZ[0]
            const sy = ePos[1] + off[0] * cX[1] + off[1] * cY[1] + off[2] * cZ[1]
            const sz = ePos[2] + off[0] * cX[2] + off[1] * cY[2] + off[2] * cZ[2]
            const r = extraSphere.radius
            for (let i = 1; i < chain.length; i++) {
              const cp = chain[i].position
              const dx = cp[0] - sx, dy = cp[1] - sy, dz = cp[2] - sz
              const dist = Math.hypot(dx, dy, dz)
              if (dist > 1e-6 && dist < r) {
                const k = r / dist
                cp[0] = sx + dx * k; cp[1] = sy + dy * k; cp[2] = sz + dz * k
              }
            }
          }

          // Hinge — confine to the body's fwd-up plane (perpendicular to
          // bodyRight). Chain swings forward/back/down, never sideways.
          for (let i = 1; i < chain.length; i++) {
            const cp = chain[i].position
            const dx = cp[0] - chain[0].position[0]
            const dy = cp[1] - chain[0].position[1]
            const dz = cp[2] - chain[0].position[2]
            const dotR = dx * bodyRight[0] + dy * bodyRight[1] + dz * bodyRight[2]
            cp[0] -= dotR * bodyRight[0]
            cp[1] -= dotR * bodyRight[1]
            cp[2] -= dotR * bodyRight[2]
          }

          // Ground clamp — particles can't sink below the floor. Used by
          // tail (drags floor when long); strands skip this since they
          // hang above the ground anyway.
          if (groundClampY !== null) {
            for (let i = 1; i < chain.length; i++) {
              if (chain[i].position[1] < groundClampY) {
                chain[i].position[1] = groundClampY
              }
            }
          }

          // Parallel-transport joint frame encoding — same as HairLong.
          let prevTang_x = 0, prevTang_y = -1, prevTang_z = 0
          let prevR_x = bodyRight[0], prevR_y = bodyRight[1], prevR_z = bodyRight[2]
          for (let i = 0; i < bones.length; i++) {
            const off = bones[i] * 16
            const here: [number, number, number] = chain[i].position
            const next: [number, number, number] = (i + 1 < chain.length)
              ? chain[i + 1].position
              : [here[0], here[1] - segDrop, here[2]]
            let uy0 = next[0] - here[0], uy1 = next[1] - here[1], uy2 = next[2] - here[2]
            const ulen = Math.hypot(uy0, uy1, uy2) || 1
            uy0 /= ulen; uy1 /= ulen; uy2 /= ulen
            let rx0: number, rx1: number, rx2: number
            if (i === 0) {
              const upDotR = uy0 * bodyRight[0] + uy1 * bodyRight[1] + uy2 * bodyRight[2]
              rx0 = bodyRight[0] - uy0 * upDotR
              rx1 = bodyRight[1] - uy1 * upDotR
              rx2 = bodyRight[2] - uy2 * upDotR
              const rlen = Math.hypot(rx0, rx1, rx2) || 1
              rx0 /= rlen; rx1 /= rlen; rx2 /= rlen
            } else {
              const cosA = prevTang_x * uy0 + prevTang_y * uy1 + prevTang_z * uy2
              if (cosA > 0.9999) {
                rx0 = prevR_x; rx1 = prevR_y; rx2 = prevR_z
              } else {
                const ax = prevTang_y * uy2 - prevTang_z * uy1
                const ay = prevTang_z * uy0 - prevTang_x * uy2
                const az = prevTang_x * uy1 - prevTang_y * uy0
                const aLen = Math.hypot(ax, ay, az) || 1
                const axn = ax / aLen, ayn = ay / aLen, azn = az / aLen
                const sinA = aLen
                const dotAR = axn * prevR_x + ayn * prevR_y + azn * prevR_z
                const crX = ayn * prevR_z - azn * prevR_y
                const crY = azn * prevR_x - axn * prevR_z
                const crZ = axn * prevR_y - ayn * prevR_x
                const oneMC = 1 - cosA
                rx0 = prevR_x * cosA + crX * sinA + axn * dotAR * oneMC
                rx1 = prevR_y * cosA + crY * sinA + ayn * dotAR * oneMC
                rx2 = prevR_z * cosA + crZ * sinA + azn * dotAR * oneMC
                const rlen2 = Math.hypot(rx0, rx1, rx2) || 1
                rx0 /= rlen2; rx1 /= rlen2; rx2 /= rlen2
              }
            }
            prevTang_x = uy0; prevTang_y = uy1; prevTang_z = uy2
            prevR_x = rx0; prevR_y = rx1; prevR_z = rx2
            const fz0 = rx1 * uy2 - rx2 * uy1
            const fz1 = rx2 * uy0 - rx0 * uy2
            const fz2 = rx0 * uy1 - rx1 * uy0
            wm[off + 0]  = rx0; wm[off + 1]  = rx1; wm[off + 2]  = rx2; wm[off + 3]  = 0
            wm[off + 4]  = uy0; wm[off + 5]  = uy1; wm[off + 6]  = uy2; wm[off + 7]  = 0
            wm[off + 8]  = fz0; wm[off + 9]  = fz1; wm[off + 10] = fz2; wm[off + 11] = 0
            wm[off + 12] = here[0]; wm[off + 13] = here[1]; wm[off + 14] = here[2]; wm[off + 15] = 1
          }
          // VAT upload for this side's contiguous bones.
          device.queue.writeBuffer(
            vatHandle.buffer,
            bones[0] * 64,
            wm.buffer,
            wm.byteOffset + bones[0] * 16 * 4,
            16 * bones.length * 4,
          )
        }

        // Floor for tail clamp — same construction as cape's ground.
        const lFootY_t = lFootIdx >= 0 ? wm[lFootIdx * 16 + 13] : 0
        const rFootY_t = rFootIdx >= 0 ? wm[rFootIdx * 16 + 13] : 0
        const tailGroundY = Math.min(lFootY_t, rFootY_t) + 0.01

        // Body buffer per chain. Strand: 0.10 — small cross-section in
        // front of cape, doesn't need to clear it. Tail: 0.16 — must sit
        // outside cape's outer face (cape buffer 0.075 + cape halfZ 0.025
        // = 0.10 from torso; tail body-thickness ~0.045 + slop ~0.015 →
        // 0.16 keeps tail OUTSIDE cape rather than coinciding).
        // Bangs collide against a head sphere (radius matches head halfX/Z
        // ≈ 0.165, +small clearance) so they don't tunnel through cheeks
        // when head turns. Sphere center at head ellipsoid Y=0.12 in
        // head-local. Tail has no extra sphere — torso SDF covers it.
        const headSphere = { boneIdx: headIdx, radius: 0.18, offsetLocal: [0, 0.12, 0] as [number, number, number] }
        if (STRAND_L_FULL) simulateRibbonChain(strandLChain, strandLBones, STRAND_ANCHOR_OFFSET_L, headIdx, STRAND_SEG_DROP * strandLengthScale, 0.10, false, null, headSphere, 0, null)
        if (STRAND_R_FULL) simulateRibbonChain(strandRChain, strandRBones, STRAND_ANCHOR_OFFSET_R, headIdx, STRAND_SEG_DROP * strandLengthScale, 0.10, false, null, headSphere, 0, null)
        if (tailActive)    simulateRibbonChain(tailChain,    tailBones,    TAIL_ANCHOR_OFFSET,     hipsIdx,    TAIL_SEG_DROP * tailLengthScale, 0.16, true,  tailGroundY, null, 0, null)
        invalidateRaymarchCache()
      }

      // (Strand-tip spring system removed — replaced by chain-driven
      // side strands above.)

      // Grenade pendulum chains — replaces the prior spring system. Each
      // grenade is a single NodeParticle parented (chain-wise) to Hips
      // with a belt-relative rest offset rotated by Hips' frame, so the
      // grenade swings naturally with body lean / hip rotation. After
      // chain integration we push each grenade out of the torso SDF
      // (group 6) so it can't penetrate the body during fast motion.
      if (composer && grenadeEntries.length > 0 && tickShouldRun) {
        const wm = composer.worldMatrices
        const getBoneWorldPosG = (boneIdx: number): [number, number, number] => [
          wm[boneIdx * 16 + 12], wm[boneIdx * 16 + 13], wm[boneIdx * 16 + 14],
        ]
        // Hips rotation columns — rest offsets live in Hips-local.
        const hm = hipsIdx * 16
        const hX0 = wm[hm + 0], hY0 = wm[hm + 4], hZ0 = wm[hm + 8]
        const hX1 = wm[hm + 1], hY1 = wm[hm + 5], hZ1 = wm[hm + 9]
        const hX2 = wm[hm + 2], hY2 = wm[hm + 6], hZ2 = wm[hm + 10]
        const rotByHips = (v: [number, number, number]): [number, number, number] => [
          v[0] * hX0 + v[1] * hY0 + v[2] * hZ0,
          v[0] * hX1 + v[1] * hY1 + v[2] * hZ1,
          v[0] * hX2 + v[1] * hY2 + v[2] * hZ2,
        ]
        // Build a one-off torso SDF for grenade collision. Reuses blendGroup
        // 6 (torso + shoulders + hips). Buffer is small — grenades sit ON
        // the belt at ~10cm Hips offset, just clearing hip/leg surfaces.
        const torsoCollPrimsG = persistentPrims.filter(
          p => p.blendGroup === 6 && (p.type === 0 || p.type === 1 || p.type === 3),
        )
        const w2lG = (mStart: number, wx: number, wy: number, wz: number): [number, number, number] => {
          const c0x = wm[mStart],     c0y = wm[mStart + 1], c0z = wm[mStart + 2]
          const c1x = wm[mStart + 4], c1y = wm[mStart + 5], c1z = wm[mStart + 6]
          const c2x = wm[mStart + 8], c2y = wm[mStart + 9], c2z = wm[mStart + 10]
          const tx  = wm[mStart + 12], ty  = wm[mStart + 13], tz  = wm[mStart + 14]
          const s0sq = Math.max(c0x*c0x + c0y*c0y + c0z*c0z, 1e-10)
          const s1sq = Math.max(c1x*c1x + c1y*c1y + c1z*c1z, 1e-10)
          const s2sq = Math.max(c2x*c2x + c2y*c2y + c2z*c2z, 1e-10)
          const dx = wx - tx, dy = wy - ty, dz = wz - tz
          return [
            (c0x * dx + c0y * dy + c0z * dz) / s0sq,
            (c1x * dx + c1y * dy + c1z * dz) / s1sq,
            (c2x * dx + c2y * dy + c2z * dz) / s2sq,
          ]
        }
        const sminG = (a: number, b: number, k: number): number => {
          const kk = Math.max(k, 1e-6)
          const h = Math.max(0, Math.min(1, 0.5 + 0.5 * (b - a) / kk))
          return (b * (1 - h) + a * h) - kk * h * (1 - h)
        }
        const torsoSDFG = (wx: number, wy: number, wz: number): number => {
          let d = 1e9
          for (const p of torsoCollPrimsG) {
            const baseM = p.boneIdx * 16
            const lp = w2lG(baseM, wx, wy, wz)
            const off = p.offsetInBone
            const lx = lp[0] - off[0], ly = lp[1] - off[1], lz = lp[2] - off[2]
            let primD: number
            if (p.type === 0) primD = Math.hypot(lx, ly, lz) - p.params[0]
            else if (p.type === 1) {
              const qx = Math.abs(lx) - p.params[0], qy = Math.abs(ly) - p.params[1], qz = Math.abs(lz) - p.params[2]
              primD = Math.hypot(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qy, qz), 0)
            } else {
              const rx = Math.max(p.params[0], 1e-4), ry = Math.max(p.params[1], 1e-4), rz = Math.max(p.params[2], 1e-4)
              primD = (Math.hypot(lx / rx, ly / ry, lz / rz) - 1) * Math.min(rx, ry, rz)
            }
            const br = (p.blendRadius && p.blendRadius > 0) ? p.blendRadius : 0.07
            d = sminG(d, primD, br)
          }
          return d
        }
        const GRENADE_BODY_BUFFER = 0.04
        const eps = 0.005
        for (const e of grenadeEntries) {
          // Tick the pendulum particle. parentRef=hipsIdx, rest target =
          // Hips world + rotByHips(restOffsetLocal). NodeParticle handles
          // one-frame-stale parent reads + distance clamp.
          tickNodeParticle(e.particle, [], getBoneWorldPosG, rotByHips(e.restOffsetLocal))
          // Body SDF push-out — grenade can't penetrate the torso.
          const cp = e.particle.position
          for (let iter = 0; iter < 2; iter++) {
            const d = torsoSDFG(cp[0], cp[1], cp[2])
            if (d >= GRENADE_BODY_BUFFER) break
            const dxp = torsoSDFG(cp[0] + eps, cp[1], cp[2])
            const dxn = torsoSDFG(cp[0] - eps, cp[1], cp[2])
            const dyp = torsoSDFG(cp[0], cp[1] + eps, cp[2])
            const dyn = torsoSDFG(cp[0], cp[1] - eps, cp[2])
            const dzp = torsoSDFG(cp[0], cp[1], cp[2] + eps)
            const dzn = torsoSDFG(cp[0], cp[1], cp[2] - eps)
            let gx = dxp - dxn, gy = dyp - dyn, gz = dzp - dzn
            const gLen = Math.hypot(gx, gy, gz)
            if (gLen < 1e-6) break
            gx /= gLen; gy /= gLen; gz /= gLen
            const push = GRENADE_BODY_BUFFER - d
            cp[0] += gx * push; cp[1] += gy * push; cp[2] += gz * push
          }
          // Override the bone's world translation. Rotation untouched —
          // primitive stays aligned with Hips' orientation.
          const off = e.boneIdx * 16
          wm[off + 12] = cp[0]
          wm[off + 13] = cp[1]
          wm[off + 14] = cp[2]
          device.queue.writeBuffer(
            vatHandle.buffer,
            e.boneIdx * 64,
            wm.buffer,
            wm.byteOffset + off * 4,
            64,
          )
        }
        invalidateRaymarchCache()
      }
      // Camera stays fixed — no per-frame Hips tracking. Scale is
      // correct via the Hips-relative envelope; if a jump animation
      // translates the character above the frame momentarily, that's
      // acceptable since we're no longer baking atlas cells. Fit sets
      // camera.target once to the rest Hips position.
      camera.update()
      {
        const c = cacheDimsFor(spriteMode)
        camera.pixelSnapView(c.w, c.h)
      }
      // Commit the tick tracker now that all anim+physics blocks have
      // observed the gate. Next frame compares against these values.
      if (tickShouldRun) {
        lastSecondaryFrame = frameIdx
        lastSecondaryElapsed = elapsed
        lastSecondaryRestPose = effectiveRestPose
      }
      // When the composer is active, the shader reads slot 0 (composer
      // writes current frame there each tick). Without composer (VAT1),
      // use frameIdx directly against the pre-baked world-matrix table.
      const drawFrameIdx = composer ? 0 : frameIdx

      const encoder = device.createCommandEncoder()

      // Raymarch cache refresh — happens BEFORE the scene pass. If the
      // cache fingerprint matches last frame, skip the march entirely
      // and blit inside the scene pass below. For an animating character
      // this re-marches every frame (AABB diff catches motion); for a
      // paused character at a fixed camera, zero march cost.
      {
        // Update the ephemeral VFX list BEFORE the diff so any spawned/
        // expired primitive shows up in the array length comparison.
        vfxSystem.update(elapsed)
        const nowPrims = currentAllPrims(elapsed)

        // AABB diff: "did anything visible actually move?" catches anim,
        // proportion slider, primitive count changes, expressions, anim
        // switch. Camera motion + palette edits bump cacheVersion via
        // explicit invalidate calls.
        if (raymarchSceneChanged(nowPrims)) invalidateRaymarchCache()

        if (raymarchCacheVersion !== raymarchCacheApplied) {
          const eyeR: [number, number, number] = [camera.position[0], camera.position[1], camera.position[2]]
          // Front-to-back sort so the shader's per-primitive occlusion
          // skip kicks in early. Only pays on cache miss.
          const sorted = nowPrims.slice()
          sorted.sort((a, b) => {
            const sa = primWorldSphere(a)
            const sb = primWorldSphere(b)
            const dax = sa.cx - eyeR[0], day = sa.cy - eyeR[1], daz = sa.cz - eyeR[2]
            const dbx = sb.cx - eyeR[0], dby = sb.cy - eyeR[1], dbz = sb.cz - eyeR[2]
            return (dax*dax + day*day + daz*daz) - (dbx*dbx + dby*dby + dbz*dbz)
          })
          raymarch.setPrimitives(sorted)
          raymarch.setTime(elapsed)
          // pxPerM uses the SPRITE-cell height (cache dim), not canvas —
          // the raymarch writes into the cache texture which is sprite-sized.
          const cacheH = cacheDimsFor(spriteMode).h
          const pxPerM = cacheH / (2 * camera.orthoSize)
          raymarch.setPxPerM(pxPerM)
          raymarch.marchIntoCache(encoder, camera.view, camera.projection, eyeR, drawFrameIdx)
          raymarchCacheApplied = raymarchCacheVersion
          snapshotRaymarchScene(nowPrims)
        }
      }

      // Pass 1: skeleton → MRT (color, normal, depth). Clear alpha=0 on
      // color so outline pass can detect background via alpha threshold.
      const scenePass = encoder.beginRenderPass({
        colorAttachments: [
          { view: targets.sceneView!,    loadOp: 'clear', storeOp: 'store', clearValue: { r: 0,   g: 0,   b: 0,   a: 0 } },
          { view: targets.normalView!,   loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1.0, a: 0 } },
          { view: targets.depthVizView!, loadOp: 'clear', storeOp: 'store', clearValue: { r: 1,   g: 0,   b: 0,   a: 0 } },
        ],
        depthStencilAttachment: {
          view: targets.sceneDepthView!,
          depthLoadOp: 'clear',
          depthStoreOp: 'store',
          depthClearValue: 1.0,
          stencilLoadOp: 'clear',
          stencilStoreOp: 'store',
          stencilClearValue: 0,
        },
      })
      // Scene pass outputs = blit from the raymarch cache framebuffer.
      // Two offsets stack here:
      //   (1) CENTER the sprite-sized cache in the full SCREEN_SIZE viewport
      //       so the sprite appears at its actual pixel size surrounded by
      //       SNES-screen context.
      //   (2) PAN offset — how many pixels the character has moved since
      //       the cache was filled (camera translation delta in pixels).
      // Pixel-copy invariant means the blit is always integer-pixel aligned.
      {
        const cache = cacheDimsFor(spriteMode)
        const pxPerM = cache.h / (2 * camera.orthoSize)
        const dxM = camera.view[12] - lastAabbView[12]
        const dyM = camera.view[13] - lastAabbView[13]
        const panOffsetX = -Math.round(dxM * pxPerM)
        const panOffsetY =  Math.round(dyM * pxPerM)
        const centerX = Math.round((canvas.width  - cache.w) / 2)
        const centerY = Math.round((canvas.height - cache.h) / 2)
        raymarch.blitCacheToPass(scenePass, [centerX + panOffsetX, centerY + panOffsetY])
      }
      scenePass.end()

      // Face paint-on: project the head joint to screen pixels so the
      // outline shader knows where to stamp pupil dots. Camera is tuned
      // for the LOD sprite cell, so NDC maps to cell pixels; blit centers
      // the cell in the SCREEN_SIZE canvas.
      if (headIdx >= 0 && composer) {
        const m = composer.worldMatrices
        const hBase = headIdx * 16
        // Anchor at the FRONT of the head, not the head joint center.
        // Head's head-local frame: origin at joint, +Y up, +Z face-forward.
        // Offset (0, headYOff, headZHalf) lands on the visible face.
        // Using the center depth (0,0,0) caused eyes to paint through the
        // back of the head when orbited, because head center depth sits
        // in the middle of the pass-band tolerance. Face-front is on one
        // side of the head's depth extent so its depth uniquely identifies
        // "surface that is actually the face."
        const v = camera.view, p = camera.projection
        const cache = cacheDimsFor(spriteMode)
        const centerX = (canvas.width  - cache.w) / 2
        const centerY = (canvas.height - cache.h) / 2
        // Project a head-LOCAL offset to (screenX, screenY, NDC depth).
        // Each feature (left eye, right eye, mouth) projects its own world
        // point so the paint tracks the face surface through any head
        // orientation — including upside-down backflips.
        function projHeadLocal(ox: number, oy: number, oz: number): [number, number, number] {
          const wx = m[hBase + 0]*ox + m[hBase + 4]*oy + m[hBase + 8]*oz  + m[hBase + 12]
          const wy = m[hBase + 1]*ox + m[hBase + 5]*oy + m[hBase + 9]*oz  + m[hBase + 13]
          const wz = m[hBase + 2]*ox + m[hBase + 6]*oy + m[hBase + 10]*oz + m[hBase + 14]
          const cx = p[0]*(v[0]*wx+v[4]*wy+v[8]*wz+v[12]) + p[4]*(v[1]*wx+v[5]*wy+v[9]*wz+v[13]) + p[8]*(v[2]*wx+v[6]*wy+v[10]*wz+v[14]) + p[12]*(v[3]*wx+v[7]*wy+v[11]*wz+v[15])
          const cy = p[1]*(v[0]*wx+v[4]*wy+v[8]*wz+v[12]) + p[5]*(v[1]*wx+v[5]*wy+v[9]*wz+v[13]) + p[9]*(v[2]*wx+v[6]*wy+v[10]*wz+v[14]) + p[13]*(v[3]*wx+v[7]*wy+v[11]*wz+v[15])
          const cz = p[2]*(v[0]*wx+v[4]*wy+v[8]*wz+v[12]) + p[6]*(v[1]*wx+v[5]*wy+v[9]*wz+v[13]) + p[10]*(v[2]*wx+v[6]*wy+v[10]*wz+v[14]) + p[14]*(v[3]*wx+v[7]*wy+v[11]*wz+v[15])
          const cw = p[3]*(v[0]*wx+v[4]*wy+v[8]*wz+v[12]) + p[7]*(v[1]*wx+v[5]*wy+v[9]*wz+v[13]) + p[11]*(v[2]*wx+v[6]*wy+v[10]*wz+v[14]) + p[15]*(v[3]*wx+v[7]*wy+v[11]*wz+v[15])
          const ndcX = cx / cw, ndcY = cy / cw, ndcZ = cz / cw
          return [centerX + (ndcX * 0.5 + 0.5) * cache.w, centerY + (1 - (ndcY * 0.5 + 0.5)) * cache.h, ndcZ]
        }

        // Head-local feature points. +Y up, +Z face-forward.
        // Chibi head: cube center at (0, 0.12, 0), extents ~(0.19, 0.21, 0.19).
        // Face surface is at Z≈0.19; eyes slightly inside (0.17), upper face.
        //
        // Mario-eye spacing is LOD-invariant: we want 1 px of skin between
        // the pupil pillars (→ anchor separation = 2 px) regardless of
        // sprite resolution. Approach: project the face center + one eye
        // to get a screen-space "head right" direction, normalize it, then
        // place both anchors ±1 px from the rounded face center along that
        // direction. Rotation of the head carries the eyes with it.
        // Anime proportions — eye line at the vertical centre of the head
        // (50% down) rather than the upper third. Chibi convention has a
        // big forehead with eyes high; anime convention puts eyes mid-face.
        const faceCenterPt = projHeadLocal(0.000, 0.115, 0.17)
        const leftRaw      = projHeadLocal(0.055, 0.115, 0.17)
        const dxAxis = leftRaw[0] - faceCenterPt[0]
        const dyAxis = leftRaw[1] - faceCenterPt[1]
        const axisLen = Math.hypot(dxAxis, dyAxis) || 1
        const ux = dxAxis / axisLen
        const uy = dyAxis / axisLen
        const fcRx = Math.round(faceCenterPt[0])
        const fcRy = Math.round(faceCenterPt[1])
        // eyeSpacingPx scales the unit direction so each anchor sits
        // eyeSpacingPx px from the face centre along the head-right axis.
        const leftEyePt:  [number, number, number] = [
          fcRx + ux * eyeSpacingPx,
          fcRy + uy * eyeSpacingPx,
          faceCenterPt[2],
        ]
        const rightEyePt: [number, number, number] = [
          fcRx - ux * eyeSpacingPx,
          fcRy - uy * eyeSpacingPx,
          faceCenterPt[2],
        ]
        // Mouth at ~80% down the face — between eye line (centre) and chin.
        const mouthPt = projHeadLocal(0.0, 0.000, 0.19)

        // Half-sizes per LOD.
        const pupilHalf: [number, number] = [EYE_PUPIL[spriteMode][2], EYE_PUPIL[spriteMode][3]]
        const ws = EYE_WHITE[spriteMode]
        const whiteHalf: [number, number] = [ws[0], ws[1]]
        const mouthHalf: [number, number] = [MOUTH_GLYPH[spriteMode][1], MOUTH_GLYPH[spriteMode][2]]
        const whiteCol: [number, number, number, number] = [
          WHITE_COLOR[0], WHITE_COLOR[1], WHITE_COLOR[2],
          whiteHalf[0] > 0 ? 1.0 : 0.0,
        ]

        const fx = camera.target[0] - camera.position[0]
        const fy = camera.target[1] - camera.position[1]
        const fz = camera.target[2] - camera.position[2]
        const fl = Math.hypot(fx, fy, fz) || 1
        outline.setViewForward(fx / fl, fy / fl, fz / fl)

        // Point-light infrastructure stays armed but no lights are
        // active by default — clean two-tone cel from ambient + key.
        // Future VFX (muzzle flashes, flares, explosions) will spawn
        // transient point lights into slots 0..3 for their lifetime.
        // invViewProj still pushed each frame so reconstruction is
        // ready the moment a light is added.
        const viewProjScratch = scratchVP
        mat4.multiply(viewProjScratch, camera.projection, camera.view)
        mat4.invert(scratchInvVP, viewProjScratch)
        outline.setInvViewProj(scratchInvVP)
        outline.setNumPointLights(0)

        // Face stamp — anchors + colours on the legacy setFacePaint path,
        // style / state on the new setFaceStyle. Mouth colour always
        // enabled (.a=1); shader gates mouth on mouthStyle != 0.
        const eyePupilCol: [number, number, number, number] = [0.06, 0.05, 0.10, 1]
        const eyeWhiteCol: [number, number, number, number] = [0.96, 0.94, 0.90, 1]
        const mouthCol:    [number, number, number, number] = [0.55, 0.20, 0.25, 1]
        outline.setFacePaint(
          leftEyePt, rightEyePt, mouthPt,
          pupilHalf, whiteHalf, mouthHalf,
          eyePupilCol, eyeWhiteCol, mouthCol,
        )

        // Time-driven auto-blink — skipped when the chosen expression is
        // already 'blink' (user asked for sticky closed eyes).
        blinkTimer += stats?.dt ?? 0
        const cycle = BLINK_PERIOD + BLINK_DURATION
        if (blinkTimer >= cycle) blinkTimer -= cycle
        const autoBlink = currentExpression === 'blink' ? 1 : (blinkTimer > BLINK_PERIOD ? 1 : 0)

        // Pixel-stamp face style follows the expression button state,
        // with J / ,. overrides replacing eye / mouth respectively.
        // Fallback to neutral if unmapped.
        const faceStyle = FACE_STYLES[currentExpression] ?? FACE_STYLES.neutral
        const effectiveEye   = eyeStyleOverride   ?? faceStyle.eye
        const effectiveMouth = mouthStyleOverride ?? faceStyle.mouth
        const eyeStyleId = EYE_STYLES.indexOf(effectiveEye)
        const mouthStyleId = MOUTH_STYLES.indexOf(effectiveMouth)
        const glow = 0.5 + 0.5 * Math.sin(elapsed * 3)
        outline.setFaceStyle(eyeStyleId, mouthStyleId, autoBlink, glow)
        if (faceStyle.accent) {
          outline.setEyeAccent([faceStyle.accent[0], faceStyle.accent[1], faceStyle.accent[2], 1])
        } else if (effectiveEye === 'goggles') {
          outline.setEyeAccent([0.18, 0.55, 1.0, 1])
        } else if (effectiveEye === 'glowing') {
          outline.setEyeAccent([1.0, 0.35, 0.15, 1])
        } else {
          outline.setEyeAccent([0, 0, 0, 0])
        }
      }

      // Pass 2: outline shader reads sceneTex → writes canvas with NAVY ring.
      const canvasView = gpu.context.getCurrentTexture().createView()
      outline.run(encoder, canvasView)

      device.queue.submit([encoder.finish()])

      const mode = SPRITE_MODES[spriteMode]
      statsEl.textContent = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Joints: ${rig.length}   Frame: ${frameIdx}/${loadedVAT.numFrames}`,
        `Anim: ${animations[animIdx].name}   [M] switch (${animations.length} loaded)`,
        `Sprite size: ${mode.label}`,
        `  canvas buffer: ${canvas.width}×${canvas.height} (CSS upscaled to window)`,
        ``,
        `[1] 24²   [2] 32²   [3] 48²   [4] debug 128²   proportion: ${currentProportion}`,
        `[V] view: ${viewMode}   [D] depth outline: ${depthOutlineOn ? 'on' : 'off'}   [L] lighting: ${lightingMode ? 'on' : 'off'}   [T] rest pose: ${restPose ? 'on' : 'off'}   [K] naked: ${nudeMode ? 'on' : 'off'}`,
        `expression: ${currentExpression}   [ / ] eye spacing: ${eyeSpacingPx}px   [J] eye style: ${eyeStyleOverride ?? '(emotion)'}`,
        `drag = orbit   [T] rest pose`,
        `[Space] swipe   [X] star   [Z] flash   [N] bolt   [B] beam   VFX: ${vfxSystem.count()}`,
        `drag = orbit   [F] preview: ${previewMode}`,
      ].join('\n')
    }

    loop.start()

    window.addEventListener('beforeunload', () => { cleanup(); loop.stop() })
  } catch (err) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU Error: ${err instanceof Error ? err.message : String(err)}`
    console.error(err)
  }
}

main()
