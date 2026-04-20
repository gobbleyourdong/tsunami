/**
 * Action-adventure scaffold entrypoint.
 *
 * Boots the Overworld scene with seed data from data/*.json. Wave
 * customization primarily happens in:
 *  - data/entities.json   — enemy archetypes, player, bosses
 *  - data/rooms.json      — overworld + dungeon layout
 *  - data/items.json      — sword, bow, bomb, key, heart, compass
 *  - data/mechanics.json  — CameraFollow / RoomGraph / LockAndKey / ItemUse / HUD / Checkpoint
 *  - data/config.json     — starting room, player HP, viewport
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (sourced from
 * 1986_legend_of_zelda essence via JOB-D).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Overworld } from './scenes/Overworld'
import { Dungeon } from './scenes/Dungeon'
import { GameOver } from './scenes/GameOver'
import config from '../data/config.json'

// Minimal scene-stack — production scaffolds use Game + SceneManager
// from @engine/game; this stub is enough for the heartbeat.
type SceneKey = 'overworld' | 'dungeon' | 'gameover'
const scenes = {
  overworld: new Overworld(),
  dungeon: new Dungeon(),
  gameover: new GameOver(),
}
let active: SceneKey = (config.starting_scene as SceneKey) ?? 'overworld'

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

  // Mount the starting scene.
  scenes[active].setup()

  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#9c7'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami action-adventure — ${config.title ?? 'Zelda-like'}`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `scene: ${active} · mechanics registered: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(
      `rooms loaded: ${scenes[active].description}`,
      20, 74,
    )

    // Heartbeat
    const r = 10 + Math.sin(t / 400) * 4
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#9c7'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
