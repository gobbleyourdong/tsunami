/**
 * Magic Hoops — cross-genre canary.
 *
 * Architecture-correctness test: build a sports + fighting + RPG hybrid
 * by PURE COMPOSITION from @engine/mechanics. If this scaffold needs
 * to add ANY new Layer 1/2 code, the abstractions are leaking genre
 * assumptions and Layer 1/2 should be refactored.
 *
 * Mechanics used (ALL from @engine/mechanics, ALL pre-existing):
 *   from "fighting" heritage: ComboAttacks, AttackFrames (spell hitboxes)
 *   from "sports" heritage:   (none direct — Scoreboard/GameClock built from HUD + WinOnCount)
 *   from "rpg" heritage:      ItemUse (spell cast dispatch), StatusStack (buffs/debuffs)
 *   from "action" heritage:   CameraFollow, HUD, CheckpointProgression (respawn)
 *   win/lose logic:           WinOnCount (first to N goals), LoseOnZero (fighter KO)
 *
 * This file is identical in shape to fighting/action_adventure main.ts.
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Match } from './scenes/Match'
import config from '../data/config.json'

const canvas = document.getElementById('game-canvas') as HTMLCanvasElement | null
if (!canvas) throw new Error('#game-canvas not found')

const match = new Match()

function boot(): void {
  const ctx = canvas!.getContext('2d')
  if (!ctx) throw new Error('2D canvas context unavailable')

  const resize = () => {
    canvas!.width = canvas!.clientWidth
    canvas!.height = canvas!.clientHeight
  }
  resize()
  window.addEventListener('resize', resize)

  match.setup()

  const render = (t: number) => {
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#c7e'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `${config.meta?.title ?? 'Magic Hoops'} — cross-genre canary`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `mechanics wired: ${match.mechanicsActive()} / registry size: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(
      `${match.description}`,
      20, 74,
    )

    // Pulse
    const r = 10 + Math.sin(t / 400) * 4
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#c7e'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
