/**
 * Rhythm Fighter — cross-genre canary #3.
 *
 * Architectural-correctness gate for timing-coordination: if AttackFrames
 * can read beat-phase from RhythmTrack and apply damage multipliers
 * per-hit, the framework's mechanic-to-mechanic coupling works without
 * new runtime types.
 *
 * Single-scene canary (paralleling magic_hoops + ninja_garden pattern).
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

  const bpm = (config as any).match_rules?.on_beat_window_beats ? 120 : 120
  const beatPeriodMs = 60000 / bpm

  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#fc6'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami canary — ${(config as any).meta?.title ?? 'Rhythm Fighter'}`,
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

    // On-beat pulse indicator (drawn bigger on each beat).
    const phase = (t % beatPeriodMs) / beatPeriodMs
    const pulse = Math.max(0, 1 - phase * 2)  // peak at start-of-beat
    const cx = canvas!.width - 40
    const cy = 40
    ctx.beginPath()
    ctx.arc(cx, cy, 8 + pulse * 12, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(255, 204, 102, ${0.3 + pulse * 0.7})`
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
