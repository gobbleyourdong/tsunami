/**
 * Puzzle Platformer Roguelite — cross-genre scaffold.
 *
 * Catherine block-pushing × Celeste movement × Into-the-Breach run
 * structure. Proves puzzle + platformer + roguelite composes from
 * @engine/mechanics alone.
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Run } from './scenes/Run'
import config from '../data/config.json'

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) throw new Error('#game-canvas not found')

const run = new Run()

function boot(): void {
  const ctx = canvas!.getContext('2d')
  if (!ctx) throw new Error('2D canvas context unavailable')

  const resize = () => {
    canvas!.width = canvas!.clientWidth
    canvas!.height = canvas!.clientHeight
  }
  resize()
  window.addEventListener('resize', resize)

  run.setup()

  const render = (t: number) => {
    ctx.fillStyle = '#10151c'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#8ecae6'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `${config.meta?.title ?? 'Puzzle Platformer Roguelite'} — cross-genre`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `mechanics wired: ${run.mechanicsActive()} / registry size: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(`${run.description}`, 20, 74)

    const r = 8 + Math.sin(t / 500) * 3
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#8ecae6'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
