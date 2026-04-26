#!/usr/bin/env node
/**
 * One-shot modeler driver: load a spec into the running modeler, capture the
 * 4-view atlas, exit. Used by the agent loop to round-trip a spec → image.
 *
 *   node modeler_driver.mjs <spec.json> <atlas_out.png> [<depth_out.png>]
 *
 * Spec JSON: pass as `null` (literal) to skip setSpec and just capture the
 * modeler's current state (useful for the first round).
 *
 * Cold-starts a Chromium each call (~3-5s). For longer loops, refactor to
 * persistent. Today's loop is short enough that we don't need the speedup.
 */
import { chromium } from 'playwright'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const URL = 'http://localhost:5173/modeler_demo.html'
const [, , specArg, atlasOut, depthOut] = process.argv

if (!atlasOut) {
  console.error('usage: node modeler_driver.mjs <spec.json|null> <atlas.png> [<depth.png>]')
  process.exit(2)
}

const specJson = specArg === 'null' ? null : readFileSync(resolve(specArg), 'utf8')

// Headless WebGPU recipe per developer.chrome.com/blog/supercharge-web-ai-testing.
// Critical: --use-angle=vulkan (NOT --use-vulkan) and --disable-vulkan-surface
// (uses bit blit instead of needing a swapchain — eliminates the xvfb dep).
// Verified on DGX Spark ARM64 with NVIDIA 580 + Vulkan ICD; no virtual display
// required. requestAdapter returns a 24-feature Vulkan adapter.
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
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
const page = await ctx.newPage()

// Surface page-side errors to our stderr so we can debug failures.
page.on('console', (msg) => {
  if (msg.type() === 'error' || msg.type() === 'warning') {
    console.error(`[page ${msg.type()}]`, msg.text())
  }
})
page.on('pageerror', (err) => console.error('[page error]', err.message))

// `networkidle` never settles for the modeler — the render loop and the
// VL inbox poll keep traffic flowing. Use domcontentloaded + an explicit
// wait for window.modeler instead.
await page.goto(URL, { waitUntil: 'domcontentloaded' })

// Wait for the modeler to expose its tool API.
await page.waitForFunction(() => typeof window.modeler === 'object' && window.modeler !== null, { timeout: 10000 })

if (specJson !== null) {
  await page.evaluate((s) => window.modeler.setSpec(JSON.parse(s)), specJson)
}
// Force agent mode and let a few frames render so the atlas + screenshot settle.
await page.evaluate(() => window.modeler.setMode('agent'))
await page.waitForTimeout(400)

const colorUrl = await page.evaluate(() => window.modeler.screenshotAtlas())
writeFileSync(resolve(atlasOut), Buffer.from(colorUrl.split(',')[1], 'base64'))
console.log(`wrote ${atlasOut}`)

if (depthOut) {
  const mrt = await page.evaluate(() => window.modeler.screenshotAtlasMRT())
  writeFileSync(resolve(depthOut), Buffer.from(mrt.depth.split(',')[1], 'base64'))
  console.log(`wrote ${depthOut}`)
}

// Echo the current spec back so the caller can verify what was applied.
const finalSpec = await page.evaluate(() => window.modeler.getSpec())
console.log('SPEC_BEGIN')
console.log(JSON.stringify(finalSpec))
console.log('SPEC_END')

await browser.close()
