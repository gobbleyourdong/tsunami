/**
 * Racing scaffold entrypoint.
 *
 * Scene flow: Title → Race → Finish → (Title on restart).
 *
 * Agent customization paths:
 *  - data/config.json      — starting_track, laps_per_race, racer_count, difficulty
 *  - data/tracks.json      — 3-5 tracks with checkpoints + theme
 *  - data/vehicles.json    — 4-6 vehicles with top_speed/acceleration/handling/weight
 *  - data/racers.json      — player + 3-5 AI racer archetypes with AI kind
 *  - data/powerups.json    — kart-style boost/shell/banana OR sim-style tuning parts
 *  - data/mechanics.json   — 8 mechanic instances (CheckpointProgression + ...)
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (Out Run + Mario Kart + Gran Turismo per JOB-T).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Title } from './scenes/Title'
import { Race } from './scenes/Race'
import { Finish } from './scenes/Finish'
import config from '../data/config.json'

type SceneKey = 'title' | 'race' | 'finish'
const scenes = {
  title: new Title(),
  race: new Race(),
  finish: new Finish(),
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
    ctx.fillStyle = '#fe4'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami racing — ${(config as any).meta?.title ?? 'Racing Scaffold'}`,
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

    // Speed-blur sweep indicator.
    ctx.strokeStyle = '#fe4'
    ctx.lineWidth = 2
    const ox = canvas!.width - 120
    const oy = 30
    for (let i = 0; i < 5; i++) {
      const phase = (t / 150 + i * 10) % 100
      ctx.globalAlpha = 1 - phase / 100
      ctx.beginPath()
      ctx.moveTo(ox + phase, oy)
      ctx.lineTo(ox + phase + 20, oy)
      ctx.stroke()
    }
    ctx.globalAlpha = 1

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
