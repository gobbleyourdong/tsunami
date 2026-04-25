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
  extendRigWithAccessories,
  extendLocalMatsWithAccessories,
  extendRigWithHair,
  extendLocalMatsWithHair,
  extendRigWithBodyParts,
  extendLocalMatsWithBodyParts,
  DEFAULT_CAPE_PARTS,
  DEFAULT_BOB_HAIR,
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
import { mat4 } from '../src/math/vec'
import { createRaymarchRenderer, type RaymarchPrimitive } from '../src/character3d/raymarch_renderer'
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
  debug: { label: '256² debug / SNES full',           w: 256, h: 256 },
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

    let spriteMode: SpriteMode = 'sz32'
    // Preview framing: 'scene' canvases at SNES full-res (256²) and
    // centers the sprite cell in it — you see the sprite at its pixel
    // size against screen context. 'framed' canvases match the cache
    // size so all render pixels are visible.
    type PreviewMode = 'scene' | 'framed'
    let previewMode: PreviewMode = 'scene'
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
          // Bob hair shipped with the engine; characters can override by
          // passing a different list. Spring-driven jiggle applied below.
          vat.rig = extendRigWithHair(vat.rig, DEFAULT_BOB_HAIR)
          vat.localMats = extendLocalMatsWithHair(vat.localMats, vat.numFrames, vat.numJoints, DEFAULT_BOB_HAIR)
          vat.numJoints = vat.rig.length
          // Body parts + cape + grenades all share the BodyPart shape.
          // Cape gets node-particle chain motion; grenades get per-grenade
          // springs (jiggle on running); body parts (breasts/hippads) stay
          // rest-pose unless they get their own springs in a future tick.
          const bodyAndExtras = [...DEFAULT_BODY_PARTS, ...DEFAULT_CAPE_PARTS, ...DEFAULT_GRENADE_BELT]
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
    const hipsIdx = rig.findIndex((j) => j.name === 'Hips')
    const characterParams = defaultCharacterParams(loadedVAT.numJoints)

    // --- Proportion system: group joints by body part, apply scale per group. ---
    // Groups mirror typical character-editor UI knobs. Each joint belongs to
    // exactly one group; scale propagates to its descendants via hierarchy
    // composition in the retarget composer.
    const GROUP_PATTERNS: Record<string, RegExp> = {
      // Head group includes face features — chibi-scaling the head must
      // grow the eyes/mouth/nose too, otherwise a huge head with tiny
      // features looks wrong. Face joints are parented to Head so their
      // position already inherits head scale through col3 propagation;
      // adding them to this group scales their OWN display cubes too.
      head:  /^(Head|HeadTop_End|Neck|LeftEye|RightEye|LeftPupil|RightPupil|Mouth|Nose|Hair(Top|Back|LeftSide|RightSide|Fringe))$/,
      torso: /^(Spine|Spine1|Spine2|Hips|Left(Shoulder)|Right(Shoulder))$/,
      arms:  /(LeftArm|RightArm|LeftForeArm|RightForeArm|LeftHand|RightHand)/,
      legs:  /(LeftUpLeg|LeftLeg|LeftFoot|RightUpLeg|RightLeg|RightFoot|LeftToe|RightToe)/,
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
      // Alucard-tier SotN realistic: adult proportions, head small, legs
      // long. 1:1 Mixamo with mild anime-lengthening of the legs.
      realistic: {
        head:  [1.0, 0.95, 1.0],
        torso: [1.0, 1.0,  1.0],
        arms:  [1.0, 1.05, 1.0],
        legs:  [1.0, 1.10, 1.0],
        bust: 0.0, hips: 0.0,
      },
      // SNES anime-RPG (Chrono / FF6 / Secret of Mana): head prominent but
      // not dominant, limbs slightly shortened, width unchanged.
      stylized: {
        head:  [1.0, 1.35, 1.0],
        torso: [1.0, 0.9,  1.0],
        arms:  [1.0, 0.85, 1.0],
        legs:  [1.0, 0.82, 1.0],
        bust: 0.0, hips: 0.0,
      },
      // SNES-chibi: head stays ROUND (uniform 1.0, no Y-stretch → no
      // cone-head); the body is squashed HARD so the head dominates by
      // ratio, not by stretching. Width unchanged across the character.
      chibi: {
        head:  [1.0, 1.0, 1.0],
        torso: [1.0, 0.55, 1.0],
        arms:  [1.0, 0.5,  1.0],
        legs:  [1.0, 0.3,  1.0],
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
      fitCameraToCharacter()
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
      return serializeCharacterSpec({
        name:        nameInput.value || 'unnamed',
        archetype:   ARCHETYPE_CHIBI,
        proportions: { ...currentScales },
        palette:     paletteEntries,
        // Face/hair/body/accessories are module-constant defaults today;
        // dump them so the spec round-trips. Runtime-mutable arrays would
        // slot in here once the rig-extend path accepts per-character
        // overrides.
        face:        DEFAULT_FACE,
        hair:        DEFAULT_HAIR,
        bodyParts:   DEFAULT_BODY_PARTS,
        accessories: DEFAULT_ACCESSORIES,
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
    // 5-segment cape: Cape0 (locked anchor at shoulder) → Cape4 (tip).
    // Each particle index matches the bone index in capeBoneIndices.
    const capeBoneIndices: number[] = []
    for (let i = 0; i < 5; i++) {
      const idx = rig.findIndex((j) => j.name === `Cape${i}`)
      if (idx >= 0) capeBoneIndices.push(idx)
    }
    const CAPE_SEG_DROP = 0.18   // Y drop per segment (matches DEFAULT_CAPE_PARTS)
    const CAPE_HAS_FULL_CHAIN = capeBoneIndices.length === 5 && spine2Idx >= 0

    // Particle 0 is the LOCKED anchor at the shoulder (Spine2 + rotated
    // offset). Particles 1..4 chain via node-particle physics (one-frame-
    // stale parent reads + distance clamp). The first VISIBLE segment
    // spans particle[0] → particle[1] hanging DOWN from the shoulder
    // anchor, eliminating the awkward up-bend the previous architecture
    // had between Spine2 and Cape0.
    const capeChain: NodeParticle[] = !CAPE_HAS_FULL_CHAIN ? [] : [
      // Cape0 — locked anchor. restOffset is matched in the lock code below.
      createNodeParticle({
        parentRef: spine2Idx, parentKind: 'bone',
        restOffset: [0, 0.10, -0.20],
        restLength: 0.22,
      }),
      // Cape1..4 — chain physics, hanging straight down from previous.
      createNodeParticle({ parentRef: 0, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 1, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 2, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
      createNodeParticle({ parentRef: 3, parentKind: 'particle', restOffset: [0, -CAPE_SEG_DROP, 0], restLength: CAPE_SEG_DROP }),
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
    type SpringEntry = { boneIdx: number; spring: SecondarySpring }
    const springEntries: SpringEntry[] = []
    // Hair (HairBob) is now LOCKED to the head — single-primitive bob has
    // no "tip" to swing, so we keep it rigidly attached. Future longer-
    // hair chains will revisit with root-locked + tip-springs.
    if (grenadeLIdx >= 0) springEntries.push({ boneIdx: grenadeLIdx, spring: createSecondarySpring([0,0,0], { stiffness: 14, damping: 0.93 }) })
    if (grenadeRIdx >= 0) springEntries.push({ boneIdx: grenadeRIdx, spring: createSecondarySpring([0,0,0], { stiffness: 14, damping: 0.93 }) })
    // Pass the SAME hair / bodyParts lists we used to extend the rig.
    // The emitter uses these to build its lookup maps; without them,
    // virtual joints (HairBob, Cape*, Grenade*) live in the rig but no
    // primitives emit for them — invisible cape + invisible hair.
    const bodyAndExtrasPrims = [...DEFAULT_BODY_PARTS, ...DEFAULT_CAPE_PARTS, ...DEFAULT_GRENADE_BELT]
    const faceRaymarchPrims: RaymarchPrimitive[] =
      chibiRaymarchPrimitives(
        rig, material,
        undefined,                 // face: stay default (empty)
        undefined,                 // accessories: stay default
        DEFAULT_BOB_HAIR,
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
      { maxSteps: 32 },   // tuned: per-primitive occlusion closes hits fast
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
    let nudeMode = true
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
    const persistentPrims = faceRaymarchPrims.slice()   // copy; add ephemeral per-frame
    console.log(`Raymarch: ${persistentPrims.length} persistent primitives`)
    if (persistentPrims.length > 0) {
      console.log('  first:', persistentPrims[0])
      console.log('  last:', persistentPrims[persistentPrims.length - 1])
    }
    function currentAllPrims(now: number): RaymarchPrimitive[] {
      return persistentPrims.concat(vfxSystem.getPrimitives(now))
    }

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
      // world = bone * (offset, 1)
      const cx = c0x * ox + c1x * oy + c2x * oz + tx
      const cy = c0y * ox + c1y * oy + c2y * oz + ty
      const cz = c0z * ox + c1z * oy + c2z * oz + tz
      const s0 = Math.sqrt(c0x * c0x + c0y * c0y + c0z * c0z)
      const s1 = Math.sqrt(c1x * c1x + c1y * c1y + c1z * c1z)
      const s2 = Math.sqrt(c2x * c2x + c2y * c2y + c2z * c2z)
      const maxScale = Math.max(s0, s1, s2)
      const rLocal = Math.abs(p.params[0]) + Math.abs(p.params[1]) + Math.abs(p.params[2]) + Math.abs(p.params[3]) + 0.05
      const r = rLocal * maxScale + Math.abs(p.blendRadius ?? 0)
      return { cx, cy, cz, r }
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
      const quantElapsed = Math.floor(elapsed / tickSec) * tickSec
      const frameIdx = Math.floor((quantElapsed / loadedVAT.durationSec) * loadedVAT.numFrames) % loadedVAT.numFrames

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
      const tickShouldRun =
        frameIdx !== lastSecondaryFrame ||
        restPose !== lastSecondaryRestPose
      const tickDt = tickShouldRun ? Math.max(elapsed - lastSecondaryElapsed, 1 / 60) : 0
      if (composer && tickShouldRun) {
        if (restPose) composer.applyRestPose(characterParams)
        else          composer.update(frameIdx, characterParams)
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
        // Read Spine2's world rotation columns so we can transform the
        // cape's local-frame offsets into world space — without this
        // the cape stays in world axes and doesn't follow body rotation.
        const s2 = spine2Idx * 16
        const sX: [number, number, number] = [wm[s2 + 0], wm[s2 + 1], wm[s2 + 2]]
        const sY: [number, number, number] = [wm[s2 + 4], wm[s2 + 5], wm[s2 + 6]]
        const sZ: [number, number, number] = [wm[s2 + 8], wm[s2 + 9], wm[s2 + 10]]
        const rotByS2 = (v: [number, number, number]): [number, number, number] => [
          v[0] * sX[0] + v[1] * sY[0] + v[2] * sZ[0],
          v[0] * sX[1] + v[1] * sY[1] + v[2] * sZ[1],
          v[0] * sX[2] + v[1] * sY[2] + v[2] * sZ[2],
        ]

        // Wind in WORLD space — drift the cape sideways regardless of body
        // facing. Slow swirl + small secondary oscillation = light breeze.
        const windStrength = 0.04
        const windAngle = elapsed * 0.7 + Math.sin(elapsed * 0.4) * 0.3
        const windX = Math.cos(windAngle) * windStrength
        const windZ = Math.sin(windAngle) * windStrength

        // ROOT (i=0): LOCKED — snap to Spine2's current world position
        // plus rotated rest offset. No stale-read lag at the attachment
        // point so the cape can't drift forward through the torso.
        {
          const spine2Pos = getBoneWorldPos(spine2Idx)
          const rotatedOff = rotByS2(capeChain[0].restOffset)
          capeChain[0].position[0] = spine2Pos[0] + rotatedOff[0]
          capeChain[0].position[1] = spine2Pos[1] + rotatedOff[1]
          capeChain[0].position[2] = spine2Pos[2] + rotatedOff[2]
          capeChain[0].prevParentPos[0] = spine2Pos[0]
          capeChain[0].prevParentPos[1] = spine2Pos[1]
          capeChain[0].prevParentPos[2] = spine2Pos[2]
          capeChain[0].initialised = true
        }

        // MID + TIP: chain physics with rotated offsets + wind.
        for (let i = 1; i < capeChain.length; i++) {
          const baseOff = capeChain[i].restOffset
          const rotatedOff = rotByS2(baseOff)
          const k = (i + 1) / capeChain.length
          const offsetWithWind: [number, number, number] = [
            rotatedOff[0] + windX * k,
            rotatedOff[1],
            rotatedOff[2] + windZ * k,
          ]
          tickNodeParticle(capeChain[i], capeChain, getBoneWorldPos, offsetWithWind)
        }

        // Body collision — push cape particles out of bounding spheres
        // around the spine. Stops the cape from passing through the
        // torso when it swings forward in wind / motion.
        const collisionList: { bone: number; r: number }[] = []
        if (spine2Idx >= 0) collisionList.push({ bone: spine2Idx, r: 0.16 })
        if (hipsIdx   >= 0) collisionList.push({ bone: hipsIdx,   r: 0.17 })
        // Skip root (i=0) — it's already locked to a sensible position.
        for (let i = 1; i < capeChain.length; i++) {
          const cp = capeChain[i].position
          for (const col of collisionList) {
            const cb = getBoneWorldPos(col.bone)
            const dx = cp[0] - cb[0]
            const dy = cp[1] - cb[1]
            const dz = cp[2] - cb[2]
            const dist = Math.hypot(dx, dy, dz)
            if (dist > 1e-6 && dist < col.r) {
              const k2 = col.r / dist
              cp[0] = cb[0] + dx * k2
              cp[1] = cb[1] + dy * k2
              cp[2] = cb[2] + dz * k2
            }
          }
        }
        for (let i = 0; i < capeBoneIndices.length; i++) {
          const boneIdx = capeBoneIndices[i]
          const off = boneIdx * 16
          // bone[i]'s segment spans particle[i] (TOP) → particle[i+1] (BOTTOM).
          // For the LAST bone (no next particle) the segment extrapolates a
          // tail of CAPE_SEG_DROP straight down so the cape has a clean
          // bottom edge instead of cutting off mid-segment.
          const top: [number, number, number] = capeChain[i].position
          const bottom: [number, number, number] = (i + 1 < capeChain.length)
            ? capeChain[i + 1].position
            : [top[0], top[1] - CAPE_SEG_DROP, top[2]]
          // Up vector = direction from segment bottom to top (bone +Y).
          let uy0 = top[0] - bottom[0]
          let uy1 = top[1] - bottom[1]
          let uy2 = top[2] - bottom[2]
          const ulen = Math.hypot(uy0, uy1, uy2) || 1
          uy0 /= ulen; uy1 /= ulen; uy2 /= ulen
          // Right vector = world X projected onto plane perpendicular to up.
          // Falls back to world Z if up is too close to world X.
          const upDotX = uy0
          let rx0 = 1 - uy0 * upDotX
          let rx1 = -uy1 * upDotX
          let rx2 = -uy2 * upDotX
          let rlen = Math.hypot(rx0, rx1, rx2)
          if (rlen < 0.05) {
            // Up is near-parallel to world X — switch reference axis to world Z.
            const upDotZ = uy2
            rx0 = -uy0 * upDotZ
            rx1 = -uy1 * upDotZ
            rx2 = 1 - uy2 * upDotZ
            rlen = Math.hypot(rx0, rx1, rx2) || 1
          }
          rx0 /= rlen; rx1 /= rlen; rx2 /= rlen
          // Forward (Z axis) = right × up.
          const fz0 = rx1 * uy2 - rx2 * uy1
          const fz1 = rx2 * uy0 - rx0 * uy2
          const fz2 = rx0 * uy1 - rx1 * uy0
          // Translation = midpoint between top and bottom (segment center).
          const cx = (top[0] + bottom[0]) * 0.5
          const cy = (top[1] + bottom[1]) * 0.5
          const cz = (top[2] + bottom[2]) * 0.5
          // Column-major mat4: col0=right, col1=up, col2=forward, col3=center.
          wm[off + 0]  = rx0; wm[off + 1]  = rx1; wm[off + 2]  = rx2; wm[off + 3]  = 0
          wm[off + 4]  = uy0; wm[off + 5]  = uy1; wm[off + 6]  = uy2; wm[off + 7]  = 0
          wm[off + 8]  = fz0; wm[off + 9]  = fz1; wm[off + 10] = fz2; wm[off + 11] = 0
          wm[off + 12] = cx;  wm[off + 13] = cy;  wm[off + 14] = cz;  wm[off + 15] = 1
        }
        // Re-upload the contiguous cape-bone range. Cape0..N are appended
        // in order to the rig so their world matrices live in consecutive
        // slots in the matrix buffer.
        const cape0Idx = capeBoneIndices[0]
        const startFloat = cape0Idx * 16
        device.queue.writeBuffer(
          vatHandle.buffer,
          cape0Idx * 64,
          wm.buffer,
          wm.byteOffset + startFloat * 4,
          16 * capeBoneIndices.length * 4,
        )
        invalidateRaymarchCache()
      }

      // Spring-jiggle: each entry's spring follows its bone's world
      // position with lag + overshoot. Read the composer-computed rest
      // target, tick the spring, override translation, re-upload that
      // bone slot. Rotation stays untouched so spheres / ellipsoids
      // inherit the parent bone's orientation.
      if (composer && springEntries.length > 0 && tickShouldRun) {
        const wm = composer.worldMatrices
        const dt = tickDt
        for (const entry of springEntries) {
          const off = entry.boneIdx * 16
          const restTarget: [number, number, number] = [wm[off + 12], wm[off + 13], wm[off + 14]]
          tickSpring(entry.spring, restTarget, dt)
          wm[off + 12] = entry.spring.position[0]
          wm[off + 13] = entry.spring.position[1]
          wm[off + 14] = entry.spring.position[2]
          device.queue.writeBuffer(
            vatHandle.buffer,
            entry.boneIdx * 64,
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
        lastSecondaryRestPose = restPose
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
        `[1] 24²   [2] 32²   [3] 48²   [4] debug 256²   proportion: ${currentProportion}`,
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
