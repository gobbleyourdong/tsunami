/**
 * Smoke test — navigate through all game screens via Playwright.
 * Run: npx tsx tests/smoke.ts
 */

import { chromium } from 'playwright'

const SCREENSHOTS_DIR = '/tmp/sigma_screens'

async function main() {
  console.log('Starting smoke test...')

  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: true,
    args: ['--no-sandbox'],
  })

  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })

  // Collect console errors
  const errors: string[] = []
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text())
  })

  // Navigate to game
  await page.goto('http://localhost:5174')
  await page.waitForTimeout(1000)

  // Screenshot: Title screen
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/01_title.png` })
  console.log('1/6 Title screen captured')

  // Press Enter → Tutorial (hold across frame)
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/02_tutorial.png` })
  console.log('2/6 Tutorial screen captured')

  // Tutorial step 1: hold W across frames
  await page.keyboard.down('KeyW')
  await page.waitForTimeout(150)
  await page.keyboard.up('KeyW')
  await page.waitForTimeout(500)

  // Tutorial step 2: hold Space across frames
  await page.keyboard.down('Space')
  await page.waitForTimeout(150)
  await page.keyboard.up('Space')
  await page.waitForTimeout(4000)  // step 3 = 2s timed + fade transition (400ms) + buffer
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/03_arena.png` })
  console.log('3/6 Arena start captured')

  // Play: move + shoot with keys held across frames
  for (let i = 0; i < 10; i++) {
    await page.keyboard.down('KeyD')
    await page.keyboard.down('Space')
    await page.waitForTimeout(100)
    await page.keyboard.up('Space')
    await page.keyboard.up('KeyD')
    await page.waitForTimeout(50)
  }
  await page.waitForTimeout(3000)  // let enemies spawn
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/04_gameplay.png` })
  console.log('4/6 Gameplay captured')

  // More fighting
  for (let i = 0; i < 15; i++) {
    await page.keyboard.down('KeyA')
    await page.keyboard.down('Space')
    await page.waitForTimeout(80)
    await page.keyboard.up('Space')
    await page.keyboard.up('KeyA')
    await page.waitForTimeout(40)
  }
  await page.waitForTimeout(2000)
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/05_combat.png` })
  console.log('5/6 Combat captured')

  // Pause
  await page.keyboard.down('Escape')
  await page.waitForTimeout(100)
  await page.keyboard.up('Escape')
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SCREENSHOTS_DIR}/06_pause.png` })
  console.log('6/6 Pause screen captured')

  await browser.close()

  if (errors.length > 0) {
    console.log(`\nConsole errors: ${errors.length}`)
    for (const e of errors.slice(0, 5)) console.log(`  ${e}`)
  }

  console.log(`\nAll screenshots saved to ${SCREENSHOTS_DIR}/`)
  console.log('Smoke test PASSED')
}

main().catch((err) => {
  console.error('Smoke test FAILED:', err)
  process.exit(1)
})
