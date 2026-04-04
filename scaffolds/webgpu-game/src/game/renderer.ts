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
const ENEMY_COLORS: Record<string, string> = { rusher: '#ff4444', shooter: '#ff8800', tank: '#cc44ff', boss: '#ff0066' }
const PROJ_PLAYER_COLOR = '#00ffcc'
const PROJ_ENEMY_COLOR = '#ff6644'

interface FXParticle {
  x: number; y: number
  vx: number; vy: number
  life: number; maxLife: number
  size: number; color: string
}

export class ArenaRenderer {
  private ctx: CanvasRenderingContext2D
  private canvas: HTMLCanvasElement
  private scale = 1
  private centerX = 0
  private centerY = 0
  private time = 0
  private particles: FXParticle[] = []
  screenShake = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D not supported')
    this.ctx = ctx
    this.resize()
    window.addEventListener('resize', () => this.resize())
  }

  /** Clear canvas to black (for non-arena scenes). */
  clear(): void {
    this.ctx.fillStyle = '#0a0a12'
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height)
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

  /** Spawn explosion particles at world position. */
  spawnExplosion(wx: number, wy: number, color: string, count = 12): void {
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5
      const speed = 40 + Math.random() * 60
      this.particles.push({
        x: wx, y: wy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.3 + Math.random() * 0.2,
        maxLife: 0.5,
        size: 2 + Math.random() * 3,
        color,
      })
    }
  }

  /** Spawn hit sparks (smaller, fewer). */
  spawnSparks(wx: number, wy: number, count = 5): void {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2
      const speed = 30 + Math.random() * 40
      this.particles.push({
        x: wx, y: wy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.15 + Math.random() * 0.1,
        maxLife: 0.25,
        size: 1.5 + Math.random() * 1.5,
        color: '#ffffff',
      })
    }
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

    // Update particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i]
      p.x += p.vx * dt
      p.y += p.vy * dt
      p.vx *= 0.95; p.vy *= 0.95
      p.life -= dt
      if (p.life <= 0) this.particles.splice(i, 1)
    }

    // Screen shake
    let shakeX = 0, shakeY = 0
    if (this.screenShake > 0) {
      shakeX = (Math.random() - 0.5) * this.screenShake * 8
      shakeY = (Math.random() - 0.5) * this.screenShake * 8
      this.screenShake *= 0.9
      if (this.screenShake < 0.01) this.screenShake = 0
    }

    ctx.save()
    ctx.translate(shakeX, shakeY)

    // Clear
    ctx.fillStyle = BG_COLOR
    ctx.fillRect(-10, -10, window.innerWidth + 20, window.innerHeight + 20)

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

    // FX particles
    for (const p of this.particles) {
      const [sx, sy] = this.toScreen(p.x, p.y)
      const alpha = p.life / p.maxLife
      ctx.beginPath()
      ctx.arc(sx, sy, p.size * alpha, 0, Math.PI * 2)
      ctx.fillStyle = p.color
      ctx.globalAlpha = alpha
      ctx.shadowColor = p.color
      ctx.shadowBlur = 4
      ctx.fill()
      ctx.shadowBlur = 0
      ctx.globalAlpha = 1
    }

    ctx.restore()
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

    const color = ENEMY_COLORS[enemy.type] ?? '#ff4444'

    // Boss: outer pulsing ring + phase glow
    if (enemy.type === 'boss') {
      const hpPct = enemy.health / enemy.maxHealth
      const phase = hpPct > 0.5 ? 1 : hpPct > 0.25 ? 2 : 3
      const phaseColor = phase === 1 ? '#ff0066' : phase === 2 ? '#ff4400' : '#ff0000'
      const pulse = 0.6 + 0.4 * Math.sin(this.time * 3 * phase)

      // Outer danger ring
      ctx.beginPath()
      ctx.arc(ex, ey, r + 8 * pulse, 0, Math.PI * 2)
      ctx.strokeStyle = phaseColor
      ctx.lineWidth = 2
      ctx.globalAlpha = pulse * 0.6
      ctx.stroke()
      ctx.globalAlpha = 1

      // Inner ring
      ctx.beginPath()
      ctx.arc(ex, ey, r + 3, 0, Math.PI * 2)
      ctx.strokeStyle = phaseColor
      ctx.lineWidth = 1.5
      ctx.shadowColor = phaseColor
      ctx.shadowBlur = 12
      ctx.stroke()
      ctx.shadowBlur = 0
    }

    // Body
    ctx.beginPath()
    if (enemy.type === 'tank' || enemy.type === 'boss') {
      // Square-ish for tanks and boss
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
    const r = Math.max(proj.radius * this.scale, 3)
    const color = proj.owner === 'player' ? PROJ_PLAYER_COLOR : PROJ_ENEMY_COLOR

    // Trail line (velocity direction, fading)
    const speed = Math.sqrt(proj.vx * proj.vx + proj.vy * proj.vy)
    if (speed > 0) {
      const trailLen = 8
      const nx = -proj.vx / speed
      const ny = -proj.vy / speed
      const gradient = ctx.createLinearGradient(px, py, px + nx * trailLen, py + ny * trailLen)
      gradient.addColorStop(0, color)
      gradient.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.moveTo(px, py)
      ctx.lineTo(px + nx * trailLen, py + ny * trailLen)
      ctx.strokeStyle = gradient
      ctx.lineWidth = r * 1.5
      ctx.stroke()
    }

    // Bullet head (glowing)
    ctx.beginPath()
    ctx.arc(px, py, r, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.shadowColor = color
    ctx.shadowBlur = 8
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
