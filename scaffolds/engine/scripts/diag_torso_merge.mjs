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
await page.click('button[data-build="hourglass"]').catch(()=>{})
await new Promise(r => setTimeout(r, 600))
await page.keyboard.press('f')   // scene mode
await page.keyboard.press('t')   // T-pose
await new Promise(r => setTimeout(r, 600))
const buf = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/torso_merge.png', buf)
console.log('hourglass:', buf.length)
await browser.close()
