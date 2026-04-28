import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 1024, height: 1024 } })
const page = await ctx.newPage()
const consoles = []
page.on('pageerror', (e) => consoles.push('PAGEERR: ' + e.message))
page.on('console', (m) => consoles.push(`[${m.type()}] ${m.text()}`))
await page.goto('http://localhost:5173/modeler_demo.html', { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => typeof window.modeler === 'object' && window.modeler !== null, { timeout: 15000 })
await page.evaluate(() => window.modeler.setMode('agent'))
await new Promise(r => setTimeout(r, 2000))

// Get current spec and try getRenderState/whatever debug paths exist
const dbg = await page.evaluate(() => {
  const m = window.modeler
  const keys = Object.keys(m).filter(k => typeof m[k] === 'function')
  return { keys, spec: m.getSpec() }
})
console.log('MODELER METHODS:', dbg.keys.join(', '))
console.log('SPEC:', JSON.stringify(dbg.spec).slice(0,500))

// Take atlas, front, top each
for (const view of ['atlas','front','side','top','iso']) {
  try {
    const data = await page.evaluate((v) => {
      if (v === 'atlas') return window.modeler.screenshotAtlas()
      return window.modeler.screenshotView(v)
    }, view)
    const buf = Buffer.from(data.split(',')[1], 'base64')
    const path = `/tmp/diag_${view}.png`
    writeFileSync(path, buf)
    console.log(`  ${view}: ${buf.length} bytes -> ${path}`)
  } catch (e) {
    console.log(`  ${view}: ERROR ${e.message}`)
  }
}

console.log('---consoles---')
for (const c of consoles) console.log(c)
await browser.close()
