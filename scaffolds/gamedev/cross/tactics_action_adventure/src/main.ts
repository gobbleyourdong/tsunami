/**
 * Tactics Action Adventure — cross-genre scaffold.
 *
 * Octopath overworld × Zelda real-time exploration × Fire Emblem
 * combat encounters. Two-mode scene: action overworld drops into
 * tactics combat on enemy contact. Adventure heritage wraps both
 * with dialog / hotspots / world-map travel / branching endings.
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Adventure } from './scenes/Adventure'
import config from '../data/config.json'

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) throw new Error('#game-canvas not found')

const adventure = new Adventure()

function boot(): void {
  const ctx = canvas!.getContext('2d')
  if (!ctx) throw new Error('2D canvas context unavailable')

  const resize = () => {
    canvas!.width = canvas!.clientWidth
    canvas!.height = canvas!.clientHeight
  }
  resize()
  window.addEventListener('resize', resize)

  adventure.setup()

  const render = (t: number) => {
    ctx.fillStyle = '#1c1614'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#d4a464'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `${config.meta?.title ?? 'Tactics Action Adventure'} — cross-genre`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `mechanics wired: ${adventure.mechanicsActive()} / registry size: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(`${adventure.description}`, 20, 74)

    const r = 8 + Math.sin(t / 450) * 3
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#d4a464'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
