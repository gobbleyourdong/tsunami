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

  // Sprite atlas — loaded images keyed by name
  private sprites = new Map<string, HTMLImageElement>()
  private spritesLoading = false
  spritesReady = false

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D not supported')
    this.ctx = ctx
    this.resize()
    window.addEventListener('resize', () => this.resize())
    this.loadSprites()
  }

  /** Load all game sprites from public/sprites/. Fallback to shapes if any fail. */
  private loadSprites(): void {
    this.spritesLoading = true
    const manifest: Record<string, string> = {
      // Characters
      'player':    '/sprites/character/player_warrior/player_warrior_best.png',
      'rusher':    '/sprites/character/enemy_goblin/enemy_goblin_best.png',
      'shooter':   '/sprites/character/enemy_bat/enemy_bat_best.png',
      'tank':      '/sprites/character/enemy_ghost/enemy_ghost_best.png',
      'boss':      '/sprites/character/boss_dragon/boss_dragon_best.png',
      // Objects
      'proj_player': '/sprites/object/proj_fireball/proj_fireball_best.png',
      'proj_enemy':  '/sprites/object/proj_magic/proj_magic_best.png',
      'pickup_health':    '/sprites/object/item_potion_red/item_potion_red_best.png',
      'pickup_speed':     '/sprites/object/item_potion_blue/item_potion_blue_best.png',
      'pickup_rapidfire': '/sprites/object/item_gem/item_gem_best.png',
      'pickup_shield':    '/sprites/object/item_shield/item_shield_best.png',
      // Backgrounds
      'bg_sky':       '/sprites/texture/bg_sky/bg_sky_best.png',
      'bg_mountains': '/sprites/texture/bg_mountains/bg_mountains_best.png',
      'bg_city':      '/sprites/texture/bg_city/bg_city_best.png',
      // UI
      'ui_heart': '/sprites/object/ui_heart/ui_heart_best.png',
    }

    let loaded = 0
    const total = Object.keys(manifest).length

    for (const [name, path] of Object.entries(manifest)) {
      const img = new Image()
      img.onload = () => {
        this.sprites.set(name, img)
        loaded++
        if (loaded >= total) {
          this.spritesReady = true
          this.spritesLoading = false
          console.log(`[renderer] ${loaded} sprites loaded`)
        }
      }
      img.onerror = () => {
        loaded++
        console.warn(`[renderer] Failed to load sprite: ${name} (${path})`)
        if (loaded >= total) {
          this.spritesReady = true
          this.spritesLoading = false
        }
      }
      img.src = path
    }
  }

  /** Draw a sprite centered at screen position. Falls back to circle if not loaded. */
  private drawSprite(name: string, sx: number, sy: number, size: number, fallbackColor: string): void {
    const ctx = this.ctx
    const sprite = this.sprites.get(name)
    if (sprite) {
      const hw = size / 2
      // Maintain aspect ratio
      const aspect = sprite.width / sprite.height
      const drawW = aspect >= 1 ? size : size * aspect
      const drawH = aspect >= 1 ? size / aspect : size
      ctx.drawImage(sprite, sx - drawW / 2, sy - drawH / 2, drawW, drawH)
    } else {
      // Fallback: colored circle
      ctx.beginPath()
      ctx.arc(sx, sy, size / 2, 0, Math.PI * 2)
      ctx.fillStyle = fallbackColor
      ctx.fill()
    }
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

    // Parallax background layers (behind grid)
    this.drawParallaxLayer('bg_sky', 0.02, 0)       // slowest, furthest back
    this.drawParallaxLayer('bg_mountains', 0.05, 0.6) // mid layer
    this.drawParallaxLayer('bg_city', 0.1, 0.75)     // closest bg layer

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

  /** Draw a tiling parallax background layer. */
  private drawParallaxLayer(spriteName: string, scrollSpeed: number, yPosition: number): void {
    const sprite = this.sprites.get(spriteName)
    if (!sprite) return

    const ctx = this.ctx
    const w = window.innerWidth
    const h = window.innerHeight

    // Scale sprite to fill width while maintaining aspect
    const spriteAspect = sprite.width / sprite.height
    const drawH = h * 0.3  // each layer is ~30% of screen height
    const drawW = drawH * spriteAspect

    // Scroll based on time
    const offset = (this.time * scrollSpeed * w) % drawW
    const y = h * yPosition

    ctx.globalAlpha = 0.6
    // Tile horizontally
    for (let x = -offset; x < w + drawW; x += drawW) {
      ctx.drawImage(sprite, x, y, drawW, drawH)
    }
    ctx.globalAlpha = 1
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

    // Body — sprite or fallback circle
    const spriteSize = r * 3.5  // sprite is bigger than collision radius
    this.drawSprite('player', px, py, spriteSize, player.speedBoostTimer > 0 ? '#44aaff' : PLAYER_COLOR)

    // Aim line
    const aimLen = 25
    ctx.beginPath()
    ctx.moveTo(px, py)
    ctx.lineTo(px + Math.cos(player.aimAngle) * aimLen, py + Math.sin(player.aimAngle) * aimLen)
    ctx.strokeStyle = PLAYER_AIM_COLOR
    ctx.lineWidth = 2
    ctx.stroke()
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

    // Body — sprite by enemy type
    const spriteSize = r * 3.5
    this.drawSprite(enemy.type, ex, ey, spriteSize, color)

    // Health bar (if damaged)
    if (enemy.health < enemy.maxHealth) {
      const barW = r * 2.5
      const barH = 3
      const barX = ex - barW / 2
      const barY = ey - r - spriteSize * 0.5 - 4
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

    // Bullet head — sprite or glowing circle
    const spriteName = proj.owner === 'player' ? 'proj_player' : 'proj_enemy'
    const spriteSize = Math.max(r * 3, 8)
    this.drawSprite(spriteName, px, py, spriteSize, color)

    // Glow behind sprite
    ctx.shadowColor = color
    ctx.shadowBlur = 6
    ctx.beginPath()
    ctx.arc(px, py, r * 0.5, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.globalAlpha = 0.3
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
  }

  private drawPickup(pickup: Pickup): void {
    const ctx = this.ctx
    const bob = Math.sin(this.time * 3 + pickup.bobPhase) * 3
    const [px, py] = this.toScreen(pickup.x, pickup.y)
    const r = pickup.radius * this.scale

    // Pickup sprite with bob + pulse
    const pulse = 0.7 + 0.3 * Math.sin(this.time * 4 + pickup.bobPhase)
    const spriteName = `pickup_${pickup.type}`
    const spriteSize = r * 3
    ctx.globalAlpha = pulse
    this.drawSprite(spriteName, px, py + bob, spriteSize, PICKUP_COLORS[pickup.type])
    ctx.globalAlpha = 1

    // Blink when about to expire
    if (pickup.lifetime < 3 && Math.sin(this.time * 10) > 0) {
      ctx.globalAlpha = 0.3
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }
}
