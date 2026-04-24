/**
 * Sprite Atlas Bake — proof of the bake mechanic.
 *
 * Renders the Mixamo running skeleton from 8 canonical azimuths (N, NE, E,
 * SE, S, SW, W, NW) into 8 side-by-side 128×128 cells of a 1024×128 canvas.
 * Each cell is the sprite "view" at that azimuth for the current VAT frame.
 *
 * Save PNG button: canvas.toBlob() → download. That PNG IS an atlas row.
 * Bake Full Atlas: steps through all 60 VAT frames, capturing each as a
 * row, producing an 8×60 atlas at 1024×7680 — the full run cycle × all views.
 *
 * This is the memoization layer the architecture calls for. The sprite is
 * literally the view; this demo captures the function as a lookup table.
 *
 * Next iteration adds palette-index output (R8) + LUT indirection so the
 * bake produces index sprites instead of RGB, enabling runtime recolor.
 */

import { initGPU, Camera, FrameLoop } from '../src'
import { mat4 } from '../src/math/vec'
import { bakeSkeletonVAT } from '../src/character3d/skeleton'
import { createSkeletonRenderer } from '../src/character3d/skeleton_renderer'
import { loadMixamoBake, chibiBoneDisplayMats, chibiMaterial } from '../src/character3d/mixamo_loader'

const NUM_VIEWS = 8                             // N, NE, E, SE, S, SW, W, NW
const CELL_SIZE = 128                            // per-view tile pixels
const MIXAMO_VAT_FRAMES = 60                     // oversampled bake
const CANVAS_W = NUM_VIEWS * CELL_SIZE
const CANVAS_H = CELL_SIZE

// Build per-view (view, projection) matrices once. Camera orbits around
// a fixed target at a fixed distance — ISO elevation.
function buildViewMatrices(cellSize: number): { view: Float32Array; proj: Float32Array }[] {
  const views: { view: Float32Array; proj: Float32Array }[] = []
  const pitch = Math.atan(1 / Math.sqrt(2))       // ~35.26° (true isometric)
  const distance = 4
  const target: [number, number, number] = [0, 0.9, 0]
  const up: [number, number, number] = [0, 1, 0]
  const orthoSize = 1.3
  const aspect = 1                                 // cells are square

  for (let i = 0; i < NUM_VIEWS; i++) {
    const yaw = (i / NUM_VIEWS) * Math.PI * 2
    const pos: [number, number, number] = [
      target[0] + distance * Math.cos(pitch) * Math.sin(yaw),
      target[1] + distance * Math.sin(pitch),
      target[2] + distance * Math.cos(pitch) * Math.cos(yaw),
    ]
    const view = mat4.create()
    mat4.lookAt(view, pos, target, up)
    const proj = mat4.create()
    mat4.ortho(proj, -orthoSize * aspect, orthoSize * aspect, -orthoSize, orthoSize, 0.1, 50)
    views.push({ view, proj })
  }
  void cellSize
  return views
}

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const errorEl = document.getElementById('error')!
  const frameIdxEl = document.getElementById('frameIdx')!
  const frameTotalEl = document.getElementById('frameTotal')!
  const prevBtn = document.getElementById('prev') as HTMLButtonElement
  const nextBtn = document.getElementById('next') as HTMLButtonElement
  const playPauseBtn = document.getElementById('playpause') as HTMLButtonElement
  const saveBtn = document.getElementById('save') as HTMLButtonElement
  const bakeAllBtn = document.getElementById('bakeAll') as HTMLButtonElement

  try {
    const gpu = await initGPU(canvas)
    const { device, format } = gpu

    // Depth attachment matches canvas dims (already created by initGPU).
    // Camera setup is per-view; we won't use the orbit camera in this demo.

    const loaded = await loadMixamoBake('/mixamo_running.json')
    const rig = loaded.rig
    const sampler = loaded.sampler
    // Chibi body parts (giant head, cube torso, stubby limbs) instead of the
    // full 65-bone limb-box skeleton. Most Mixamo joints collapse to zero.
    const boneDisplay = chibiBoneDisplayMats(rig)

    const scales = rig.map(() => [1, 1, 1] as [number, number, number])
    const vat = bakeSkeletonVAT(device, rig, MIXAMO_VAT_FRAMES, scales, sampler)
    const material = chibiMaterial(rig)
    const renderer = createSkeletonRenderer(device, format, vat, boneDisplay, material)

    const views = buildViewMatrices(CELL_SIZE)

    let currentFrame = 0
    let playing = true
    let elapsed = 0

    frameTotalEl.textContent = String(MIXAMO_VAT_FRAMES)

    // --- Render one canvas sweep: 8 views side-by-side for a given frame. ---
    function renderSweep(frameIdx: number, mode: 'display' | 'gbuffer' = 'display') {
      const encoder = device.createCommandEncoder()
      const canvasView = gpu.context.getCurrentTexture().createView()

      // G-buffer mode clears to (0, 0.5, 0.5, 0) = transparent, "flat" normal,
      // depth=0. Any pixel not overwritten reads as background.
      const clearValue = mode === 'gbuffer'
        ? { r: 0, g: 0.5, b: 0.5, a: 0 }
        : { r: 0.04, g: 0.04, b: 0.06, a: 1.0 }

      for (let i = 0; i < NUM_VIEWS; i++) {
        const { view, proj } = views[i]
        const pass = encoder.beginRenderPass({
          colorAttachments: [
            {
              view: canvasView,
              loadOp: i === 0 ? 'clear' : 'load',
              storeOp: 'store',
              clearValue,
            },
          ],
          depthStencilAttachment: {
            view: gpu.depthView,
            depthLoadOp: 'clear',
            depthStoreOp: 'store',
            depthClearValue: 1.0,
            stencilLoadOp: 'clear',
            stencilStoreOp: 'store',
            stencilClearValue: 0,
          },
        })
        pass.setViewport(i * CELL_SIZE, 0, CELL_SIZE, CELL_SIZE, 0, 1)
        pass.setScissorRect(i * CELL_SIZE, 0, CELL_SIZE, CELL_SIZE)
        renderer.draw(pass, view, proj, frameIdx, 1.0, mode)
        pass.end()
      }
      device.queue.submit([encoder.finish()])
    }

    // --- Save current canvas as PNG. Works on WebGPU canvases in Chromium. ---
    async function saveCanvas(filename: string) {
      return new Promise<void>((resolve) => {
        canvas.toBlob((blob) => {
          if (!blob) { resolve(); return }
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = filename
          a.click()
          URL.revokeObjectURL(url)
          resolve()
        }, 'image/png')
      })
    }

    // --- Step the animation, render, update UI. ---
    function renderNow() {
      renderSweep(currentFrame)
      frameIdxEl.textContent = String(currentFrame)
    }

    prevBtn.onclick = () => {
      currentFrame = (currentFrame - 1 + MIXAMO_VAT_FRAMES) % MIXAMO_VAT_FRAMES
      playing = false
      playPauseBtn.textContent = 'Play'
      renderNow()
    }
    nextBtn.onclick = () => {
      currentFrame = (currentFrame + 1) % MIXAMO_VAT_FRAMES
      playing = false
      playPauseBtn.textContent = 'Play'
      renderNow()
    }
    playPauseBtn.onclick = () => {
      playing = !playing
      playPauseBtn.textContent = playing ? 'Pause' : 'Play'
    }
    saveBtn.onclick = () => saveCanvas(`sprite_row_frame${currentFrame.toString().padStart(2, '0')}.png`)

    async function bakeAtlas(mode: 'display' | 'gbuffer', filename: string, btn: HTMLButtonElement) {
      btn.disabled = true
      const wasPlaying = playing
      playing = false

      const atlasCanvas = document.createElement('canvas')
      atlasCanvas.width = CANVAS_W
      atlasCanvas.height = CANVAS_H * MIXAMO_VAT_FRAMES
      const atlasCtx = atlasCanvas.getContext('2d')!
      atlasCtx.imageSmoothingEnabled = false

      for (let f = 0; f < MIXAMO_VAT_FRAMES; f++) {
        renderSweep(f, mode)
        await new Promise((r) => requestAnimationFrame(r))
        atlasCtx.drawImage(canvas, 0, f * CANVAS_H)
        btn.textContent = `Baking ${f + 1}/${MIXAMO_VAT_FRAMES}…`
      }

      await new Promise<void>((resolve) => {
        atlasCanvas.toBlob((blob) => {
          if (!blob) { resolve(); return }
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = filename
          a.click()
          URL.revokeObjectURL(url)
          resolve()
        }, 'image/png')
      })

      btn.disabled = false
      playing = wasPlaying
    }

    bakeAllBtn.onclick = async () => {
      await bakeAtlas('display', 'mixamo_running_display.png', bakeAllBtn)
      bakeAllBtn.textContent = 'Bake Display Atlas (RGB preview)'
    }
    const bakeGBufferBtn = document.getElementById('bakeGBuffer') as HTMLButtonElement
    bakeGBufferBtn.onclick = async () => {
      await bakeAtlas('gbuffer', 'mixamo_running_gbuffer.png', bakeGBufferBtn)
      bakeGBufferBtn.textContent = 'Bake G-Buffer Atlas (idx+normals+depth)'
    }

    // --- Main loop ---
    const loop = new FrameLoop()
    loop.onUpdate = (stats) => { if (playing) elapsed += stats.dt }
    loop.onRender = (stats) => {
      if (playing) {
        const loopT = loaded.durationSec
        currentFrame = Math.floor((elapsed / loopT) * MIXAMO_VAT_FRAMES) % MIXAMO_VAT_FRAMES
      }
      renderNow()

      statsEl.textContent = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Views: ${NUM_VIEWS} × ${CELL_SIZE}px`,
        `VAT frames: ${MIXAMO_VAT_FRAMES}`,
        `Loop: ${loaded.durationSec.toFixed(2)}s`,
        `Rig joints: ${rig.length}`,
      ].join('\n')
    }

    loop.start()
  } catch (err) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU Error: ${err instanceof Error ? err.message : String(err)}`
    console.error(err)
  }
}

main()
