import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 1024, height: 1024 } })
const page = await ctx.newPage()
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
await page.keyboard.press('f')   // scene mode
// Capture every 200ms for ~2.4s = ~12 frames covering the 2s backflip
for (let i = 0; i < 8; i++) {
  await new Promise(r => setTimeout(r, 250))
  const buf = await page.screenshot({ fullPage: false })
  writeFileSync(`/tmp/anim_${i}.png`, buf)
}
console.log('captured 8 frames')
await browser.close()
