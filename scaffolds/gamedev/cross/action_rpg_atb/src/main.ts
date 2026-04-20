/**
 * Action-RPG ATB — cross-genre canary #4.
 *
 * Unlike the single-scene canaries (magic_hoops / ninja_garden /
 * rhythm_fighter), this one ships TWO scenes — Field + Battle — that
 * exchange state on transition. The party roster (PartyComposition),
 * per-member HP/MP, inventory, and equipment (EquipmentLoadout) must
 * persist from Field into Battle and back.
 *
 * Architectural-correctness invariant: scene-boundary state
 * persistence. If a party member's HP drops to 0 in Battle, they
 * stay KO'd on return to Field. Equipment swaps in Battle stick in
 * Field. etc.
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Field } from './scenes/Field'
import { Battle } from './scenes/Battle'
import config from '../data/config.json'

type SceneKey = 'field' | 'battle'
const scenes = {
  field: new Field(),
  battle: new Battle(),
}
let active: SceneKey = 'field'

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
    ctx.fillStyle = '#6ac'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami canary — ${(config as any).meta?.title ?? 'Action-RPG ATB'}`,
      20, 30,
    )
    ctx.fillStyle = '#aaa'
    ctx.fillText(
      `scene: ${active} · mechanics: ${scenes[active].mechanicsActive()} / ${(mechanicRegistry as any).factories?.size ?? '?'} registered`,
      20, 52,
    )
    ctx.fillText(
      `${scenes[active].description}`,
      20, 74,
    )

    // Field-to-battle transition diamond (pulses when active scene flips).
    const cx = canvas!.width - 40
    const cy = 40
    const size = 10 + Math.sin(t / 500) * 3
    ctx.fillStyle = active === 'field' ? '#6c9' : '#c96'
    ctx.beginPath()
    ctx.moveTo(cx, cy - size)
    ctx.lineTo(cx + size, cy)
    ctx.lineTo(cx, cy + size)
    ctx.lineTo(cx - size, cy)
    ctx.closePath()
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
