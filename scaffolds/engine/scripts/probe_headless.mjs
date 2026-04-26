#!/usr/bin/env node
// Probe whether headless Chromium can render the modeler's WebGPU canvas.
import { chromium } from 'playwright'

const URL = 'http://localhost:5173/modeler_demo.html'

// Per https://developer.chrome.com/blog/supercharge-web-ai-testing
// the working recipe for headless Chrome WebGPU on Linux is:
//   --no-sandbox --headless=new --use-angle=vulkan
//   --enable-features=Vulkan --disable-vulkan-surface --enable-unsafe-webgpu
// Critical: --use-angle=vulkan (NOT --use-vulkan) and --disable-vulkan-surface
// (uses bit blit instead of swapchain). NVIDIA Vulkan ICD must be installed.
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
const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } })

const errs = []
page.on('console', (msg) => {
  if (msg.type() === 'error' || msg.type() === 'warning') errs.push(`[${msg.type()}] ${msg.text()}`)
})
page.on('pageerror', (err) => errs.push(`[pageerror] ${err.message}`))

await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 })
await page.waitForFunction(() => typeof window.modeler === 'object' && window.modeler !== null, { timeout: 15000 }).catch(() => {})

const probe = await page.evaluate(async () => {
  const hasGPU = !!navigator.gpu
  if (!hasGPU) return { hasGPU: false }
  let adapterInfo = null
  try {
    const adapter = await navigator.gpu.requestAdapter()
    if (adapter) {
      adapterInfo = {
        info: adapter.info ?? null,
        features: [...(adapter.features ?? [])],
      }
    }
  } catch (e) { adapterInfo = { error: String(e) } }
  const modelerReady = typeof window.modeler === 'object' && window.modeler !== null
  return { hasGPU, adapterInfo, modelerReady }
})

console.log(JSON.stringify(probe, null, 2))
if (errs.length) {
  console.error('--- console errors ---')
  for (const e of errs) console.error(e)
}

await browser.close()
