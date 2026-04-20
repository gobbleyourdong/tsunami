/**
 * Fighting scaffold entrypoint.
 *
 * Scene flow: CharSelect → VsScreen → Fight → Victory.
 * Agent customization paths:
 *  - data/characters.json — roster + stats + sprite refs + move_list_ref
 *  - data/moves.json      — per-character move tables (inputs, frames, damage)
 *  - data/stages.json     — stage backgrounds + affinities + fatality flags
 *  - data/config.json     — rounds/match, timer, super_meter cap, win_condition
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (Street Fighter II +
 * Mortal Kombat II + Tekken 3 per JOB-E).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { CharSelect } from './scenes/CharSelect'
import { VsScreen } from './scenes/VsScreen'
import { Fight } from './scenes/Fight'
import { Victory } from './scenes/Victory'
import config from '../data/config.json'

type SceneKey = 'char_select' | 'vs_screen' | 'fight' | 'victory'
const scenes = {
  char_select: new CharSelect(),
  vs_screen: new VsScreen(),
  fight: new Fight(),
  victory: new Victory(),
}
let active: SceneKey = 'char_select'

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
    ctx.fillStyle = '#e97'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami fighting — ${config.meta?.title ?? 'Fighter'}`,
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

    // Round timer pulse
    const r = 10 + Math.sin(t / 400) * 4
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#e97'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
