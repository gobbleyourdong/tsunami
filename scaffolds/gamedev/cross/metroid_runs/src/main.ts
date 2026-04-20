/**
 * Metroid Runs — cross-genre canary #5.
 *
 * Procedurally-generated rooms per run (ProceduralRoomChain with
 * different seeds) + permanent ability progression (abilities
 * unlocked in one run carry forward). Tests the per-run-reset vs.
 * persistent-progression invariant — no prior canary splits state
 * along this axis.
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Run } from './scenes/Run'
import config from '../data/config.json'

const scene = new Run()

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

  scene.setup()

  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#9c6'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami canary — ${(config as any).meta?.title ?? 'Metroid Runs'}`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `scene: run · mechanics: ${scene.mechanicsActive()} / ${(mechanicRegistry as any).factories?.size ?? '?'} registered`,
      20, 52,
    )
    ctx.fillText(
      `${scene.description}`,
      20, 74,
    )

    // Rotating ability-slot indicators (persistent across runs).
    const slots = 6
    const cx = canvas!.width - 40
    const cy = 40
    for (let i = 0; i < slots; i++) {
      const angle = t / 800 + i * (Math.PI * 2 / slots)
      const sx = cx + Math.cos(angle) * 14
      const sy = cy + Math.sin(angle) * 14
      ctx.fillStyle = i < 3 ? '#9c6' : '#444'  // mock: 3 unlocked
      ctx.beginPath()
      ctx.arc(sx, sy, 3, 0, Math.PI * 2)
      ctx.fill()
    }

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
