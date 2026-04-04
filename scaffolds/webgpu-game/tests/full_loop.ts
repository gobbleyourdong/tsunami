/**
 * Full loop test — play → die → game over → retry → play again.
 * Run: npx tsx tests/full_loop.ts
 */

import { chromium } from 'playwright'

const DIR = '/tmp/sigma_screens'

async function main() {
  console.log('Full loop test...')

  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: true,
    args: ['--no-sandbox'],
  })

  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
  await page.goto('http://localhost:5174')
  await page.waitForTimeout(1000)

  // --- FIRST PLAYTHROUGH ---
  console.log('=== Playthrough 1 ===')

  // Title → Enter
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(800)

  // Tutorial: WASD + Space + wait
  await page.keyboard.down('KeyW')
  await page.waitForTimeout(150)
  await page.keyboard.up('KeyW')
  await page.waitForTimeout(500)
  await page.keyboard.down('Space')
  await page.waitForTimeout(150)
  await page.keyboard.up('Space')
  await page.waitForTimeout(4000)

  // Shoot enemies for a bit
  for (let i = 0; i < 20; i++) {
    await page.keyboard.down('KeyD')
    await page.keyboard.down('Space')
    await page.waitForTimeout(80)
    await page.keyboard.up('Space')
    await page.keyboard.up('KeyD')
    await page.waitForTimeout(40)
  }

  await page.screenshot({ path: `${DIR}/loop_01_playing.png` })
  const playText = await page.evaluate(() => document.getElementById('hud')?.textContent ?? '')
  console.log(`  Playing: ${playText.substring(0, 80)}`)

  // Wait for death (stop shooting, let enemies kill)
  console.log('  Waiting for death...')
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(500)
    const text = await page.evaluate(() => document.getElementById('hud')?.textContent ?? '')
    if (text.includes('GAME OVER')) {
      console.log('  Died!')
      break
    }
  }
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${DIR}/loop_02_gameover1.png` })

  // --- RETRY ---
  console.log('=== Retry ===')
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(1000)

  await page.screenshot({ path: `${DIR}/loop_03_title_again.png` })
  const titleText = await page.evaluate(() => document.getElementById('hud')?.textContent ?? '')
  const backAtTitle = titleText.includes('SIGMA ARENA')
  console.log(`  Back at title: ${backAtTitle}`)

  // --- SECOND PLAYTHROUGH ---
  console.log('=== Playthrough 2 ===')
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(800)

  // Skip tutorial faster
  await page.keyboard.down('KeyW')
  await page.waitForTimeout(150)
  await page.keyboard.up('KeyW')
  await page.waitForTimeout(500)
  await page.keyboard.down('Space')
  await page.waitForTimeout(150)
  await page.keyboard.up('Space')
  await page.waitForTimeout(4000)

  // Shoot and score
  for (let i = 0; i < 30; i++) {
    await page.keyboard.down('KeyA')
    await page.keyboard.down('Space')
    await page.waitForTimeout(80)
    await page.keyboard.up('Space')
    await page.keyboard.up('KeyA')
    await page.waitForTimeout(40)
  }

  await page.screenshot({ path: `${DIR}/loop_04_playing_again.png` })
  const play2Text = await page.evaluate(() => document.getElementById('hud')?.textContent ?? '')
  console.log(`  Playing again: ${play2Text.substring(0, 80)}`)

  await browser.close()

  console.log(`\nFull loop test ${backAtTitle ? 'PASSED' : 'FAILED'}`)
  if (!backAtTitle) process.exit(1)
}

main().catch((err) => {
  console.error('Full loop test FAILED:', err)
  process.exit(1)
})
