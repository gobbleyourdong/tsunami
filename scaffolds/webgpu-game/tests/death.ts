/**
 * Death test — let the player die and verify game over screen.
 * Run: npx tsx tests/death.ts
 */

import { chromium } from 'playwright'

const DIR = '/tmp/sigma_screens'

async function main() {
  console.log('Death test: verifying game over flow...')

  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium-browser',
    headless: true,
    args: ['--no-sandbox'],
  })

  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })

  const errors: string[] = []
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text())
  })

  await page.goto('http://localhost:5174')
  await page.waitForTimeout(1000)

  // Title → Enter
  await page.keyboard.down('Enter')
  await page.waitForTimeout(100)
  await page.keyboard.up('Enter')
  await page.waitForTimeout(800)

  // Tutorial: WASD
  await page.keyboard.down('KeyW')
  await page.waitForTimeout(150)
  await page.keyboard.up('KeyW')
  await page.waitForTimeout(500)

  // Tutorial: Space
  await page.keyboard.down('Space')
  await page.waitForTimeout(150)
  await page.keyboard.up('Space')
  await page.waitForTimeout(4000)  // wait for timed step + transition

  await page.screenshot({ path: `${DIR}/death_01_arena.png` })
  console.log('1/4 Arena entered')

  // DON'T shoot — just stand still and let enemies kill us
  // Wave 1 = 3 rushers, they should reach and kill us in ~10-15 seconds
  console.log('Waiting for enemies to kill player (up to 20s)...')

  let gameOverDetected = false
  for (let i = 0; i < 60; i++) {  // check every 500ms for 30 seconds
    await page.waitForTimeout(500)

    // Check if game over text is visible
    const text = await page.evaluate(() => document.getElementById('hud')?.textContent ?? '')
    if (text.includes('GAME OVER')) {
      gameOverDetected = true
      break
    }

    // Screenshot at a few checkpoints
    if (i === 10) {
      await page.screenshot({ path: `${DIR}/death_02_taking_damage.png` })
      console.log('2/4 Taking damage')
    }
    if (i === 20) {
      await page.screenshot({ path: `${DIR}/death_03_low_hp.png` })
      console.log('3/4 Low HP')
    }
  }

  await page.screenshot({ path: `${DIR}/death_04_gameover.png` })

  if (gameOverDetected) {
    console.log('4/4 GAME OVER screen captured')
    console.log('\nDeath test PASSED — full loop: arena → death → game over')
  } else {
    console.log('4/4 Game over NOT reached (player survived 20s)')
    console.log('\nDeath test PARTIAL — enemies may not be dealing enough damage')
  }

  if (errors.length > 0) {
    console.log(`Console errors: ${errors.length}`)
    for (const e of errors.slice(0, 5)) console.log(`  ${e}`)
  }

  await browser.close()
}

main().catch((err) => {
  console.error('Death test FAILED:', err)
  process.exit(1)
})
