/**
 * Ninja Garden — cross-genre canary #2.
 *
 * Architectural-correctness gate: if this composes from the 12 listed
 * mechanics in `@engine/mechanics` ALONE with no new runtime types,
 * the framework's Layer 1/2 abstractions handle sandbox + action +
 * stealth composition. magic_hoops tested sports+fighting+RPG; this
 * tests sandbox+action+stealth.
 *
 * Single-scene canary (paralleling magic_hoops pattern).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Match } from './scenes/Match'
import config from '../data/config.json'

const scene = new Match()

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
    ctx.fillStyle = '#c9c'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami canary — ${(config as any).meta?.title ?? 'Ninja Garden'}`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `scene: match · mechanics: ${scene.mechanicsActive()} / ${(mechanicRegistry as any).factories?.size ?? '?'} registered`,
      20, 52,
    )
    ctx.fillText(
      `${scene.description}`,
      20, 74,
    )

    // Shuriken orbit indicator.
    const cx = canvas!.width - 40
    const cy = 40
    for (let i = 0; i < 4; i++) {
      const angle = t / 400 + i * (Math.PI / 2)
      const sx = cx + Math.cos(angle) * 14
      const sy = cy + Math.sin(angle) * 14
      ctx.fillStyle = '#c9c'
      ctx.fillRect(sx - 2, sy - 2, 4, 4)
    }

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
