/**
 * Text Demo — Sample Newton text renderer.
 *
 * Renders "HELLO WORLD" at three sizes on a WebGPU canvas to visually
 * validate the Sample Newton glyph rendering. First build of the full
 * pipeline: baker → atlas upload → quad batcher → Newton iteration →
 * signed distance → AA'd filled glyphs.
 *
 * # Setup (one-time per font)
 *
 *   cd ark/scaffolds/engine
 *   pip install fonttools numpy pillow
 *   python tools/font_bake.py /path/to/Font.ttf --out public/fonts/regular
 *
 * This produces:
 *   public/fonts/regular.atlas.bin   — RGBA32F Hermite-handle atlas
 *   public/fonts/regular.atlas.json  — metadata
 *   public/fonts/regular.atlas.png   — 8-bit preview (debug only)
 *
 * The demo fetches `/fonts/regular.atlas.{bin,json}` at startup.
 *
 * # Validation checklist (run on hardware)
 *
 *   [ ] HELLO WORLD renders legibly at 16 px and 200 px
 *   [ ] Letters stay crisp at intermediate sizes (no pixelation / aliasing)
 *   [ ] Multi-contour glyphs (O, B, 8) render with holes (not filled inside)
 *   [ ] No spurious connection lines between contours
 *   [ ] At small sizes (8 px), text remains readable
 *   [ ] FPS stays ≥ 60 with ~30 glyphs on screen
 *
 * Winding-sign check: if glyphs render as their "negatives" (background
 * fills where glyph should be, glyph holes render solid), flip the sign
 * comparison in text_shader.ts fs_main (`cross_z > 0.0` → `< 0.0`).
 */

import { initGPU, resizeGPU, FrameLoop } from '../src'
import { createTextRenderer, loadFontAtlas } from '../src/ui'

// ── DOM helpers (no innerHTML — avoid XSS path) ─────────────────

function elem<K extends keyof HTMLElementTagNameMap>(
  tag: K, text?: string, parent?: Element,
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag)
  if (text !== undefined) el.textContent = text
  if (parent) parent.appendChild(el)
  return el
}

function showAtlasMissingError(container: HTMLElement, msg: string): void {
  container.textContent = ''   // clear any prior content
  container.style.display = 'block'

  elem('h3', 'Atlas not found', container)

  const p1 = elem('p', '', container)
  p1.appendChild(document.createTextNode('This demo needs a baked font atlas at '))
  elem('code', '/fonts/regular.atlas.{bin,json}', p1)
  p1.appendChild(document.createTextNode('.'))

  elem('p', 'Bake one with:', container)

  elem('pre',
    'cd ark/scaffolds/engine\n' +
    'pip install fonttools numpy pillow\n' +
    'python tools/font_bake.py /path/to/Font.ttf --out public/fonts/regular',
    container,
  )

  elem('p', 'Then reload.', container)

  const detail = elem('p', `Underlying error: ${msg}`, container)
  detail.style.opacity = '0.6'
  detail.style.marginTop = '8px'
}

function showGenericError(container: HTMLElement, msg: string): void {
  container.textContent = ''
  container.style.display = 'block'
  elem('h3', 'WebGPU Error', container)
  elem('pre', msg, container)
}

// ── Main ─────────────────────────────────────────────────────────

async function main() {
  const canvas = document.getElementById('canvas') as HTMLCanvasElement
  const statsEl = document.getElementById('stats') as HTMLElement
  const errorEl = document.getElementById('error') as HTMLElement

  try {
    const gpu = await initGPU(canvas)
    const { device } = gpu

    const text = createTextRenderer(gpu)
    const atlas = await loadFontAtlas(gpu, '/fonts/regular')
    text.load_atlas('regular', atlas)

    const loop = new FrameLoop()
    let t = 0

    loop.onUpdate = (stats) => {
      t += stats.dt
      resizeGPU(gpu)
    }

    loop.onRender = (stats) => {
      const view = gpu.context.getCurrentTexture().createView()
      const encoder = device.createCommandEncoder({ label: 'text-demo:frame' })

      const pass = encoder.beginRenderPass({
        label: 'text-demo:pass',
        colorAttachments: [
          {
            view,
            clearValue: { r: 0.06, g: 0.06, b: 0.08, a: 1.0 },
            loadOp: 'clear',
            storeOp: 'store',
          },
        ],
      })

      const vw = canvas.width
      const vh = canvas.height

      text.begin(pass, { width: vw, height: vh })

      // Three+ sizes on one canvas. Positions are top-left in pixel coords.
      const y_200 = 100
      const y_80 = y_200 + 220
      const y_32 = y_80 + 100
      const y_16 = y_32 + 50
      const y_8 = y_16 + 28

      text.draw('HELLO WORLD', [40, y_200],
        { color: [1.0, 1.0, 1.0, 1.0], size: 200 })

      text.draw('HELLO WORLD', [40, y_80],
        { color: [0.85, 0.92, 1.0, 1.0], size: 80 })

      text.draw('HELLO WORLD — mid', [40, y_32],
        { color: [0.75, 0.85, 1.0, 1.0], size: 32 })

      text.draw('HELLO WORLD — small 16px', [40, y_16],
        { color: [0.65, 0.75, 0.95, 1.0], size: 16 })

      text.draw('hello world — tiny 8px abcdefghijklmnopqrstuvwxyz', [40, y_8],
        { color: [0.55, 0.65, 0.85, 1.0], size: 8 })

      // Multi-contour glyph stress test — holes must render correctly.
      text.draw('OBO888QRCG0Dpqbd', [40, y_8 + 30],
        { color: [1.0, 0.7, 0.4, 1.0], size: 48 })

      // Live-scaled line: pulses to confirm scale-free rendering.
      const live_size = 32 + 32 * (0.5 + 0.5 * Math.sin(t * 0.8))
      text.draw('scale-free', [40, y_8 + 110],
        { color: [0.95, 0.55, 0.75, 1.0], size: live_size })

      text.end()

      pass.end()
      device.queue.submit([encoder.finish()])

      const n_glyphs_rough =
        'HELLO WORLD'.length * 2 +
        'HELLO WORLD — mid'.length +
        'HELLO WORLD — small 16px'.length +
        'hello world — tiny 8px abcdefghijklmnopqrstuvwxyz'.length +
        'OBO888QRCG0Dpqbd'.length +
        'scale-free'.length

      statsEl.textContent = [
        `FPS: ${stats.fps.toFixed(0)}`,
        `Frame: ${stats.frameTime.toFixed(1)}ms`,
        `Glyphs drawn: ~${n_glyphs_rough}`,
        `Viewport: ${vw}×${vh}`,
        `Atlas: ${Object.keys(atlas.metrics).length} glyphs`,
        ``,
        `visual checks:`,
        `- HELLO WORLD legible at all sizes`,
        `- O, B, 8, Q, R, C, G, 0, D, p, q, b, d → holes correct`,
        `- scale-free line stays crisp as it pulses`,
        `- if glyphs look inverted → flip sign in shader`,
      ].join('\n')
    }

    loop.start()

    window.addEventListener('beforeunload', () => {
      loop.stop()
      text.destroy()
    })
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    const is_atlas_missing = /404|fetch|atlas/.test(msg.toLowerCase())
    if (is_atlas_missing) {
      showAtlasMissingError(errorEl, msg)
    } else {
      showGenericError(errorEl, msg)
    }
    console.error(err)
  }
}

main()
