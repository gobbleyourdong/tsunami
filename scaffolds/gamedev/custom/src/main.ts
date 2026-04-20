/**
 * Custom scaffold entrypoint.
 *
 * Boots Layer 0 (Game harness + scene manager) and mounts MainScene.
 * Genre scaffolds extend this — they override src/scenes/ and populate
 * src/data/*.json but keep this main.ts unchanged in 90% of cases.
 *
 * To customize:
 * - Edit data/config.json for game-level settings (mode, viewport, physics)
 * - Edit src/scenes/MainScene.ts to compose mechanics from @engine/mechanics
 * - Add more scenes under src/scenes/ and register them below
 */

import { mechanicRegistry } from '@engine/mechanics'
import { MainScene } from './scenes/MainScene'
import config from '../data/config.json'

// Mounting point: the canvas in index.html.
const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) {
  throw new Error('#game-canvas not found in DOM')
}

/** Simple 2D bootstrap — draws a heartbeat to prove the loop runs.
 *  Genre scaffolds replace this with a real Game + SceneManager. */
function boot(): void {
  const ctx = canvas!.getContext('2d')
  if (!ctx) {
    console.error('2D canvas context unavailable')
    return
  }

  // Resize to viewport
  const resize = () => {
    canvas!.width = canvas!.clientWidth
    canvas!.height = canvas!.clientHeight
  }
  resize()
  window.addEventListener('resize', resize)

  // Instantiate MainScene (inert until we wire a proper SceneManager)
  const scene = new MainScene()
  scene.setup()

  // Diagnostic render
  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#7af'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami gamedev scaffold — ${config.title ?? 'custom'}`,
      20, 30,
    )
    ctx.fillStyle = '#888'
    ctx.fillText(
      `mechanics registered: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(
      `scene: ${scene.name} · iter ${(t / 1000).toFixed(1)}s`,
      20, 74,
    )
    // Pulse circle — proof the RAF loop is ticking
    const r = 10 + Math.sin(t / 400) * 4
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#7af'
    ctx.fill()
    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
