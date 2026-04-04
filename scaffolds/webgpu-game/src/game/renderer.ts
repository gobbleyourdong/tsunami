/**
 * Arena renderer — Canvas 2D for immediate visuals.
 * WebGPU upgrade path: swap this for the engine's GPU renderer
 * when the pipeline is wired. Same draw calls, different backend.
 */

import type { PlayerController } from './player'
import type { EnemyManager, Enemy } from './enemies'
import type { ProjectileManager, Projectile } from './projectiles'
import type { PickupManager, Pickup } from './pickups'
import { PICKUP_COLORS } from './pickups'

const ARENA_SIZE = 12
const BG_COLOR = '#0a0a12'
const GRID_COLOR = '#1a1a2e'
const WALL_COLOR = '#4a9eff'
const PLAYER_COLOR = '#00ff88'
const PLAYER_AIM_COLOR = '#00ff8844'
const ENEMY_COLORS = { rusher: '#ff4444', shooter: '#ff8800', tank: '#cc44ff' }
const PROJ_PLAYER_COLOR = '#00ffcc'
const PROJ_ENEMY_COLOR = '#ff6644'

export class ArenaRenderer {
  private ctx: CanvasRenderingContext2D
  private canvas: HTMLCanvasElement
  private scale = 1
  private centerX = 0
  private centerY = 0
  private time = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D not supported')
    this.ctx = ctx
    this.resize()
    window.addEventListener('resize', () => this.resize())
  }

  private resize(): void {
    const dpr = window.devicePixelRatio || 1
    this.canvas.width = window.innerWidth * dpr
    this.canvas.height = window.innerHeight * dpr
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    this.centerX = window.innerWidth / 2
    this.centerY = window.innerHeight / 2
    this.scale = Math.min(window.innerWidth, window.innerHeight) / (ARENA_SIZE * 2.5)
  }

  /** Convert world coords to screen coords. */
  private toScreen(wx: number, wy: number): [number, number] {
    return [
      this.centerX + wx * this.scale,
      this.centerY + wy * this.scale,
    ]
  }

  render(
    dt: number,
    player: PlayerController,
    enemies: EnemyManager,
    projectiles: ProjectileManager,
    pickups: PickupManager
  ): void {
    this.time += dt
    const ctx = this.ctx

    // Clear
    ctx.fillStyle = BG_COLOR
    ctx.fillRect(0, 0, window.innerWidth, window.innerHeight)

    // Grid
    this.drawGrid()

    // Arena walls (glowing border)
    this.drawWalls()

    // Pickups
    for (const p of pickups.pickups) {
      this.drawPickup(p)
    }

    // Enemies
    for (const e of enemies.enemies) {
      this.drawEnemy(e)
    }

    // Projectiles
    for (const p of projectiles.projectiles) {
      this.drawProjectile(p)
    }

    // Player
    this.drawPlayer(player)
  }

  private drawGrid(): void {
    const ctx = this.ctx
    ctx.strokeStyle = GRID_COLOR
    ctx.lineWidth = 0.5
    ctx.beginPath()
    for (let i = -ARENA_SIZE; i <= ARENA_SIZE; i += 2) {
      const [x1, y1] = this.toScreen(i, -ARENA_SIZE)
      const [x2, y2] = this.toScreen(i, ARENA_SIZE)
      ctx.moveTo(x1, y1); ctx.lineTo(x2, y2)
      const [x3, y3] = this.toScreen(-ARENA_SIZE, i)
      const [x4, y4] = this.toScreen(ARENA_SIZE, i)
      ctx.moveTo(x3, y3); ctx.lineTo(x4, y4)
    }
    ctx.stroke()
  }

  private drawWalls(): void {
    const ctx = this.ctx
    const [x1, y1] = this.toScreen(-ARENA_SIZE, -ARENA_SIZE)
    const [x2, y2] = this.toScreen(ARENA_SIZE, ARENA_SIZE)
    const w = x2 - x1, h = y2 - y1

    // Glow
    const pulse = 0.5 + 0.3 * Math.sin(this.time * 2)
    ctx.shadowColor = WALL_COLOR
    ctx.shadowBlur = 15 * pulse
    ctx.strokeStyle = WALL_COLOR
    ctx.lineWidth = 2
    ctx.strokeRect(x1, y1, w, h)
    ctx.shadowBlur = 0
  }

  private drawPlayer(player: PlayerController): void {
    const ctx = this.ctx
    const [px, py] = this.toScreen(player.x, player.y)
    const r = player.radius * this.scale

    // Shield indicator
    if (player.shieldTimer > 0) {
      ctx.beginPath()
      ctx.arc(px, py, r + 6, 0, Math.PI * 2)
      ctx.strokeStyle = '#44ccff88'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Body
    ctx.beginPath()
    ctx.arc(px, py, r, 0, Math.PI * 2)
    ctx.fillStyle = player.speedBoostTimer > 0 ? '#44aaff' : PLAYER_COLOR
    ctx.fill()

    // Aim line
    const aimLen = 25
    ctx.beginPath()
    ctx.moveTo(px, py)
    ctx.lineTo(px + Math.cos(player.aimAngle) * aimLen, py + Math.sin(player.aimAngle) * aimLen)
    ctx.strokeStyle = PLAYER_AIM_COLOR
    ctx.lineWidth = 2
    ctx.stroke()

    // Rapid fire indicator
    if (player.rapidFireTimer > 0) {
      ctx.beginPath()
      ctx.arc(px, py, r * 0.4, 0, Math.PI * 2)
      ctx.fillStyle = '#ffcc00'
      ctx.fill()
    }
  }

  private drawEnemy(enemy: Enemy): void {
    const ctx = this.ctx
    const [ex, ey] = this.toScreen(enemy.x, enemy.y)
    const r = enemy.radius * this.scale

    if (enemy.dead) {
      // Death flash
      const alpha = enemy.deathTimer / 0.3
      ctx.beginPath()
      ctx.arc(ex, ey, r * (2 - alpha), 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 200, 100, ${alpha * 0.5})`
      ctx.fill()
      return
    }

    const color = ENEMY_COLORS[enemy.type]

    // Body
    ctx.beginPath()
    if (enemy.type === 'tank') {
      // Square-ish for tanks
      ctx.rect(ex - r, ey - r, r * 2, r * 2)
    } else {
      ctx.arc(ex, ey, r, 0, Math.PI * 2)
    }
    ctx.fillStyle = color
    ctx.fill()

    // Health bar (if damaged)
    if (enemy.health < enemy.maxHealth) {
      const barW = r * 2.5
      const barH = 3
      const barX = ex - barW / 2
      const barY = ey - r - 8
      ctx.fillStyle = '#333'
      ctx.fillRect(barX, barY, barW, barH)
      ctx.fillStyle = color
      ctx.fillRect(barX, barY, barW * (enemy.health / enemy.maxHealth), barH)
    }
  }

  private drawProjectile(proj: Projectile): void {
    const ctx = this.ctx
    const [px, py] = this.toScreen(proj.x, proj.y)
    const r = proj.radius * this.scale

    ctx.beginPath()
    ctx.arc(px, py, Math.max(r, 2), 0, Math.PI * 2)
    ctx.fillStyle = proj.owner === 'player' ? PROJ_PLAYER_COLOR : PROJ_ENEMY_COLOR

    // Glow
    ctx.shadowColor = ctx.fillStyle
    ctx.shadowBlur = 6
    ctx.fill()
    ctx.shadowBlur = 0
  }

  private drawPickup(pickup: Pickup): void {
    const ctx = this.ctx
    const bob = Math.sin(this.time * 3 + pickup.bobPhase) * 3
    const [px, py] = this.toScreen(pickup.x, pickup.y)
    const r = pickup.radius * this.scale

    // Pulsing glow
    const pulse = 0.7 + 0.3 * Math.sin(this.time * 4 + pickup.bobPhase)
    ctx.beginPath()
    ctx.arc(px, py + bob, r, 0, Math.PI * 2)
    ctx.fillStyle = PICKUP_COLORS[pickup.type]
    ctx.globalAlpha = pulse
    ctx.shadowColor = PICKUP_COLORS[pickup.type]
    ctx.shadowBlur = 10
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0

    // Blink when about to expire
    if (pickup.lifetime < 3 && Math.sin(this.time * 10) > 0) {
      ctx.globalAlpha = 0.3
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }
}
