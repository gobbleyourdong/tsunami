/**
 * Beat-em-up scaffold entrypoint.
 *
 * Scene flow: Title → Stage → GameOver → (Title on restart).
 *
 * Agent customization paths:
 *  - data/config.json      — starting_stage, starting_character, lives_per_continue, difficulty
 *  - data/characters.json  — 3 playable brawler archetypes (haymaker/speed/grappler)
 *  - data/enemies.json     — 6-8 enemy archetypes (grunt / knife-grunt / fatboy / runner / mid-boss)
 *  - data/stages.json      — 4-6 stage blocks with boss-gate + spawn waves
 *  - data/moves.json       — per-character combos + grab + special + throw w/ frame data
 *  - data/pickups.json     — 6-8 ground items (knife / pipe / chicken / jewels)
 *  - data/rules.json       — co-op, continues, arcade-continue-timer, boss-gate-per-stage
 *  - data/mechanics.json   — 9 mechanic instances (ComboAttacks + WaveSpawner + ...)
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (Final Fight + Streets of Rage 2 + TMNT per JOB-INT-7).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Title } from './scenes/Title'
import { Stage } from './scenes/Stage'
import { GameOver } from './scenes/GameOver'
import config from '../data/config.json'

type SceneKey = 'title' | 'stage' | 'gameover'
const scenes = {
  title: new Title(),
  stage: new Stage(),
  gameover: new GameOver(),
}
let active: SceneKey = 'title'

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) throw new Error('#game-canvas not found')

function boot(): void {
  const ctx = canvas!.getContext('2d')
  if (!ctx) throw new Error('2D canvas context unavailable')

  const resize = () => {
    canvas!.width = canvas!.clientWidth
    canvas!.height = canvas!.clientHeight
  }
  resize()
  window.addEventListener('resize', resize)

  scenes[active].setup()

  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#f96'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami beat-em-up — ${(config as any).meta?.title ?? 'Beat-em-up'}`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `scene: ${active} · mechanics: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(
      `${scenes[active].description}`,
      20, 74,
    )

    // Scrolling-forward arcade arrow indicator.
    const cx = canvas!.width - 40
    const cy = 40
    const offset = (t / 60) % 20
    ctx.strokeStyle = '#f96'
    ctx.lineWidth = 2
    for (let i = 0; i < 3; i++) {
      const x = cx - i * 8 - offset
      ctx.beginPath()
      ctx.moveTo(x, cy - 6)
      ctx.lineTo(x + 6, cy)
      ctx.lineTo(x, cy + 6)
      ctx.stroke()
    }

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
