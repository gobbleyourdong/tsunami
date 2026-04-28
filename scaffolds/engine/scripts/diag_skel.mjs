import { chromium } from 'playwright'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 1024, height: 1024 } })
const page = await ctx.newPage()
const consoles = []
page.on('pageerror', (e) => consoles.push('PAGEERR: ' + e.message))
page.on('console', (m) => consoles.push(`[${m.type()}] ${m.text().slice(0,300)}`))
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
console.log('---consoles---')
let errCount = 0, warnCount = 0
for (const c of consoles) {
  if (c.startsWith('[error]') || c.startsWith('PAGEERR')) errCount++
  else if (c.startsWith('[warning]')) warnCount++
  console.log(c)
}
console.log(`SUMMARY: ${errCount} errors, ${warnCount} warnings`)
await browser.close()
