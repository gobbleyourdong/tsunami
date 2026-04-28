import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 800, height: 800 } })
const page = await ctx.newPage()
const consoles = []
page.on('console', (m) => consoles.push(`[${m.type()}] ${m.text().slice(0,200)}`))
page.on('pageerror', (e) => consoles.push('PAGEERR ' + e.message))
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))

// Press T to enter rest pose (T-pose now)
await page.keyboard.press('t')
await new Promise(r => setTimeout(r, 500))

const buf = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/skel_tpose.png', buf)
console.log('skel_tpose:', buf.length, 'bytes')

console.log('--- console (filter for tpose/error) ---')
for (const c of consoles) {
  if (c.includes('T-pose') || c.includes('error') || c.includes('PAGEERR') || c.includes('warning')) console.log(c)
}
await browser.close()
