import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox','--headless=new','--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-unsafe-webgpu'],
})
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1200 } })
const page = await ctx.newPage()
await page.goto('http://localhost:5173/skeleton_demo.html', { waitUntil: 'domcontentloaded' })
await new Promise(r => setTimeout(r, 4000))
// Pick debug 256² resolution + scene mode
await page.click('button[data-res="256"]').catch(()=>{})
await new Promise(r => setTimeout(r, 500))
await page.keyboard.press('f')   // scene mode
await page.keyboard.press('t')   // T-pose
await new Promise(r => setTimeout(r, 600))
const canvas = await page.$('#canvas')
const buf = await canvas.screenshot()
writeFileSync('/tmp/clothing_check.png', buf)
console.log('canvas:', buf.length)
await browser.close()
