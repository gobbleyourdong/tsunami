import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
const page = await ctx.newPage()
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
await page.keyboard.press('f')   // scene mode (no T-pose)
// Let animation run a bit — backflip is the default
await new Promise(r => setTimeout(r, 1500))
const buf = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/anim_explode.png', buf)
console.log('anim:', buf.length)
await browser.close()
