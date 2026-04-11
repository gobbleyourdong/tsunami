import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { FrameLoop } from '@engine/renderer/frame'

const W = 800, H = 500
const CITIES = [150, 250, 350, 450, 550, 650]
const INTERCEPTOR_SPEED = 350, MISSILE_SPEED_BASE = 60
const WAVE_INTERVAL = 8

interface Missile { x: number; y: number; tx: number; ty: number; speed: number; alive: boolean }
interface Interceptor { x: number; y: number; tx: number; ty: number; alive: boolean }
interface Explosion { x: number; y: number; r: number; maxR: number; growing: boolean }

let missiles: Missile[] = []
let interceptors: Interceptor[] = []
let explosions: Explosion[] = []
let citiesAlive = CITIES.map(() => true)
let wave = 0, waveTimer = 0, mouseX = W / 2, mouseY = H / 2

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem(2)
const health = new HealthSystem(6)
health.onDeath = () => { gameOver = true }
let gameOver = false

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px`, cursor: 'crosshair' })
const ctx = canvas.getContext('2d')!

canvas.addEventListener('mousemove', e => { const r = canvas.getBoundingClientRect(); mouseX = e.clientX - r.left; mouseY = e.clientY - r.top })
canvas.addEventListener('click', () => {
  if (gameOver) return
  interceptors.push({ x: W / 2, y: H - 20, tx: mouseX, ty: mouseY, alive: true })
})

function spawnWave() {
  wave++
  const count = 3 + wave * 2
  const speed = MISSILE_SPEED_BASE + wave * 10
  for (let i = 0; i < count; i++) {
    const tx = CITIES[Math.floor(Math.random() * CITIES.length)]
    missiles.push({ x: Math.random() * W, y: -20, tx, ty: H - 40, speed: speed + Math.random() * 30, alive: true })
  }
}

function restart() {
  missiles = []; interceptors = []; explosions = []
  citiesAlive = CITIES.map(() => true)
  wave = 0; waveTimer = 0; gameOver = false
  score.reset(); health.heal(health.max)
  spawnWave()
}

spawnWave()

function draw() {
  const grad = ctx.createLinearGradient(0, 0, 0, H)
  grad.addColorStop(0, '#0a0a2e'); grad.addColorStop(1, '#1a1a3e')
  ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H)

  // Ground
  ctx.fillStyle = '#2d3748'; ctx.fillRect(0, H - 30, W, 30)

  // Cities
  for (let i = 0; i < CITIES.length; i++) {
    ctx.fillStyle = citiesAlive[i] ? '#4a9eff' : '#1e293b'
    ctx.fillRect(CITIES[i] - 15, H - 50, 30, 20)
    ctx.fillRect(CITIES[i] - 8, H - 60, 16, 10)
  }

  // Launcher
  ctx.fillStyle = '#22c55e'; ctx.fillRect(W / 2 - 10, H - 40, 20, 12)

  // Missiles (enemy)
  for (const m of missiles) {
    if (!m.alive) continue
    ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2
    ctx.beginPath(); ctx.moveTo(m.x, m.y - 15); ctx.lineTo(m.x, m.y); ctx.stroke()
    ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(m.x, m.y, 3, 0, Math.PI * 2); ctx.fill()
  }

  // Interceptors
  for (const ic of interceptors) {
    if (!ic.alive) continue
    ctx.strokeStyle = '#4ade80'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(W / 2, H - 30); ctx.lineTo(ic.x, ic.y); ctx.stroke()
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(ic.x, ic.y, 2, 0, Math.PI * 2); ctx.fill()
  }

  // Explosions
  for (const e of explosions) {
    ctx.fillStyle = `rgba(255, 200, 50, ${0.6 * (1 - e.r / e.maxR)})`
    ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2); ctx.fill()
  }

  // Crosshair
  ctx.strokeStyle = '#4ade80'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.arc(mouseX, mouseY, 8, 0, Math.PI * 2); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(mouseX - 12, mouseY); ctx.lineTo(mouseX + 12, mouseY); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(mouseX, mouseY - 12); ctx.lineTo(mouseX, mouseY + 12); ctx.stroke()

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}  Wave: ${wave}`, 10, 24)

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'; ctx.fillText('ALL CITIES DESTROYED', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText(`Score: ${score.score}  |  Click to restart`, W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

canvas.addEventListener('click', () => { if (gameOver) restart() })

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (gameOver) { draw(); return }

  // Move missiles
  for (const m of missiles) {
    if (!m.alive) continue
    const dx = m.tx - m.x, dy = m.ty - m.y
    const d = Math.hypot(dx, dy)
    if (d < 5) { m.alive = false; const ci = CITIES.indexOf(m.tx); if (ci >= 0 && citiesAlive[ci]) { citiesAlive[ci] = false; health.damage(1) }; continue }
    m.x += (dx / d) * m.speed * dt; m.y += (dy / d) * m.speed * dt
  }

  // Move interceptors
  for (const ic of interceptors) {
    if (!ic.alive) continue
    const dx = ic.tx - ic.x, dy = ic.ty - ic.y, d = Math.hypot(dx, dy)
    if (d < 5) { ic.alive = false; explosions.push({ x: ic.tx, y: ic.ty, r: 0, maxR: 40, growing: true }); continue }
    ic.x += (dx / d) * INTERCEPTOR_SPEED * dt; ic.y += (dy / d) * INTERCEPTOR_SPEED * dt
  }

  // Explosions grow/shrink
  for (const e of explosions) {
    if (e.growing) { e.r += 80 * dt; if (e.r >= e.maxR) e.growing = false }
    else { e.r -= 40 * dt }
  }

  // Explosion kills missiles
  for (const e of explosions) {
    for (const m of missiles) {
      if (m.alive && Math.hypot(m.x - e.x, m.y - e.y) < e.r) { m.alive = false; score.addKill() }
    }
  }

  explosions = explosions.filter(e => e.r > 0)
  missiles = missiles.filter(m => m.alive || false) // keep for trail

  // Next wave
  if (missiles.every(m => !m.alive)) { waveTimer += dt; if (waveTimer > 2) { waveTimer = 0; spawnWave() } }

  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
