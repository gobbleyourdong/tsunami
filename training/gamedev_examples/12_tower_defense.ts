import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { FrameLoop } from '@engine/renderer/frame'

const W = 800, H = 500
const CELL = 40, COLS = W / CELL, ROWS = H / CELL
const TOWER_COST = 50, TOWER_RANGE = 120, TOWER_DAMAGE = 25, TOWER_RATE = 1.0
const ENEMY_SPEED = 60, ENEMY_HP_BASE = 100
const BULLET_SPEED = 400

// Path (grid coords)
const PATH: [number, number][] = [
  [0,3],[1,3],[2,3],[3,3],[4,3],[5,3],[5,4],[5,5],[5,6],[5,7],[5,8],
  [6,8],[7,8],[8,8],[9,8],[10,8],[10,7],[10,6],[10,5],[10,4],[10,3],
  [11,3],[12,3],[13,3],[14,3],[15,3],[16,3],[17,3],[18,3],[19,3]
]

interface Tower { x: number; y: number; cooldown: number }
interface Enemy { pathIdx: number; progress: number; hp: number; maxHp: number; speed: number }
interface Bullet { x: number; y: number; tx: number; ty: number; speed: number }

let towers: Tower[] = []
let enemies: Enemy[] = []
let bullets: Bullet[] = []
let gold = 200, wave = 0, spawnTimer = 0, enemiesLeft = 0
let placing = false, mouseX = 0, mouseY = 0

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()
const health = new HealthSystem(20)
let gameOver = false
health.onDeath = () => { gameOver = true }

function pathPos(idx: number, progress: number): [number, number] {
  if (idx >= PATH.length - 1) return [PATH[PATH.length-1][0] * CELL + CELL/2, PATH[PATH.length-1][1] * CELL + CELL/2]
  const [ax, ay] = PATH[idx], [bx, by] = PATH[idx + 1]
  return [(ax + (bx - ax) * progress) * CELL + CELL/2, (ay + (by - ay) * progress) * CELL + CELL/2]
}

function isOnPath(cx: number, cy: number): boolean {
  return PATH.some(([px, py]) => px === cx && py === cy)
}

function spawnWave() {
  wave++; enemiesLeft = 5 + wave * 2; spawnTimer = 0
}

function restart() {
  towers = []; enemies = []; bullets = []
  gold = 200; wave = 0; gameOver = false
  score.reset(); health.heal(health.max)
  spawnWave()
}

spawnWave()

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px`, cursor: 'crosshair' })
const ctx = canvas.getContext('2d')!

canvas.addEventListener('mousemove', e => { const r = canvas.getBoundingClientRect(); mouseX = e.clientX - r.left; mouseY = e.clientY - r.top })
canvas.addEventListener('click', () => {
  if (gameOver) { restart(); return }
  const cx = Math.floor(mouseX / CELL), cy = Math.floor(mouseY / CELL)
  if (isOnPath(cx, cy) || gold < TOWER_COST) return
  if (towers.some(t => t.x === cx && t.y === cy)) return
  towers.push({ x: cx, y: cy, cooldown: 0 })
  gold -= TOWER_COST
})

function draw() {
  ctx.fillStyle = '#1a2332'; ctx.fillRect(0, 0, W, H)

  // Path
  for (const [px, py] of PATH) {
    ctx.fillStyle = '#2d3748'; ctx.fillRect(px * CELL, py * CELL, CELL, CELL)
  }

  // Towers
  for (const t of towers) {
    ctx.fillStyle = '#4a9eff'
    ctx.fillRect(t.x * CELL + 5, t.y * CELL + 5, CELL - 10, CELL - 10)
    ctx.strokeStyle = 'rgba(74,158,255,0.15)'; ctx.beginPath()
    ctx.arc(t.x * CELL + CELL/2, t.y * CELL + CELL/2, TOWER_RANGE, 0, Math.PI * 2); ctx.stroke()
  }

  // Enemies
  for (const e of enemies) {
    const [ex, ey] = pathPos(e.pathIdx, e.progress)
    ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(ex, ey, 10, 0, Math.PI * 2); ctx.fill()
    // HP bar
    const hpPct = e.hp / e.maxHp
    ctx.fillStyle = '#333'; ctx.fillRect(ex - 12, ey - 18, 24, 4)
    ctx.fillStyle = hpPct > 0.5 ? '#22c55e' : '#ef4444'; ctx.fillRect(ex - 12, ey - 18, 24 * hpPct, 4)
  }

  // Bullets
  ctx.fillStyle = '#fbbf24'
  for (const b of bullets) { ctx.beginPath(); ctx.arc(b.x, b.y, 3, 0, Math.PI * 2); ctx.fill() }

  // Placing preview
  if (!gameOver) {
    const cx = Math.floor(mouseX / CELL), cy = Math.floor(mouseY / CELL)
    const valid = !isOnPath(cx, cy) && gold >= TOWER_COST && !towers.some(t => t.x === cx && t.y === cy)
    ctx.fillStyle = valid ? 'rgba(74,158,255,0.3)' : 'rgba(239,68,68,0.3)'
    ctx.fillRect(cx * CELL, cy * CELL, CELL, CELL)
  }

  // HUD
  ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Gold: ${gold}  Wave: ${wave}  Lives: ${health.current}  Score: ${score.score}`, 10, 20)

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'; ctx.fillText('BASE DESTROYED', W/2, H/2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText('Click to restart', W/2, H/2 + 20); ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (gameOver) { draw(); return }

  // Spawn enemies
  if (enemiesLeft > 0) {
    spawnTimer += dt
    if (spawnTimer >= 0.8) { spawnTimer = 0; enemiesLeft--
      enemies.push({ pathIdx: 0, progress: 0, hp: ENEMY_HP_BASE + wave * 20, maxHp: ENEMY_HP_BASE + wave * 20, speed: ENEMY_SPEED + wave * 5 })
    }
  }

  // Move enemies
  for (const e of enemies) {
    e.progress += (e.speed / CELL) * dt
    if (e.progress >= 1) { e.progress = 0; e.pathIdx++ }
    if (e.pathIdx >= PATH.length - 1) { health.damage(1); e.hp = 0 }
  }
  enemies = enemies.filter(e => e.hp > 0)

  // Tower shooting
  for (const t of towers) {
    t.cooldown -= dt
    if (t.cooldown > 0) continue
    const tx = t.x * CELL + CELL/2, ty = t.y * CELL + CELL/2
    let target: Enemy | null = null
    for (const e of enemies) {
      const [ex, ey] = pathPos(e.pathIdx, e.progress)
      if (Math.hypot(ex - tx, ey - ty) < TOWER_RANGE) { target = e; break }
    }
    if (target) {
      const [ex, ey] = pathPos(target.pathIdx, target.progress)
      bullets.push({ x: tx, y: ty, tx: ex, ty: ey, speed: BULLET_SPEED })
      t.cooldown = TOWER_RATE
    }
  }

  // Move bullets
  for (const b of bullets) {
    const dx = b.tx - b.x, dy = b.ty - b.y, d = Math.hypot(dx, dy)
    if (d < 5) { b.speed = 0; continue }
    b.x += (dx/d) * b.speed * dt; b.y += (dy/d) * b.speed * dt
  }

  // Bullet hits
  for (let i = bullets.length - 1; i >= 0; i--) {
    const b = bullets[i]
    if (b.speed === 0) { bullets.splice(i, 1); continue }
    for (const e of enemies) {
      const [ex, ey] = pathPos(e.pathIdx, e.progress)
      if (Math.hypot(b.x - ex, b.y - ey) < 15) {
        e.hp -= TOWER_DAMAGE; bullets.splice(i, 1)
        if (e.hp <= 0) { score.addKill(); gold += 15 }
        break
      }
    }
  }

  // Next wave
  if (enemies.length === 0 && enemiesLeft === 0) spawnWave()

  score.update(dt); keyboard.update(); draw()
}

loop.start()
