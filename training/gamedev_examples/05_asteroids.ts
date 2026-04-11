import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 800, H = 600
const TURN_SPEED = 4, THRUST = 300, FRICTION = 0.98, BULLET_SPEED = 500, BULLET_LIFE = 1.5

interface Entity { x: number; y: number; dx: number; dy: number; r: number; angle?: number }
interface Bullet extends Entity { life: number }

let ship: Entity = { x: W / 2, y: H / 2, dx: 0, dy: 0, r: 12, angle: -Math.PI / 2 }
let asteroids: Entity[] = []
let bullets: Bullet[] = []
let alive = true
let level = 1

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem(2)

function spawnAsteroids(count: number) {
  for (let i = 0; i < count; i++) {
    const edge = Math.random() * 4 | 0
    const x = edge < 2 ? Math.random() * W : edge === 2 ? 0 : W
    const y = edge >= 2 ? Math.random() * H : edge === 0 ? 0 : H
    const angle = Math.atan2(H / 2 - y, W / 2 - x) + (Math.random() - 0.5)
    const speed = 40 + Math.random() * 60
    asteroids.push({ x, y, dx: Math.cos(angle) * speed, dy: Math.sin(angle) * speed, r: 30 + Math.random() * 15 })
  }
}

function wrap(e: Entity) {
  if (e.x < -e.r) e.x = W + e.r
  if (e.x > W + e.r) e.x = -e.r
  if (e.y < -e.r) e.y = H + e.r
  if (e.y > H + e.r) e.y = -e.r
}

function dist(a: Entity, b: Entity) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function restart() {
  ship = { x: W / 2, y: H / 2, dx: 0, dy: 0, r: 12, angle: -Math.PI / 2 }
  asteroids = []; bullets = []
  alive = true; level = 1
  score.reset()
  spawnAsteroids(4)
}

spawnAsteroids(4)

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  ctx.fillStyle = '#0a0a1a'
  ctx.fillRect(0, 0, W, H)

  // Ship
  if (alive) {
    ctx.save()
    ctx.translate(ship.x, ship.y)
    ctx.rotate(ship.angle!)
    ctx.strokeStyle = '#4a9eff'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(14, 0)
    ctx.lineTo(-10, -8)
    ctx.lineTo(-6, 0)
    ctx.lineTo(-10, 8)
    ctx.closePath()
    ctx.stroke()
    ctx.restore()
  }

  // Asteroids
  ctx.strokeStyle = '#94a3b8'
  ctx.lineWidth = 1.5
  for (const a of asteroids) {
    ctx.beginPath()
    ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2)
    ctx.stroke()
  }

  // Bullets
  ctx.fillStyle = '#fbbf24'
  for (const b of bullets) {
    ctx.beginPath()
    ctx.arc(b.x, b.y, 2, 0, Math.PI * 2)
    ctx.fill()
  }

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'
  ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}  Level: ${level}`, 10, 24)

  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
    ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'
    ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'
    ctx.fillText('DESTROYED', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.fillText('SPACE to restart', W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

let shootCooldown = 0
const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (!alive && keyboard.justPressed('Space')) { restart(); return }
  if (!alive) { keyboard.update(); draw(); return }

  // Rotation
  if (keyboard.isDown('ArrowLeft') || keyboard.isDown('KeyA')) ship.angle! -= TURN_SPEED * dt
  if (keyboard.isDown('ArrowRight') || keyboard.isDown('KeyD')) ship.angle! += TURN_SPEED * dt

  // Thrust
  if (keyboard.isDown('ArrowUp') || keyboard.isDown('KeyW')) {
    ship.dx += Math.cos(ship.angle!) * THRUST * dt
    ship.dy += Math.sin(ship.angle!) * THRUST * dt
  }

  // Friction
  ship.dx *= FRICTION; ship.dy *= FRICTION
  ship.x += ship.dx * dt; ship.y += ship.dy * dt
  wrap(ship)

  // Shoot
  shootCooldown -= dt
  if (keyboard.justPressed('Space') && shootCooldown <= 0) {
    shootCooldown = 0.2
    bullets.push({
      x: ship.x + Math.cos(ship.angle!) * 16,
      y: ship.y + Math.sin(ship.angle!) * 16,
      dx: Math.cos(ship.angle!) * BULLET_SPEED + ship.dx,
      dy: Math.sin(ship.angle!) * BULLET_SPEED + ship.dy,
      r: 2, life: BULLET_LIFE,
    })
  }

  // Update bullets
  for (const b of bullets) { b.x += b.dx * dt; b.y += b.dy * dt; b.life -= dt; wrap(b) }
  bullets = bullets.filter(b => b.life > 0)

  // Update asteroids
  for (const a of asteroids) { a.x += a.dx * dt; a.y += a.dy * dt; wrap(a) }

  // Bullet-asteroid collision
  for (let i = bullets.length - 1; i >= 0; i--) {
    for (let j = asteroids.length - 1; j >= 0; j--) {
      if (dist(bullets[i], asteroids[j]) < asteroids[j].r) {
        const a = asteroids[j]
        bullets.splice(i, 1)
        asteroids.splice(j, 1)
        score.addKill()
        // Split
        if (a.r > 15) {
          for (let k = 0; k < 2; k++) {
            const angle = Math.random() * Math.PI * 2
            const speed = 50 + Math.random() * 80
            asteroids.push({ x: a.x, y: a.y, dx: Math.cos(angle) * speed, dy: Math.sin(angle) * speed, r: a.r * 0.6 })
          }
        }
        break
      }
    }
  }

  // Ship-asteroid collision
  for (const a of asteroids) {
    if (dist(ship, a) < ship.r + a.r) { alive = false; break }
  }

  // Next level
  if (asteroids.length === 0) { level++; spawnAsteroids(3 + level) }

  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
