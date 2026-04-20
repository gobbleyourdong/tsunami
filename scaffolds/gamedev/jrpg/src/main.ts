/**
 * JRPG scaffold entrypoint.
 *
 * Scene flow: Title → World → Town → Battle → (loop back to World on
 * victory / fled, to Title on defeat).
 *
 * Agent customization paths:
 *  - data/party.json        — 4-member party roster + components + formations
 *  - data/world_map.json    — 8 regions + connections + encounter tables
 *  - data/battles.json      — 5 grunts + 3 bosses + encounter groups
 *  - data/spells.json       — 12 spells across offense/heal/status trees
 *  - data/equipment.json    — 15 items across weapon/armor/accessory slots
 *  - data/mechanics.json    — 9 mechanic instances (ATBCombat + the v1.2 cluster)
 *  - data/config.json       — starting region, combat_style, win/lose conditions
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (FF4 + DQ3 + Chrono
 * Trigger per JOB-F).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Title } from './scenes/Title'
import { World } from './scenes/World'
import { Town } from './scenes/Town'
import { Battle } from './scenes/Battle'
import config from '../data/config.json'

type SceneKey = 'title' | 'world' | 'town' | 'battle'
const scenes = {
  title: new Title(),
  world: new World(),
  town: new Town(),
  battle: new Battle(),
}
let active: SceneKey = 'title'

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
    ctx.fillStyle = '#8cf'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami jrpg — ${(config as any).meta?.title ?? 'JRPG Scaffold'}`,
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

    // ATB-pulse indicator (top-right).
    const r = 8 + Math.sin(t / 300) * 3
    ctx.beginPath()
    ctx.arc(canvas!.width - 30, 30, r, 0, Math.PI * 2)
    ctx.fillStyle = '#8cf'
    ctx.fill()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
