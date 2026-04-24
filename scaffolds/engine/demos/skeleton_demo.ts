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
import { createSkeletonRenderer } from '../src/character3d/skeleton_renderer'
import {
  chibiBoneDisplayMats,
  chibiRaymarchPrimitives,
  chibiMaterial,
  uniformBoneDisplayMats,
  defaultRainbowMaterial,
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
  link:    { label: 'Link LTTP 24²',    w: 24,  h: 24  },
  chibi:   { label: 'SNES chibi 32²',   w: 32,  h: 32  },
  alucard: { label: 'Alucard SotN 80²', w: 80,  h: 80  },
  full:    { label: 'SNES 256²',        w: 256, h: 256 },
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

    let spriteMode: SpriteMode = 'chibi'
    canvas.width = SPRITE_MODES[spriteMode].w
    canvas.height = SPRITE_MODES[spriteMode].h

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
    camera.setAspect(canvas.width, canvas.height)

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

    function applyGroupScale(group: keyof typeof GROUP_PATTERNS, s: number) {
      const pat = GROUP_PATTERNS[group]
      for (let j = 0; j < rig.length; j++) {
        if (pat.test(rig[j].name)) characterParams.scales[j] = [s, s, s]
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
    function estimateBounds(): { minY: number; maxY: number; maxR: number; cx: number; cz: number } {
      const lm = loadedVAT.localMats
      if (!lm) {
        // VAT1 legacy: fall back to rest offsets (ignores rotations — imprecise
        // but this path isn't exercised once we commit to VAT2).
        return { minY: 0, maxY: 1.8, maxR: 0.4, cx: 0, cz: 0 }
      }
      const scaledLocal = new Float32Array(16)
      for (let j = 0; j < rig.length; j++) {
        const s = characterParams.scales[j]
        const src = j * 16
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
      }
      let minY = Infinity, maxY = -Infinity, maxR = 0, cx = 0, cz = 0
      for (let j = 0; j < rig.length; j++) {
        const w = worldMatsTmp[j]
        const x = w[12], y = w[13], z = w[14]
        if (y < minY) minY = y
        if (y > maxY) maxY = y
        const r = Math.hypot(x, z)
        if (r > maxR) maxR = r
        cx += x; cz += z
      }
      cx /= rig.length; cz /= rig.length
      return { minY, maxY, maxR, cx, cz }
    }

    function fitCameraToCharacter() {
      const b = estimateBounds()
      // Joint cubes extend ~0.1m around their pivot (head 0.21 half-Y,
      // foot 0.09 half-Z, limbs 0.05-0.075). Add that plus animation swing
      // + outline ring. Feet get extra bottom margin because the foot cube
      // orients forward and its vertical extent is harder to predict.
      const topMargin = 0.14
      const bottomMargin = 0.18
      const radialMargin = 0.18
      const halfH = ((b.maxY + topMargin) - (b.minY - bottomMargin)) / 2
      const center = ((b.maxY + topMargin) + (b.minY - bottomMargin)) / 2
      const aspect = canvas.width / canvas.height
      const halfFromRadius = (b.maxR + radialMargin) / aspect
      camera.orthoSize = Math.max(halfH, halfFromRadius)
      camera.target = [b.cx, center, b.cz]
    }

    const propGroups: (keyof typeof GROUP_PATTERNS)[] = ['head', 'torso', 'arms', 'legs', 'bust', 'hips']
    const currentScales: Record<string, number> = { head: 1, torso: 1, arms: 1, legs: 1, bust: 0, hips: 0 }

    function bindSlider(group: keyof typeof GROUP_PATTERNS) {
      const slider = document.getElementById(`${group}-slider`) as HTMLInputElement
      const valEl = document.getElementById(`${group}-val`)!
      slider.oninput = () => {
        const v = Number(slider.value)
        currentScales[group] = v
        valEl.textContent = v.toFixed(2)
        applyGroupScale(group, v)
        // Head group overwrites face joint scales with uniform headS,
        // which would clobber an active expression. Re-apply the
        // expression's per-axis modulation on top after the slider fire.
        if (group === 'head' && currentExpression !== 'neutral') applyExpression(currentExpression)
        fitCameraToCharacter()
        invalidateRaymarchCache()   // proportion change → cache must re-march
      }
      applyGroupScale(group, Number(slider.value))
    }
    propGroups.forEach(bindSlider)
    fitCameraToCharacter()   // initial fit

    const resetBtn = document.getElementById('reset-props') as HTMLButtonElement
    resetBtn.onclick = () => {
      for (const g of propGroups) {
        const s = document.getElementById(`${g}-slider`) as HTMLInputElement
        // bust/hips default to 0 (off); other proportions default to 1.
        s.value = (g === 'bust' || g === 'hips') ? '0.0' : '1.0'
        s.dispatchEvent(new Event('input'))
      }
    }
    // Body-shape presets. First step on the 9-macro (MakeHuman) path —
    // these drive only the 4 existing proportion axes, so they can't
    // express shoulder-width / belly / neck independently yet. Adding
    // those as continuous sliders needs more virtual joints (belly as
    // a virtual joint on Spine1, shoulder-width as non-uniform Spine2
    // X-scale). Presets give the silhouette variety now; keep the
    // architectural room for the full MakeHuman 9-macro later.
    const BODY_PRESETS: Record<string, Record<string, string>> = {
      'preset-chibi':  { head: '1.8',  torso: '0.85', arms: '0.7',  legs: '0.75', bust: '0.0',  hips: '0.0'  },
      'preset-male':   { head: '0.95', torso: '1.08', arms: '1.05', legs: '1.00', bust: '0.0',  hips: '0.0'  },
      'preset-female': { head: '0.95', torso: '0.92', arms: '0.88', legs: '0.98', bust: '0.85', hips: '1.00' },
      'preset-child':  { head: '1.40', torso: '0.75', arms: '0.75', legs: '0.70', bust: '0.0',  hips: '0.0'  },
      'preset-tall':   { head: '0.90', torso: '1.00', arms: '1.05', legs: '1.30', bust: '0.0',  hips: '0.0'  },
      'preset-stocky': { head: '1.00', torso: '1.15', arms: '1.00', legs: '0.82', bust: '0.0',  hips: '0.30' },
    }
    for (const [btnId, presets] of Object.entries(BODY_PRESETS)) {
      const btn = document.getElementById(btnId) as HTMLButtonElement | null
      if (!btn) continue
      btn.onclick = () => {
        for (const g of propGroups) {
          const s = document.getElementById(`${g}-slider`) as HTMLInputElement
          s.value = presets[g]
          s.dispatchEvent(new Event('input'))
        }
      }
    }

    let vatHandle = {
      buffer: loadedVAT.buffer,
      numInstances: loadedVAT.numJoints,
      numFrames: loadedVAT.numFrames,
    }
    let elapsed = 0   // hoisted so switchAnimation can reset it

    let displayMode: 'chibi' | 'skeleton' = 'chibi'
    let boneDisplay = chibiBoneDisplayMats(rig)
    let material = chibiMaterial(rig)

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

    // MRT skeleton renderer: writes color, normal, depth in one pass.
    const renderer = createSkeletonRenderer(device, SCENE_FORMAT, vatHandle, boneDisplay, material, { mrt: true })

    // --- Palette controls: one color picker per named slot. Edits hit
    // renderer.setPaletteSlot() which writeBuffers the palette LUT — next
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
          renderer.setPaletteSlot(slot, nr, ng, nb, 1)
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
    let currentExpression = 'neutral'
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
      // Proportion sliders: apply each known group; fire input events so
      // scales + camera fit recompute via the same path a slider drag uses.
      for (const g of propGroups) {
        const v = spec.proportions?.[g]
        if (typeof v !== 'number') continue
        const s = document.getElementById(`${g}-slider`) as HTMLInputElement | null
        if (!s) continue
        s.value = String(v)
        s.dispatchEvent(new Event('input'))
      }
      // Palette: set each known slot. Unknown slots ignored (forward-compat).
      for (const [slotName, slotIdx] of Object.entries(material.namedSlots)) {
        const rgb = spec.palette?.[slotName]
        if (!rgb) continue
        material.palette[slotIdx * 4 + 0] = rgb[0]
        material.palette[slotIdx * 4 + 1] = rgb[1]
        material.palette[slotIdx * 4 + 2] = rgb[2]
        renderer.setPaletteSlot(slotIdx, rgb[0], rgb[1], rgb[2], 1)
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
      { maxSteps: 48 },
    )
    raymarch.resizeCache(canvas.width, canvas.height)
    // Cache invalidation: bump whenever any raymarch input changes so next
    // frame re-marches into the cache; otherwise we skip the march and blit.
    // Bumped by: sprite mode, animation frame, proportion sliders, palette
    // edits, camera moves, primitive list changes. For a static pose at a
    // parked camera, the cache holds and the frame becomes one blit.
    let raymarchCacheVersion = 0
    let raymarchCacheApplied = -1
    function invalidateRaymarchCache() { raymarchCacheVersion++ }
    let rendererMode: 'cube' | 'raymarch' = 'cube'

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

    function refreshDisplay() {
      boneDisplay = displayMode === 'chibi' ? chibiBoneDisplayMats(rig) : uniformBoneDisplayMats(rig.length, 0.06)
      material = displayMode === 'chibi' ? chibiMaterial(rig) : defaultRainbowMaterial(rig.length)
      renderer.rebind(vatHandle, boneDisplay, material)
      buildPaletteUI()
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
      // Rig + proportion sliders are shared across Mixamo anims (same 65
      // joints, same parent indices), so boneDisplay/material carry over.
      renderer.rebind(vatHandle, boneDisplay, material)
      // Raymarch renderer reads from the VAT buffer too — without this
      // rebind, raymarch mode after an anim switch reads stale matrices
      // from the previous animation's buffer (invisible character).
      raymarch.rebind(vatHandle)
      invalidateRaymarchCache()
      elapsed = 0
    }

    function applySpriteMode(mode: SpriteMode) {
      spriteMode = mode
      const cfg = SPRITE_MODES[mode]
      canvas.width = cfg.w
      canvas.height = cfg.h
      gpu.context.configure({ device, format, alphaMode: 'premultiplied' })
      recreateTargets(cfg.w, cfg.h)
      outline.rebindSources(targets.sceneView!, targets.normalView!, targets.depthVizView!, cfg.w, cfg.h)
      camera.setAspect(cfg.w, cfg.h)
      fitCameraToCharacter()   // aspect changed → refit
      raymarch.resizeCache(cfg.w, cfg.h)
      invalidateRaymarchCache()
    }

    type ViewMode = 'color' | 'normal' | 'depth'
    let viewMode: ViewMode = 'color'
    let depthOutlineOn = false
    let lightingMode: 0 | 1 | 2 = 0   // off / MRT normal / reconstructed normal

    // --- Camera mode: editor (free orbit, sub-pixel OK) vs game (8-angle
    // cardinal preset, discrete yaw per pose-cache contract). Same
    // renderer; mode just discretizes the camera inputs so (pose, yaw)
    // becomes a finite state space that cacheable/atlasable. Pitch is
    // locked to an iso-ish angle in game mode. ---
    type CameraMode = 'editor' | 'game'
    let cameraMode: CameraMode = 'editor'
    // 8 cardinal yaws, N/NE/E/SE/S/SW/W/NW. Yaw=0 looks down -Z (toward
    // character's back); rotating CCW when viewed from above. This
    // matches the convention the orbit controller was already using.
    const GAME_YAWS = [0, 45, 90, 135, 180, 225, 270, 315].map((d) => d * Math.PI / 180)
    const GAME_PITCH = 30 * Math.PI / 180   // classic iso-ish pitch
    let gameYawIdx = 0
    function applyGameCamera() {
      camera.setOrbitAngles(GAME_YAWS[gameYawIdx], GAME_PITCH)
    }
    function toggleCameraMode() {
      if (cameraMode === 'editor') {
        // Snap to the nearest preset yaw so the switch isn't jarring.
        const { yaw } = camera.getOrbitAngles()
        const norm = ((yaw % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2)
        let best = 0, bestDist = Infinity
        for (let i = 0; i < GAME_YAWS.length; i++) {
          const d = Math.abs(norm - GAME_YAWS[i])
          const dWrap = Math.min(d, Math.PI * 2 - d)
          if (dWrap < bestDist) { bestDist = dWrap; best = i }
        }
        gameYawIdx = best
        cameraMode = 'game'
        applyGameCamera()
      } else {
        cameraMode = 'editor'
      }
    }
    function cycleGameYaw(delta: number) {
      if (cameraMode !== 'game') return
      gameYawIdx = ((gameYawIdx + delta) % GAME_YAWS.length + GAME_YAWS.length) % GAME_YAWS.length
      applyGameCamera()
    }
    const YAW_LABELS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    function cycleViewMode() {
      viewMode = viewMode === 'color' ? 'normal' : viewMode === 'normal' ? 'depth' : 'color'
      outline.setViewMode(viewMode)
    }

    window.addEventListener('keydown', (e) => {
      if (e.key === 'c' || e.key === 'C') {
        displayMode = displayMode === 'chibi' ? 'skeleton' : 'chibi'
        refreshDisplay()
      }
      if (e.key === '1') applySpriteMode('link')
      if (e.key === '2') applySpriteMode('chibi')
      if (e.key === '3') applySpriteMode('alucard')
      if (e.key === '4') applySpriteMode('full')
      if (e.key === 's' || e.key === 'S') saveCurrentFrame()
      if (e.key === 'a' || e.key === 'A') saveAnimationStrip()
      if (e.key === 'v' || e.key === 'V') cycleViewMode()
      if (e.key === 'm' || e.key === 'M') switchAnimation(animIdx + 1)
      if (e.key === 'd' || e.key === 'D') {
        depthOutlineOn = !depthOutlineOn
        outline.setDepthOutline(depthOutlineOn)
      }
      if (e.key === 'l' || e.key === 'L') {
        lightingMode = ((lightingMode + 1) % 3) as 0 | 1 | 2
        outline.setLighting(lightingMode)
      }
      if (e.key === 'g' || e.key === 'G') toggleCameraMode()
      if (e.key === 'q' || e.key === 'Q' || e.key === '[') cycleGameYaw(-1)
      if (e.key === 'e' || e.key === 'E' || e.key === ']') cycleGameYaw(+1)
      if (e.key === 'r' || e.key === 'R') {
        rendererMode = rendererMode === 'cube' ? 'raymarch' : 'cube'
        invalidateRaymarchCache()
      }
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

    // --- Save helpers ---
    function saveBlob(blob: Blob, filename: string) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    }

    function saveCurrentFrame() {
      canvas.toBlob((blob) => {
        if (!blob) return
        saveBlob(blob, `chibi_${spriteMode}_frame.png`)
      }, 'image/png')
    }

    /** Bake every frame into THREE horizontal-strip PNGs: color, normal, depth.
     *  The full G-buffer atlas set — what the game engine consumes at runtime
     *  for lighting + depth compositing + palette-swap recolor. Each frame
     *  rendered once; the three MRT targets copied via separate viewMode
     *  passes to the same canvas, drawImage'd into three separate strips. */
    async function saveAnimationStrip() {
      const W = canvas.width
      const H = canvas.height
      const N = loadedVAT!.numFrames

      function makeStripCanvas() {
        const c = document.createElement('canvas')
        c.width = W * N
        c.height = H
        const ctx = c.getContext('2d')!
        ctx.imageSmoothingEnabled = false
        return { canvas: c, ctx }
      }
      const colorStrip  = makeStripCanvas()
      const normalStrip = makeStripCanvas()
      const depthStrip  = makeStripCanvas()

      const wasRunning = (loop as unknown as { running: boolean }).running
      loop.stop()
      const savedViewMode = viewMode

      async function renderFrame(f: number) {
        // Retarget compose for the target frame (writes slot 0). Then shader
        // reads slot 0 regardless of composer presence.
        if (composer) composer.update(f, characterParams)
        const encoder = device.createCommandEncoder()
        const scenePass = encoder.beginRenderPass({
          colorAttachments: [
            { view: targets.sceneView!,    loadOp: 'clear', storeOp: 'store', clearValue: { r: 0, g: 0, b: 0, a: 0 } },
            { view: targets.normalView!,   loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1.0, a: 0 } },
            { view: targets.depthVizView!, loadOp: 'clear', storeOp: 'store', clearValue: { r: 1, g: 0, b: 0, a: 0 } },
          ],
          depthStencilAttachment: {
            view: targets.sceneDepthView!,
            depthLoadOp: 'clear', depthStoreOp: 'store', depthClearValue: 1.0,
            stencilLoadOp: 'clear', stencilStoreOp: 'store', stencilClearValue: 0,
          },
        })
        renderer.draw(scenePass, camera.view, camera.projection, composer ? 0 : f, 1.0)
        scenePass.end()
        const canvasView = gpu.context.getCurrentTexture().createView()
        outline.run(encoder, canvasView)
        device.queue.submit([encoder.finish()])
        await new Promise((r) => requestAnimationFrame(r))
      }

      for (let f = 0; f < N; f++) {
        // Color + outline pass
        outline.setViewMode('color')
        await renderFrame(f)
        colorStrip.ctx.drawImage(canvas, f * W, 0)

        // Normal pass (re-run outline with normal view mode — same scene data
        // already in MRT textures, just different display).
        outline.setViewMode('normal')
        const encN = device.createCommandEncoder()
        outline.run(encN, gpu.context.getCurrentTexture().createView())
        device.queue.submit([encN.finish()])
        await new Promise((r) => requestAnimationFrame(r))
        normalStrip.ctx.drawImage(canvas, f * W, 0)

        // Depth pass
        outline.setViewMode('depth')
        const encD = device.createCommandEncoder()
        outline.run(encD, gpu.context.getCurrentTexture().createView())
        device.queue.submit([encD.finish()])
        await new Promise((r) => requestAnimationFrame(r))
        depthStrip.ctx.drawImage(canvas, f * W, 0)
      }

      // Restore view mode
      outline.setViewMode(savedViewMode)

      async function downloadStrip(c: HTMLCanvasElement, kind: string) {
        await new Promise<void>((resolve) => {
          c.toBlob((blob) => {
            if (!blob) { resolve(); return }
            saveBlob(blob, `chibi_${spriteMode}_${kind}_${N}frames.png`)
            resolve()
          }, 'image/png')
        })
      }
      await downloadStrip(colorStrip.canvas,  'color')
      await downloadStrip(normalStrip.canvas, 'normal')
      await downloadStrip(depthStrip.canvas,  'depth')

      if (wasRunning) loop.start()
    }

    const loop = new FrameLoop()

    loop.onUpdate = (stats) => {
      elapsed += stats.dt
      // In game mode, force-reapply the preset yaw/pitch each frame so
      // mouse-orbit drags don't leak discrete states. This is what
      // makes the pose key finite: game camera can only ever be one of
      // GAME_YAWS[0..7] × GAME_PITCH.
      if (cameraMode === 'game') applyGameCamera()
      camera.update()
      // Pixel-snap the view translation. Camera angles are allowed to
      // change rasterization (that's the pose-cache discretization); camera
      // translations must NOT. Snapping view.x/y to the pixel grid keeps
      // the character rasterizing the same bytes regardless of where the
      // camera has panned — "sprites copy, don't swim."
      camera.pixelSnapView(canvas.width, canvas.height)
    }

    // Track last-seen inputs to auto-invalidate the raymarch cache when
    // anything that would change the pixel output changes. Simple quantized
    // fingerprint avoids false negatives while keeping the comparison O(1).
    let lastCacheFrameIdx = -1
    const lastCacheView = new Float32Array(16)
    let lastCacheOrtho = -1
    function raymarchCacheFingerprintChanged(frameIdx: number): boolean {
      if (frameIdx !== lastCacheFrameIdx) return true
      if (camera.orthoSize !== lastCacheOrtho) return true
      for (let i = 0; i < 16; i++) {
        if (camera.view[i] !== lastCacheView[i]) return true
      }
      return false
    }
    function snapshotCacheFingerprint(frameIdx: number) {
      lastCacheFrameIdx = frameIdx
      lastCacheOrtho = camera.orthoSize
      for (let i = 0; i < 16; i++) lastCacheView[i] = camera.view[i]
    }

    loop.onRender = (stats) => {
      const frameIdx = Math.floor((elapsed / loadedVAT.durationSec) * loadedVAT.numFrames) % loadedVAT.numFrames

      // Retargeting compose: overwrite vat.buffer's FIRST frame slot with
      // the current frame's composed world matrices (local × scale →
      // parent-chained world). Renderer then reads from slot 0.
      if (composer) composer.update(frameIdx, characterParams)
      // When the composer is active, the shader reads slot 0 (composer
      // writes current frame there each tick). Without composer (VAT1),
      // use frameIdx directly against the pre-baked world-matrix table.
      const drawFrameIdx = composer ? 0 : frameIdx

      const encoder = device.createCommandEncoder()

      // Raymarch cache refresh — happens BEFORE the scene pass. If the
      // cache fingerprint matches last frame, skip the march entirely
      // and just blit inside the scene pass below. For an animating
      // character this re-marches every frame (frameIdx bumps version);
      // for a paused character at a fixed camera, zero march cost.
      if (rendererMode === 'raymarch') {
        if (raymarchCacheFingerprintChanged(drawFrameIdx)) invalidateRaymarchCache()
        if (raymarchCacheVersion !== raymarchCacheApplied) {
          const eyeR: [number, number, number] = [camera.position[0], camera.position[1], camera.position[2]]
          vfxSystem.update(elapsed)
          raymarch.setPrimitives(currentAllPrims(elapsed))
          raymarch.setTime(elapsed)
          const pxPerM = canvas.height / (2 * camera.orthoSize)
          raymarch.setPxPerM(pxPerM)
          raymarch.marchIntoCache(encoder, camera.view, camera.projection, eyeR, drawFrameIdx)
          raymarchCacheApplied = raymarchCacheVersion
          snapshotCacheFingerprint(drawFrameIdx)
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
      if (rendererMode === 'raymarch') {
        // Scene pass outputs = blit from the raymarch cache framebuffer.
        // All the expensive march work happened above (either this frame
        // on cache miss, or a past frame the cache is replaying). Outline
        // pass downstream can't tell the difference from direct rendering.
        raymarch.blitCacheToPass(scenePass)
      } else {
        renderer.draw(scenePass, camera.view, camera.projection, drawFrameIdx, 1.0)
      }
      scenePass.end()

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
        `[1] Link 16×24   [2] SNES chibi 32×32`,
        `[3] Alucard 48×80   [4] SNES 256×224`,
        `[V] view: ${viewMode}   [C] display: ${displayMode}   [D] depth outline: ${depthOutlineOn ? 'on' : 'off'}   [L] lighting: ${['off','mrt','recon'][lightingMode]}`,
        `[G] camera: ${cameraMode}${cameraMode === 'game' ? ` (${YAW_LABELS[gameYawIdx]})   [Q/E] rotate` : '   (orbit freely)'}   [R] renderer: ${rendererMode}`,
        `[Space] swipe   [X] star   [Z] flash   [N] bolt   [B] beam   VFX: ${vfxSystem.count()}`,
        `[S] save frame   [A] save anim strip   drag = orbit`,
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
