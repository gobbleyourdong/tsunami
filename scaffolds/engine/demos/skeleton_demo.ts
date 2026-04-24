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
import { createRaymarchRenderer, type RaymarchPrimitive } from '../src/character3d/raymarch_renderer'
import { VFXSystem } from '../src/character3d/vfx_system'

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
    // size against screen context. 'framed' canvases match the sprite
    // cell size exactly so the sprite fills the canvas, zoomed by CSS.
    type PreviewMode = 'scene' | 'framed'
    let previewMode: PreviewMode = 'scene'
    const SNES_SCREEN = 256
    function canvasSizeForMode(): number {
      return previewMode === 'scene' ? SNES_SCREEN : SPRITE_MODES[spriteMode].w
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
    // Aspect is based on the SPRITE size (what the raymarch renders into),
    // not the screen. The cache is sprite-sized; cameras project into it.
    camera.setAspect(SPRITE_MODES[spriteMode].w, SPRITE_MODES[spriteMode].h)
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
          vat.rig = extendRigWithHair(vat.rig)
          vat.localMats = extendLocalMatsWithHair(vat.localMats, vat.numFrames, vat.numJoints)
          vat.numJoints = vat.rig.length
          vat.rig = extendRigWithBodyParts(vat.rig)
          vat.localMats = extendLocalMatsWithBodyParts(vat.localMats, vat.numFrames, vat.numJoints)
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
    /** Compute the animation ENVELOPE — union of joint-position bounds
     *  across every frame of every loaded animation. That's the true max
     *  extent the character will ever take; fitting to it lets the sprite
     *  hug the cell tightly without animation extrema (jump, swing)
     *  clipping outside. Sub-ms cost: ~20 anims × ~100 frames × ~80
     *  joints × one 4×4 mat-mul. Runs once per preset/mode change. */
    function estimateBounds(): { minY: number; maxY: number; maxR: number; cx: number; cz: number } {
      let minY = Infinity, maxY = -Infinity, maxR = 0, cxSum = 0, czSum = 0, cCount = 0
      const scaledLocal = new Float32Array(16)
      for (const anim of animations) {
        const lm = anim.vat.localMats
        if (!lm) continue
        const nf = anim.vat.numFrames
        const nj = rig.length
        for (let f = 0; f < nf; f++) {
          const base = f * nj * 16
          for (let j = 0; j < nj; j++) {
            const s = characterParams.scales[j]
            const src = base + j * 16
            const parent = rig[j].parent
            const isRoot = parent < 0
            for (let i = 0; i < 16; i++) scaledLocal[i] = lm[src + i]
            if (!isRoot) {
              scaledLocal[12] *= s[0]
              scaledLocal[13] *= s[1]
              scaledLocal[14] *= s[2]
            }
            const w = worldMatsTmp[j]
            if (isRoot) {
              w.set(scaledLocal)
            } else {
              const a = worldMatsTmp[parent], b = scaledLocal
              for (let col = 0; col < 4; col++) {
                for (let row = 0; row < 4; row++) {
                  w[col * 4 + row] =
                    a[row]      * b[col * 4]     +
                    a[row + 4]  * b[col * 4 + 1] +
                    a[row + 8]  * b[col * 4 + 2] +
                    a[row + 12] * b[col * 4 + 3]
                }
              }
            }
            const x = w[12], y = w[13], z = w[14]
            if (y < minY) minY = y
            if (y > maxY) maxY = y
            const r = Math.hypot(x, z)
            if (r > maxR) maxR = r
            cxSum += x; czSum += z; cCount++
          }
        }
      }
      if (cCount === 0) return { minY: 0, maxY: 1.8, maxR: 0.4, cx: 0, cz: 0 }
      return { minY, maxY, maxR, cx: cxSum / cCount, cz: czSum / cCount }
    }

    function fitCameraToCharacter() {
      const b = estimateBounds()
      // Margins only need to cover primitive thickness (head cube ~0.1m
      // half-size, limb radii ~0.05-0.07m) plus a 1-2 pixel outline ring.
      // The BIG anim extremes are already in the envelope (estimateBounds
      // walks every frame of every animation), so no anim-safety slack
      // needed here. Result: sprite hugs the cell tightly.
      const topMargin = 0.08
      const bottomMargin = 0.08
      const radialMargin = 0.10
      const halfH = ((b.maxY + topMargin) - (b.minY - bottomMargin)) / 2
      const center = ((b.maxY + topMargin) + (b.minY - bottomMargin)) / 2
      // Aspect based on sprite cell, not screen — camera is tuned for
      // rendering into the LOD-sized cache, not the SCREEN_SIZE scene.
      const sprite = SPRITE_MODES[spriteMode]
      const aspect = sprite.w / sprite.h
      const halfFromRadius = (b.maxR + radialMargin) / aspect
      camera.orthoSize = Math.max(halfH, halfFromRadius)
      camera.target = [b.cx, center, b.cz]
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
      sz24:  [0,   0,   0, 0],      // too small — skip white
      sz32:  [0,   0,   0, 0],      // 1 skin px between eyes, can't fit white
      sz48:  [0.5, 1.0, 0, 0],      // 2×3 white around 1×2 pupil (CT-tier)
      debug: [3.0, 2.0, 0, 0],      // 6×4 white around 3×2 pupil (SF-tier)
    }
    const PUPIL_COLOR: [number, number, number, number] = [0.10, 0.08, 0.20, 1.0]
    const WHITE_COLOR: [number, number, number, number] = [0.95, 0.92, 0.88, 1.0]

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
        paletteListEl.appendChild(row)
      }
    }
    buildPaletteUI()

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
    const faceRaymarchPrims: RaymarchPrimitive[] =
      chibiRaymarchPrimitives(rig, material) as RaymarchPrimitive[]
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
      })
    }
    const raymarch = createRaymarchRenderer(
      device, SCENE_FORMAT,
      faceRaymarchPrims,
      material.palette,
      vatHandle,
      { maxSteps: 32 },   // tuned: per-primitive occlusion closes hits fast
    )
    // Cache is sprite-sized, not screen-sized — the raymarch writes to the
    // LOD cell and we blit it centered into the bigger scene target.
    raymarch.resizeCache(SPRITE_MODES[spriteMode].w, SPRITE_MODES[spriteMode].h)
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
      camera.setAspect(cfg.w, cfg.h)
      // Proportion is independent — do NOT reset on resolution change.
      // Whatever proportion the user picked stays.
      fitCameraToCharacter()
      raymarch.resizeCache(cfg.w, cfg.h)
      invalidateRaymarchCache()
    }
    function togglePreviewMode() {
      previewMode = previewMode === 'scene' ? 'framed' : 'scene'
      applySpriteMode(spriteMode)   // re-run to resize canvas + rebind sources
    }

    type ViewMode = 'color' | 'normal' | 'depth'
    let viewMode: ViewMode = 'color'
    let depthOutlineOn = false
    let lightingMode: 0 | 1 = 0   // off / on (2-tone cel from MRT normal)
    // Rest pose: freezes animation and poses the rig at identity local
    // rotations — a stable reference for iterating on proportion sliders.
    // Toggle with T.
    let restPose = false

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
      camera.update()
      // Pixel-snap the view translation. Camera angles are allowed to
      // change rasterization (that's the pose-cache discretization); camera
      // translations must NOT. Snapping view.x/y to the pixel grid keeps
      // the character rasterizing the same bytes regardless of where the
      // camera has panned — "sprites copy, don't swim."
      // Snap against sprite-cell dimensions — that's the pixel grid the
      // raymarch rasterizes against. Canvas is larger (SCREEN_SIZE) but
      // the sprite IS the LOD cell.
      camera.pixelSnapView(SPRITE_MODES[spriteMode].w, SPRITE_MODES[spriteMode].h)
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
      if (composer) {
        if (restPose) composer.applyRestPose(characterParams)
        else          composer.update(frameIdx, characterParams)
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
          const spriteH = SPRITE_MODES[spriteMode].h
          const pxPerM = spriteH / (2 * camera.orthoSize)
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
        const spriteCfg = SPRITE_MODES[spriteMode]
        const pxPerM = spriteCfg.h / (2 * camera.orthoSize)
        const dxM = camera.view[12] - lastAabbView[12]
        const dyM = camera.view[13] - lastAabbView[13]
        const panOffsetX = -Math.round(dxM * pxPerM)
        const panOffsetY =  Math.round(dyM * pxPerM)   // screen Y is down
        const centerX = Math.round((canvas.width  - spriteCfg.w) / 2)
        const centerY = Math.round((canvas.height - spriteCfg.h) / 2)
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
        // Head joint position — bone's col3 (with the +Y tweak the chibi
        // rig uses to lift the head above shoulders). We want the visible
        // face anchor, so use col3 + CHIBI_CENTERED_OFFSET if present.
        const headOff = [0, 0, 0]   // head model origin is bone origin
        const wx = m[hBase + 0] * headOff[0] + m[hBase + 4] * headOff[1] + m[hBase + 8] * headOff[2] + m[hBase + 12]
        const wy = m[hBase + 1] * headOff[0] + m[hBase + 5] * headOff[1] + m[hBase + 9] * headOff[2] + m[hBase + 13]
        const wz = m[hBase + 2] * headOff[0] + m[hBase + 6] * headOff[1] + m[hBase + 10] * headOff[2] + m[hBase + 14]
        // Project world → clip via view × projection.
        const v = camera.view, p = camera.projection
        const cx = p[0]*(v[0]*wx + v[4]*wy + v[8]*wz + v[12]) + p[4]*(v[1]*wx + v[5]*wy + v[9]*wz + v[13]) + p[8]*(v[2]*wx + v[6]*wy + v[10]*wz + v[14]) + p[12]*(v[3]*wx + v[7]*wy + v[11]*wz + v[15])
        const cy = p[1]*(v[0]*wx + v[4]*wy + v[8]*wz + v[12]) + p[5]*(v[1]*wx + v[5]*wy + v[9]*wz + v[13]) + p[9]*(v[2]*wx + v[6]*wy + v[10]*wz + v[14]) + p[13]*(v[3]*wx + v[7]*wy + v[11]*wz + v[15])
        const cw = p[3]*(v[0]*wx + v[4]*wy + v[8]*wz + v[12]) + p[7]*(v[1]*wx + v[5]*wy + v[9]*wz + v[13]) + p[11]*(v[2]*wx + v[6]*wy + v[10]*wz + v[14]) + p[15]*(v[3]*wx + v[7]*wy + v[11]*wz + v[15])
        const ndcX = cx / cw, ndcY = cy / cw
        const spriteCfg = SPRITE_MODES[spriteMode]
        const cellPxX = (ndcX * 0.5 + 0.5) * spriteCfg.w
        const cellPxY = (1 - (ndcY * 0.5 + 0.5)) * spriteCfg.h   // flip Y (NDC up → pixel down)
        const centerX = (canvas.width  - spriteCfg.w) / 2
        const centerY = (canvas.height - spriteCfg.h) / 2
        // White enable=0 when the glyph has zero size → overlay falls
        // back to bare pupil dot on skin. Tiers below 80² go without
        // whites because they can't fit the extra pixels.
        const w = EYE_WHITE[spriteMode]
        const whiteCol: [number, number, number, number] = [
          WHITE_COLOR[0], WHITE_COLOR[1], WHITE_COLOR[2],
          w[0] > 0 ? 1.0 : 0.0,
        ]
        outline.setFacePaint(
          [centerX + cellPxX, centerY + cellPxY],
          EYE_PUPIL[spriteMode],
          w,
          PUPIL_COLOR,
          whiteCol,
        )
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
        `[V] view: ${viewMode}   [D] depth outline: ${depthOutlineOn ? 'on' : 'off'}   [L] lighting: ${lightingMode ? 'on' : 'off'}   [T] rest pose: ${restPose ? 'on' : 'off'}`,
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
