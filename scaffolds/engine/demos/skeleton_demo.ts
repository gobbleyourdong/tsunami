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
  chibiMaterial,
  uniformBoneDisplayMats,
  defaultRainbowMaterial,
} from '../src/character3d/mixamo_loader'
import {
  loadVATBinary,
  createRetargetComposer,
  defaultCharacterParams,
} from '../src/character3d/glb_loader'
import { createOutlinePass } from '../src/character3d/outline'

// Canvas IS the sprite. Each mode sizes the pixel buffer to its target
// sprite dimensions; CSS scales crisp-upscaled to fill the window.
// Same orthoSize everywhere — character fills the canvas height regardless
// of pixel resolution, so you see the final sprite at 1:1 pixel density.
const SPRITE_MODES = {
  link:    { label: 'Link LTTP 16×24',    w: 16,  h: 24  },
  chibi:   { label: 'SNES chibi 32×32',   w: 32,  h: 32  },
  alucard: { label: 'Alucard SotN 48×80', w: 48,  h: 80  },
  full:    { label: 'SNES 256×224',       w: 256, h: 224 },
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

    const camera = new Camera({
      mode: 'orthographic',
      position: [3, 2.5, 3],
      target: [0, CHARACTER_HEIGHT_M / 2, 0],
      orthoSize: ORTHO_HALF_H,
      near: 0.1,
      far: 50,
      controls: 'orbit',
    })
    const cleanup = camera.bindToCanvas(canvas)
    camera.setAspect(canvas.width, canvas.height)

    const loadedVAT = await loadVATBinary(device, '/mixamo_walking.vat')
    if (!loadedVAT.rig) throw new Error('VAT meta.json missing rig hierarchy')
    console.log(`VAT loaded: ${loadedVAT.numJoints} joints × ${loadedVAT.numFrames} frames, ${loadedVAT.durationSec.toFixed(2)}s, ${loadedVAT.isLocal ? 'local (retargetable)' : 'world (pre-baked)'}`)

    const rig = loadedVAT.rig
    // Retargeting composer — per-frame world-matrix compose from local +
    // per-character proportions. For VAT1 (legacy) no composer is used.
    const composer = loadedVAT.isLocal ? createRetargetComposer(device, loadedVAT) : null
    const characterParams = defaultCharacterParams(loadedVAT.numJoints)

    // --- Proportion system: group joints by body part, apply scale per group. ---
    // Groups mirror typical character-editor UI knobs. Each joint belongs to
    // exactly one group; scale propagates to its descendants via hierarchy
    // composition in the retarget composer.
    const GROUP_PATTERNS: Record<string, RegExp> = {
      head:  /^(Head|HeadTop_End|Neck)$/,                      // head + neck (moves head up/down with scale)
      torso: /^(Spine|Spine1|Spine2|Hips|Left(Shoulder)|Right(Shoulder))$/,
      arms:  /(LeftArm|RightArm|LeftForeArm|RightForeArm|LeftHand|RightHand)/,
      legs:  /(LeftUpLeg|LeftLeg|LeftFoot|RightUpLeg|RightLeg|RightFoot|LeftToe|RightToe)/,
    }

    function applyGroupScale(group: keyof typeof GROUP_PATTERNS, s: number) {
      const pat = GROUP_PATTERNS[group]
      for (let j = 0; j < rig.length; j++) {
        if (pat.test(rig[j].name)) characterParams.scales[j] = [s, s, s]
      }
    }

    const propGroups: (keyof typeof GROUP_PATTERNS)[] = ['head', 'torso', 'arms', 'legs']
    const currentScales: Record<string, number> = { head: 1, torso: 1, arms: 1, legs: 1 }

    function bindSlider(group: keyof typeof GROUP_PATTERNS) {
      const slider = document.getElementById(`${group}-slider`) as HTMLInputElement
      const valEl = document.getElementById(`${group}-val`)!
      slider.oninput = () => {
        const v = Number(slider.value)
        currentScales[group] = v
        valEl.textContent = v.toFixed(2)
        applyGroupScale(group, v)
      }
      applyGroupScale(group, Number(slider.value))
    }
    propGroups.forEach(bindSlider)

    const resetBtn = document.getElementById('reset-props') as HTMLButtonElement
    resetBtn.onclick = () => {
      for (const g of propGroups) {
        const s = document.getElementById(`${g}-slider`) as HTMLInputElement
        s.value = '1.0'
        s.dispatchEvent(new Event('input'))
      }
    }
    const chibiBtn = document.getElementById('preset-chibi') as HTMLButtonElement
    chibiBtn.onclick = () => {
      const presets: Record<string, string> = { head: '1.8', torso: '0.85', arms: '0.7', legs: '0.75' }
      for (const g of propGroups) {
        const s = document.getElementById(`${g}-slider`) as HTMLInputElement
        s.value = presets[g]
        s.dispatchEvent(new Event('input'))
      }
    }

    const vatHandle = {
      buffer: loadedVAT.buffer,
      numInstances: loadedVAT.numJoints,
      numFrames: loadedVAT.numFrames,
    }

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
    const outline = createOutlinePass(
      device, format,
      targets.sceneView!, targets.normalView!, targets.depthVizView!,
      canvas.width, canvas.height,
    )

    function refreshDisplay() {
      boneDisplay = displayMode === 'chibi' ? chibiBoneDisplayMats(rig) : uniformBoneDisplayMats(rig.length, 0.06)
      material = displayMode === 'chibi' ? chibiMaterial(rig) : defaultRainbowMaterial(rig.length)
      renderer.rebind(vatHandle, boneDisplay, material)
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
    }

    type ViewMode = 'color' | 'normal' | 'depth'
    let viewMode: ViewMode = 'color'
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
    let elapsed = 0

    loop.onUpdate = (stats) => {
      elapsed += stats.dt
      camera.update()
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
      renderer.draw(scenePass, camera.view, camera.projection, drawFrameIdx, 1.0)
      scenePass.end()

      // Pass 2: outline shader reads sceneTex → writes canvas with NAVY ring.
      const canvasView = gpu.context.getCurrentTexture().createView()
      outline.run(encoder, canvasView)

      device.queue.submit([encoder.finish()])

      const mode = SPRITE_MODES[spriteMode]
      statsEl.textContent = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Joints: ${rig.length}   Frame: ${frameIdx}/${loadedVAT.numFrames}`,
        `Source: mixamo_walking.vat (DAE world mats)`,
        `Sprite size: ${mode.label}`,
        `  canvas buffer: ${canvas.width}×${canvas.height} (CSS upscaled to window)`,
        ``,
        `[1] Link 16×24   [2] SNES chibi 32×32`,
        `[3] Alucard 48×80   [4] SNES 256×224`,
        `[V] view: ${viewMode}   [C] display: ${displayMode}`,
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
