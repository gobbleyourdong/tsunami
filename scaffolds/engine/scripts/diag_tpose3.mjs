import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
// Wider viewport so canvas-wrap is bigger relative to side panel.
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } })
const page = await ctx.newPage()
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
// Toggle to scene mode (F off) so canvas fills wrap and we can SEE the body clearly.
await page.keyboard.press('f')
// T-pose
await page.keyboard.press('t')
await new Promise(r => setTimeout(r, 600))
const buf = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/skel_tpose_scene.png', buf)
console.log('scene-tpose:', buf.length)
await browser.close()
