/**
 * RPG Smoke test — title → move → NPC dialog → map transition.
 * Run: npx tsx tests/rpg_smoke.ts
 */

import { chromium } from 'playwright'

const DIR = '/tmp/rpg_screens'

async function main() {
  console.log('RPG smoke test...')

  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: true,
    args: ['--no-sandbox'],
  })

  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
  await page.goto('http://localhost:5174/rpg.html')
  await page.waitForTimeout(1500)

  // 1. Title screen
  await page.screenshot({ path: `${DIR}/01_title.png` })
  console.log('1/5 Title screen')

  // 2. Start game
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(1000)
  await page.screenshot({ path: `${DIR}/02_village.png` })
  console.log('2/5 Village')

  // 3. Walk around
  for (let i = 0; i < 8; i++) {
    await page.keyboard.down('KeyW')
    await page.waitForTimeout(120)
    await page.keyboard.up('KeyW')
    await page.waitForTimeout(50)
  }
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${DIR}/03_walking.png` })
  console.log('3/5 Walking')

  // 4. Talk to NPC (walk toward elder and press E)
  for (let i = 0; i < 3; i++) {
    await page.keyboard.down('KeyW')
    await page.waitForTimeout(120)
    await page.keyboard.up('KeyW')
    await page.waitForTimeout(50)
  }
  await page.keyboard.down('KeyE')
  await page.waitForTimeout(100)
  await page.keyboard.up('KeyE')
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${DIR}/04_dialog.png` })
  console.log('4/5 Dialog')

  // Advance dialog
  await page.keyboard.down('KeyE')
  await page.waitForTimeout(100)
  await page.keyboard.up('KeyE')
  await page.waitForTimeout(300)

  // 5. Walk north toward forest exit
  for (let i = 0; i < 20; i++) {
    await page.keyboard.down('KeyW')
    await page.waitForTimeout(100)
    await page.keyboard.up('KeyW')
    await page.waitForTimeout(30)
  }
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${DIR}/05_exploration.png` })
  console.log('5/5 Exploration/Map transition')

  await browser.close()
  console.log(`\nRPG smoke test PASSED — screenshots in ${DIR}/`)
}

main().catch(err => {
  console.error('RPG smoke test FAILED:', err)
  process.exit(1)
})
