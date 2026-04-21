/**
 * Bullet Hell RPG — cross-genre scaffold.
 *
 * Proves that bullet-hell arcade + RPG progression can compose from
 * @engine/mechanics alone. If adding a new genre combo here requires
 * a new Layer 1/2 mechanic, the abstraction is leaking — push the
 * fix up to the engine, not this scaffold.
 *
 * Heritage mix: bullet-hell (BulletPattern/WaveSpawner/BossPhases/
 * ScoreCombos/Difficulty) + rpg (LevelUpProgression/EquipmentLoadout/
 * StatusStack) + universal (HUD/CameraFollow/LoseOnZero/CheckpointProgression)
 * + fighting-heritage AttackFrames for the player's own shot hitboxes.
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
    ctx.fillStyle = '#0a0c12'
    ctx.fillRect(0, 0, canvas!.width, canvas!.height)
    ctx.fillStyle = '#ffb84a'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `${config.meta?.title ?? 'Bullet Hell RPG'} — cross-genre scaffold`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `mechanics wired: ${run.mechanicsActive()} / registry size: ${(mechanicRegistry as any).factories?.size ?? '?'}`,
      20, 52,
    )
    ctx.fillText(
      `${run.description}`,
      20, 74,
    )

    const r = 8 + Math.sin(t / 300) * 3
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#ffb84a'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
