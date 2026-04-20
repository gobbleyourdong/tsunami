/**
 * Stealth scaffold entrypoint.
 *
 * Scene flow: Title → Level → GameOver → (Title on continue).
 *
 * Agent customization paths:
 *  - data/config.json      — starting_level, starting_inventory, alarm_tolerance, win_condition
 *  - data/player.json      — Health + Stealth meter + Inventory
 *  - data/guards.json      — 3-5 archetypes with vision_cone params + patrol_path_ref
 *  - data/tools.json       — 5-7 player tools (silenced pistol, smoke grenade, body drag, ...)
 *  - data/levels.json      — 3-4 levels with patrol_paths + hiding_spots + extraction_points
 *  - data/mechanics.json   — 9 mechanic instances (VisionCone + ...)
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (MGS + Thief + Splinter Cell per JOB-R).
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
    ctx.fillStyle = '#8a6'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami stealth — ${(config as any).meta?.title ?? 'Stealth Scaffold'}`,
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

    // Detection-cone sweep indicator.
    const cx = canvas!.width - 40
    const cy = 40
    const sweep = Math.sin(t / 800) * 0.6
    ctx.strokeStyle = '#8a6'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, 16, -0.3 + sweep, 0.3 + sweep)
    ctx.closePath()
    ctx.stroke()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
