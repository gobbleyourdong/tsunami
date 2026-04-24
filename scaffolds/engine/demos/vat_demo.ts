/**
 * VAT Demo: instanced billboard sprites driven by a procedural RGBA32F
 * storage buffer. Canvas pixel buffer is fixed at MAX_SCENE_W × MAX_SCENE_H;
 * CSS scales it to fill the window with nearest-neighbor (pixel-art style).
 * No blit pass — scene renders directly to the fixed-size canvas.
 *
 * Validates the VAT pipeline for rigged-character animation: same buffer
 * layout will drive joint matrices once Mixamo data is plugged in.
 */

import { initGPU, Camera, FrameLoop, colorPass } from '../src'
import { createOrbitVAT } from '../src/character3d/vat'
import { createVATRenderer } from '../src/character3d/vat_renderer'
import { loadSpriteTexture } from '../src/character3d/sprite_texture'

const NUM_INSTANCES = 256        // denser-packed 32×32 sprites overlap; lower count
const NUM_FRAMES = 120
const ANIM_FPS = 8

// Canvas pixel buffer is fixed at this size (set via HTML width/height
// attributes). CSS scales to fill window. To change the "resolution,"
// edit the canvas attributes in vat_demo.html AND these constants.
// 256×224 = SNES native resolution (mode 1), aspect 8:7.
const MAX_SCENE_W = 256
const MAX_SCENE_H = 224

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats')!
  const errorEl = document.getElementById('error')!

  try {
    const gpu = await initGPU(canvas)
    const { device, format } = gpu

    // True isometric — camera on the diagonal (yaw 45°, pitch atan(1/√2)).
    // Orthographic so scale is uniform; orthoSize frames the orbit (radius 5,
    // height spread ±1.6) with margin.
    const camera = new Camera({
      mode: 'orthographic',
      position: [7, 7, 7],
      target: [0, 0, 0],
      orthoSize: 6,
      near: 0.1,
      far: 100,
      controls: 'orbit',
    })
    const cleanup = camera.bindToCanvas(canvas)
    camera.setAspect(MAX_SCENE_W, MAX_SCENE_H)

    const vat = createOrbitVAT(device, NUM_INSTANCES, NUM_FRAMES)
    const sprite = await loadSpriteTexture(device, '/canonical_final_sprite.png')
    const renderer = createVATRenderer(device, format, vat, sprite)

    // Pixel-snap toggle — press P to flip. Default on (stable pixel-grid motion).
    let pixelSnap = true
    window.addEventListener('keydown', (e) => {
      if (e.key === 'p' || e.key === 'P') pixelSnap = !pixelSnap
    })

    const loop = new FrameLoop()
    let elapsed = 0

    loop.onUpdate = (stats) => {
      elapsed += stats.dt
      camera.update()
    }

    loop.onRender = (stats) => {
      const frameIdx = Math.floor(elapsed * ANIM_FPS) % NUM_FRAMES
      const encoder = device.createCommandEncoder()
      const canvasView = gpu.context.getCurrentTexture().createView()
      const pass = encoder.beginRenderPass(colorPass(canvasView, gpu.depthView))
      renderer.draw(pass, camera.view, camera.projection, frameIdx, {
        sceneW: MAX_SCENE_W,
        sceneH: MAX_SCENE_H,
        pixelSnap,
      })
      pass.end()
      device.queue.submit([encoder.finish()])

      statsEl.textContent = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Frame: ${stats.frameTime.toFixed(1)}ms`,
        `Instances: ${NUM_INSTANCES.toLocaleString()}`,
        `Tris/frame: ${(NUM_INSTANCES * 2).toLocaleString()}`,
        `VAT buf: ${(NUM_INSTANCES * NUM_FRAMES * 16 / 1024 / 1024).toFixed(2)} MB`,
        `Canvas: ${canvas.width}×${canvas.height} (${(canvas.width * canvas.height / 1000).toFixed(0)}k px)`,
        `Anim frame: ${frameIdx} / ${NUM_FRAMES}`,
        `Sprite: ${sprite.width}×${sprite.height} px (1:1, never scaled)`,
        `Pixel snap: ${pixelSnap ? 'ON' : 'OFF'}   [press P to toggle]`,
      ].join('\n')
    }

    loop.start()

    window.addEventListener('beforeunload', () => {
      cleanup()
      loop.stop()
    })
  } catch (err) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU Error: ${err instanceof Error ? err.message : String(err)}`
    console.error(err)
  }
}

main()
