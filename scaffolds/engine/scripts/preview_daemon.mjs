#!/usr/bin/env node
/**
 * Throttled live-preview daemon.
 *
 * Keeps ONE persistent headless Chromium open against the modeler. Every
 * `intervalSec` it captures the current 4-view atlas and overwrites
 * `outPath`. Decoupled from any visible browser tab — you can close the
 * Vite tab entirely and your machine goes quiet; this daemon stays warm.
 *
 *   node preview_daemon.mjs [interval=3] [out=~/modeler_preview.png]
 *
 *   feh --reload 2 ~/modeler_preview.png    # or any auto-reloading viewer
 *
 * The daemon picks up spec changes via the modeler's normal VL-inbox poll
 * — nothing additional needed; just write to public/sdf_modeler/inbox.ark.json
 * and the next snapshot will reflect it.
 */
import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const URL = 'http://localhost:5173/modeler_demo.html'
const intervalSec = Number(process.argv[2] ?? 3)
// Default output lives in public/sdf_modeler/ so Vite serves it; the preview.html
// next to it loads the image with a cache-busting query string. Visit
// http://localhost:5173/sdf_modeler/preview.html for the live feed.
const __dir = dirname(fileURLToPath(import.meta.url))
const defaultOut = resolve(__dir, '../public/sdf_modeler/preview.png')
const outPath = resolve(process.argv[3] ?? defaultOut)

const browser = await chromium.launch({
  headless: true,
  args: [
    '--no-sandbox',
    '--headless=new',
    '--use-angle=vulkan',
    '--enable-features=Vulkan',
    '--disable-vulkan-surface',
    '--enable-unsafe-webgpu',
  ],
})
const ctx = await browser.newContext({ viewport: { width: 1024, height: 1024 } })
const page = await ctx.newPage()

page.on('pageerror', (err) => console.error('[page error]', err.message))

await page.goto(URL, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(
  () => typeof window.modeler === 'object' && window.modeler !== null,
  { timeout: 15000 },
)
await page.evaluate(() => window.modeler.setMode('agent'))

console.log(`[preview-daemon] every ${intervalSec}s → ${outPath}`)
console.log('[preview-daemon] Ctrl-C to stop')

// Render mode: 'atlas' (default — 4-view 2x2 grid), or one of the named
// single views: 'front' | 'side' | 'top' | 'iso'. Single views render at
// full canvas size — 4× the pixels per view for inspecting artifacts.
// Set via env var: PREVIEW_VIEW=iso node preview_daemon.mjs
const previewView = process.env.PREVIEW_VIEW ?? 'atlas'
// Optionally capture debug views alongside the main color render.
// PREVIEW_DEBUG accepts a comma-separated list of view modes:
//   normal | depth | silhouette | curvature | persurface
// Each requested mode produces a parallel preview_<mode>.png file.
// e.g. PREVIEW_DEBUG=normal,depth captures both preview_normal.png and
// preview_depth.png each tick. Useful for auditing SDF gradient + surface
// distance simultaneously without restarting the daemon.
const debugModes = (process.env.PREVIEW_DEBUG ?? '')
  .split(',').map((s) => s.trim()).filter(Boolean)
console.log(`[preview-daemon] view mode: ${previewView}${debugModes.length ? ', debug=' + debugModes.join('+') : ''}`)

const debugOutPaths = Object.fromEntries(
  debugModes.map((m) => [m, outPath.replace(/\.png$/, `_${m}.png`)]),
)

let frame = 0
const tick = async () => {
  try {
    const dataUrl = await page.evaluate((mode) => {
      if (mode === 'atlas') return window.modeler.screenshotAtlas()
      return window.modeler.screenshotView(mode)
    }, previewView)
    writeFileSync(outPath, Buffer.from(dataUrl.split(',')[1], 'base64'))
    if (previewView !== 'atlas') {
      for (const m of debugModes) {
        const debugUrl = await page.evaluate(({ v, mode }) => {
          return window.modeler.screenshotView(v, mode)
        }, { v: previewView, mode: m })
        writeFileSync(debugOutPaths[m], Buffer.from(debugUrl.split(',')[1], 'base64'))
      }
    }
    frame++
    if (frame % 10 === 0) {
      const spec = await page.evaluate(() => window.modeler.getSpec())
      console.log(`[preview-daemon] frame ${frame}, spec="${spec.name}", view=${previewView}`)
    }
  } catch (err) {
    console.error('[preview-daemon] capture failed:', err.message)
  }
}

// First tick immediately so the file exists for the viewer to open.
await tick()
const handle = setInterval(tick, intervalSec * 1000)

const shutdown = async () => {
  clearInterval(handle)
  await browser.close()
  console.log('[preview-daemon] stopped')
  process.exit(0)
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
