import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { FrameLoop } from '@engine/renderer/frame'

const W = 700, H = 600
const COLS = 8, ROWS = 4, ALIEN_W = 36, ALIEN_H = 24, GAP = 12
const PLAYER_W = 44, PLAYER_H = 14, PLAYER_SPEED = 280
const BULLET_W = 3, BULLET_H = 10, BULLET_SPEED = 400
const ALIEN_SPEED_BASE = 50, ALIEN_DROP = 18
const ALIEN_SHOOT_CHANCE = 0.003

interface Alien { x: number; y: number; alive: boolean; row: number }
interface Bullet { x: number; y: number; active: boolean; isAlien: boolean }

let playerX = W / 2 - PLAYER_W / 2
let aliens: Alien[] = []
let bullets: Bullet[] = []
let alienDir = 1, alienSpeed = ALIEN_SPEED_BASE
let gameOver = false, won = false

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem(2)
const health = new HealthSystem(3)

health.onDeath = () => { gameOver = true }

function spawnAliens() {
  aliens = []
  const startX = (W - (COLS * (ALIEN_W + GAP) - GAP)) / 2
  const colors = ['#ff4455', '#ff8844', '#ffcc33', '#44ccff']
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS; c++)
      aliens.push({ x: startX + c * (ALIEN_W + GAP), y: 50 + r * (ALIEN_H + GAP), alive: true, row: r })
}

function restart() {
  playerX = W / 2 - PLAYER_W / 2
  bullets = []; alienDir = 1; alienSpeed = ALIEN_SPEED_BASE
  gameOver = false; won = false
  score.reset(); health.heal(health.max)
  spawnAliens()
}

spawnAliens()

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!
const COLORS = ['#ff4455', '#ff8844', '#ffcc33', '#44ccff']

function draw() {
  ctx.fillStyle = '#0a0a1a'
  ctx.fillRect(0, 0, W, H)

  // Aliens
  for (const a of aliens) {
    if (!a.alive) continue
    ctx.fillStyle = COLORS[a.row]
    ctx.fillRect(a.x, a.y, ALIEN_W, ALIEN_H)
  }

  // Player
  ctx.fillStyle = '#4ade80'
  ctx.fillRect(playerX, H - 50, PLAYER_W, PLAYER_H)

  // Bullets
  for (const b of bullets) {
    if (!b.active) continue
    ctx.fillStyle = b.isAlien ? '#ef4444' : '#fbbf24'
    ctx.fillRect(b.x, b.y, BULLET_W, BULLET_H)
  }

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'
  ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}`, 10, 24)
  ctx.fillStyle = '#ef4444'
  ctx.fillText(`Lives: ${health.current}`, W - 100, 24)

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'
    ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = won ? '#4ade80' : '#ef4444'
    ctx.fillText(won ? 'VICTORY' : 'GAME OVER', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.fillText(`Score: ${score.score}  |  SPACE to restart`, W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

let shootCooldown = 0
const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (gameOver && keyboard.justPressed('Space')) { restart(); return }
  if (gameOver) { keyboard.update(); draw(); return }

  // Player
  if (keyboard.isDown('ArrowLeft') || keyboard.isDown('KeyA')) playerX = Math.max(0, playerX - PLAYER_SPEED * dt)
  if (keyboard.isDown('ArrowRight') || keyboard.isDown('KeyD')) playerX = Math.min(W - PLAYER_W, playerX + PLAYER_SPEED * dt)

  // Player shoot
  shootCooldown -= dt
  if ((keyboard.justPressed('Space') || keyboard.justPressed('ArrowUp')) && shootCooldown <= 0) {
    shootCooldown = 0.3
    bullets.push({ x: playerX + PLAYER_W / 2, y: H - 55, active: true, isAlien: false })
  }

  // Move aliens
  let shouldDrop = false
  for (const a of aliens) {
    if (!a.alive) continue
    a.x += alienDir * alienSpeed * dt
    if (a.x <= 0 || a.x + ALIEN_W >= W) shouldDrop = true
  }
  if (shouldDrop) {
    alienDir *= -1
    for (const a of aliens) if (a.alive) a.y += ALIEN_DROP
    alienSpeed += 4
  }

  // Alien shoot
  const aliveAliens = aliens.filter(a => a.alive)
  if (Math.random() < ALIEN_SHOOT_CHANCE * aliveAliens.length) {
    const shooter = aliveAliens[Math.floor(Math.random() * aliveAliens.length)]
    bullets.push({ x: shooter.x + ALIEN_W / 2, y: shooter.y + ALIEN_H, active: true, isAlien: true })
  }

  // Update bullets
  for (const b of bullets) {
    if (!b.active) continue
    b.y += (b.isAlien ? BULLET_SPEED * 0.6 : -BULLET_SPEED) * dt
    if (b.y < -10 || b.y > H + 10) b.active = false
  }

  // Player bullets → aliens
  for (const b of bullets) {
    if (!b.active || b.isAlien) continue
    for (const a of aliens) {
      if (!a.alive) continue
      if (b.x >= a.x && b.x <= a.x + ALIEN_W && b.y >= a.y && b.y <= a.y + ALIEN_H) {
        b.active = false; a.alive = false
        score.addKill()
        break
      }
    }
  }

  // Alien bullets → player
  for (const b of bullets) {
    if (!b.active || !b.isAlien) continue
    if (b.x >= playerX && b.x <= playerX + PLAYER_W && b.y >= H - 50 && b.y <= H - 50 + PLAYER_H) {
      b.active = false
      health.damage(1)
    }
  }

  // Aliens reach bottom
  for (const a of aliens) {
    if (a.alive && a.y + ALIEN_H >= H - 60) { gameOver = true; break }
  }

  // Win
  if (aliveAliens.length === 0 && !gameOver) { won = true; gameOver = true }

  bullets = bullets.filter(b => b.active)
  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
