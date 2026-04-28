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
// Click hourglass build button
await page.click('button[data-build="hourglass"]').catch(()=>{})
await new Promise(r => setTimeout(r, 500))
await page.keyboard.press('f')   // scene mode for clear view
await page.keyboard.press('t')   // T-pose
await new Promise(r => setTimeout(r, 600))
// Front view
const buf1 = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/hourglass_front.png', buf1)
// Drag to rotate to back
await page.mouse.move(400, 400)
await page.mouse.down()
await page.mouse.move(400, 400)
for (let dx = 0; dx < 360; dx += 30) { await page.mouse.move(400 + dx, 400) }
await page.mouse.up()
await new Promise(r => setTimeout(r, 400))
const buf2 = await page.screenshot({ fullPage: false })
writeFileSync('/tmp/hourglass_back.png', buf2)
console.log('front:', buf1.length, 'back:', buf2.length)
await browser.close()
