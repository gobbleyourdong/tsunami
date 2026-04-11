import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { FrameLoop } from '@engine/renderer/frame'

const W = 700, H = 700
const PLAYER_R = 14, PLAYER_SPEED = 200
const BULLET_R = 4, BULLET_SPEED = 450, SHOOT_RATE = 0.15
const ENEMY_R = 12, ENEMY_SPEED_BASE = 80, SPAWN_RATE_BASE = 1.5

interface Bullet { x: number; y: number; dx: number; dy: number }
interface Enemy { x: number; y: number; hp: number; speed: number }

let px = W / 2, py = H / 2
let bullets: Bullet[] = []
let enemies: Enemy[] = []
let mouseX = W / 2, mouseY = 0
let shootTimer = 0, spawnTimer = 0, elapsed = 0

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem(2)
const health = new HealthSystem(5)
let gameOver = false
health.onDeath = () => { gameOver = true }

function spawnEnemy() {
  const edge = Math.random() * 4 | 0
  const x = edge === 0 ? -20 : edge === 1 ? W + 20 : Math.random() * W
  const y = edge === 2 ? -20 : edge === 3 ? H + 20 : Math.random() * H
  const speed = ENEMY_SPEED_BASE + elapsed * 2
  enemies.push({ x, y, hp: 1 + Math.floor(elapsed / 20), speed })
}

function restart() {
  px = W / 2; py = H / 2
  bullets = []; enemies = []; shootTimer = 0; spawnTimer = 0; elapsed = 0
  gameOver = false; score.reset(); health.heal(health.max)
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px`, cursor: 'crosshair' })
const ctx = canvas.getContext('2d')!

canvas.addEventListener('mousemove', e => {
  const r = canvas.getBoundingClientRect(); mouseX = e.clientX - r.left; mouseY = e.clientY - r.top
})

function draw() {
  ctx.fillStyle = '#111318'; ctx.fillRect(0, 0, W, H)

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.02)'
  for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
  for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }

  // Player
  const angle = Math.atan2(mouseY - py, mouseX - px)
  ctx.save(); ctx.translate(px, py); ctx.rotate(angle)
  ctx.fillStyle = '#4a9eff'
  ctx.beginPath(); ctx.moveTo(18, 0); ctx.lineTo(-10, -10); ctx.lineTo(-6, 0); ctx.lineTo(-10, 10); ctx.closePath(); ctx.fill()
  ctx.restore()
  ctx.strokeStyle = 'rgba(74,158,255,0.3)'; ctx.beginPath(); ctx.arc(px, py, PLAYER_R + 2, 0, Math.PI * 2); ctx.stroke()

  // Enemies
  for (const e of enemies) {
    ctx.fillStyle = e.hp > 1 ? '#dc2626' : '#ef4444'
    ctx.beginPath(); ctx.arc(e.x, e.y, ENEMY_R, 0, Math.PI * 2); ctx.fill()
    if (e.hp > 1) {
      ctx.fillStyle = '#333'; ctx.fillRect(e.x - 10, e.y - 20, 20, 3)
      ctx.fillStyle = '#22c55e'; ctx.fillRect(e.x - 10, e.y - 20, 20 * (e.hp / (1 + Math.floor(elapsed / 20))), 3)
    }
  }

  // Bullets
  ctx.fillStyle = '#fbbf24'
  for (const b of bullets) { ctx.beginPath(); ctx.arc(b.x, b.y, BULLET_R, 0, Math.PI * 2); ctx.fill() }

  // Crosshair
  ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.arc(mouseX, mouseY, 10, 0, Math.PI * 2); ctx.stroke()

  // HUD
  ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}  HP: ${health.current}/${health.max}  Time: ${Math.floor(elapsed)}s`, 10, 24)
  if (score.combo > 1) { ctx.fillStyle = '#fbbf24'; ctx.fillText(`x${score.combo}`, 10, 44) }

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'; ctx.fillText('ELIMINATED', W/2, H/2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText(`Score: ${score.score} | ${Math.floor(elapsed)}s survived | SPACE to restart`, W/2, H/2 + 20)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (gameOver) { if (keyboard.justPressed('Space')) restart(); keyboard.update(); draw(); return }

  elapsed += dt

  // Movement
  let dx = 0, dy = 0
  if (keyboard.isDown('KeyA') || keyboard.isDown('ArrowLeft')) dx--
  if (keyboard.isDown('KeyD') || keyboard.isDown('ArrowRight')) dx++
  if (keyboard.isDown('KeyW') || keyboard.isDown('ArrowUp')) dy--
  if (keyboard.isDown('KeyS') || keyboard.isDown('ArrowDown')) dy++
  if (dx || dy) { const len = Math.hypot(dx, dy); px += (dx/len) * PLAYER_SPEED * dt; py += (dy/len) * PLAYER_SPEED * dt }
  px = Math.max(PLAYER_R, Math.min(W - PLAYER_R, px))
  py = Math.max(PLAYER_R, Math.min(H - PLAYER_R, py))

  // Auto-shoot toward mouse
  shootTimer -= dt
  if (shootTimer <= 0) {
    shootTimer = SHOOT_RATE
    const angle = Math.atan2(mouseY - py, mouseX - px)
    bullets.push({ x: px + Math.cos(angle) * 20, y: py + Math.sin(angle) * 20, dx: Math.cos(angle) * BULLET_SPEED, dy: Math.sin(angle) * BULLET_SPEED })
  }

  // Update bullets
  for (const b of bullets) { b.x += b.dx * dt; b.y += b.dy * dt }
  bullets = bullets.filter(b => b.x > -10 && b.x < W + 10 && b.y > -10 && b.y < H + 10)

  // Spawn enemies
  const spawnRate = Math.max(0.3, SPAWN_RATE_BASE - elapsed * 0.02)
  spawnTimer += dt
  if (spawnTimer >= spawnRate) { spawnTimer = 0; spawnEnemy() }

  // Move enemies toward player
  for (const e of enemies) {
    const dx = px - e.x, dy = py - e.y, d = Math.hypot(dx, dy)
    if (d > 1) { e.x += (dx/d) * e.speed * dt; e.y += (dy/d) * e.speed * dt }
  }

  // Bullet-enemy collision
  for (let i = bullets.length - 1; i >= 0; i--) {
    for (let j = enemies.length - 1; j >= 0; j--) {
      if (Math.hypot(bullets[i].x - enemies[j].x, bullets[i].y - enemies[j].y) < ENEMY_R + BULLET_R) {
        enemies[j].hp--
        bullets.splice(i, 1)
        if (enemies[j].hp <= 0) { enemies.splice(j, 1); score.addKill() }
        break
      }
    }
  }

  // Enemy-player collision
  for (let i = enemies.length - 1; i >= 0; i--) {
    if (Math.hypot(enemies[i].x - px, enemies[i].y - py) < PLAYER_R + ENEMY_R) {
      enemies.splice(i, 1); health.damage(1)
    }
  }

  score.update(dt); keyboard.update(); draw()
}

loop.start()
