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
page.on('console', (m) => consoles.push(`[${m.type()}] ${m.text().slice(0,300)}`))
await page.goto('http://localhost:5173/modeler_demo.html', { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => typeof window.modeler === 'object' && window.modeler !== null, { timeout: 15000 })
await page.evaluate(() => window.modeler.setMode('agent'))
await new Promise(r => setTimeout(r, 1500))

// Capture iso view in 4 channels: color, normal, depth, curvature
const view = process.argv[2] ?? 'iso'
for (const mode of ['color', 'normal', 'depth', 'curvature']) {
  try {
    const data = await page.evaluate(({ v, m }) => window.modeler.screenshotView(v, m), { v: view, m: mode })
    const buf = Buffer.from(data.split(',')[1], 'base64')
    const path = `/tmp/v_${view}_${mode}.png`
    writeFileSync(path, buf)
    console.log(`  ${view}/${mode}: ${buf.length} bytes -> ${path}`)
  } catch (e) {
    console.log(`  ${view}/${mode}: ERROR ${e.message}`)
  }
}

const errs = consoles.filter(c => c.startsWith('[error]') || c.startsWith('PAGEERR') || c.startsWith('[warning]'))
console.log(`Issues: ${errs.length}`)
for (const e of errs.slice(0, 5)) console.log('  ' + e)
await browser.close()
