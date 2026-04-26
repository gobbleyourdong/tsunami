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

let frame = 0
const tick = async () => {
  try {
    const dataUrl = await page.evaluate(() => window.modeler.screenshotAtlas())
    writeFileSync(outPath, Buffer.from(dataUrl.split(',')[1], 'base64'))
    frame++
    if (frame % 10 === 0) {
      const spec = await page.evaluate(() => window.modeler.getSpec())
      console.log(`[preview-daemon] frame ${frame}, spec="${spec.name}"`)
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
