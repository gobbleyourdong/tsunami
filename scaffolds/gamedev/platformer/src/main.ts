/**
 * Platformer scaffold entrypoint.
 *
 * Scene flow: Title → Level → GameOver → (Title on continue).
 *
 * Agent customization paths:
 *  - data/config.json      — starting_level, lives_start, scoring_mode, win_condition
 *  - data/player.json      — movement params (walk_speed, jump_height, coyote_frames, dash_distance)
 *  - data/enemies.json     — 5-7 enemy archetypes with Health + AI kind
 *  - data/powerups.json    — mushroom/fire-flower/star/1up/dash-token/weapon-pickup
 *  - data/levels.json      — 4-5 levels with checkpoints + exit + secret_areas
 *  - data/mechanics.json   — 9 mechanic instances (PhysicsModifier tunes gravity)
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (SMB + Mega Man 2 + Celeste per JOB-G).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Title } from './scenes/Title'
import { Level } from './scenes/Level'
import { GameOver } from './scenes/GameOver'
import config from '../data/config.json'

type SceneKey = 'title' | 'level' | 'gameover'
const scenes = {
  title: new Title(),
  level: new Level(),
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
    ctx.fillStyle = '#7dd'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami platformer — ${(config as any).meta?.title ?? 'Platformer'}`,
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

    // Jump-pulse indicator.
    const y = 30 + Math.abs(Math.sin(t / 500)) * -20
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, y, 8, 0, Math.PI * 2)
    ctx.fillStyle = '#7dd'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
