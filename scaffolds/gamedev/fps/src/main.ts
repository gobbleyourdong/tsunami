/**
 * FPS scaffold entrypoint.
 *
 * Scene flow: Title → Level → GameOver → (Title on continue).
 *
 * Agent customization paths:
 *  - data/config.json      — starting_level, starting_weapons, starting_ammo, difficulty
 *  - data/player.json      — Health + Armor + Ammo pools per weapon family
 *  - data/weapons.json     — 6-9 weapons with damage/ammo/spread/rate/projectile_kind
 *  - data/enemies.json     — 4-6 archetypes (zombie/soldier/heavy/flying/boss)
 *  - data/levels.json      — 3-4 levels as room-graph with keycards/switches/exit
 *  - data/mechanics.json   — 9 mechanic instances (BulletPattern + WaveSpawner + ...)
 *
 * Seed attribution: see data/SEED_ATTRIBUTION.md (Doom + Quake + Half-Life per JOB-H).
 */

import { mechanicRegistry } from '@engine/mechanics'
import { Title } from './scenes/Title'
import { Level } from './scenes/Level'
import { GameOver } from './scenes/GameOver'
import config from '../data/config.json'

type SceneKey = 'title' | 'level' | 'gameover'
const scenes = {
  title: new Title(),
  level: new Level(),
  gameover: new GameOver(),
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
    ctx.fillStyle = '#f86'
    ctx.font = '14px system-ui, sans-serif'
    ctx.fillText(
      `tsunami fps — ${(config as any).meta?.title ?? 'FPS Scaffold'}`,
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

    // Crosshair pulse
    const cx = canvas!.width / 2
    const cy = canvas!.height / 2
    ctx.strokeStyle = '#f86'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    const r = 10 + Math.sin(t / 200) * 2
    ctx.moveTo(cx - r, cy); ctx.lineTo(cx - 3, cy)
    ctx.moveTo(cx + 3, cy); ctx.lineTo(cx + r, cy)
    ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy - 3)
    ctx.moveTo(cx, cy + 3); ctx.lineTo(cx, cy + r)
    ctx.stroke()

    requestAnimationFrame(render)
  }
  requestAnimationFrame(render)
}

boot()
