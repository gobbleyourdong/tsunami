import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 600, H = 500
const COLS = 3, ROWS = 3, HOLE_R = 35, GAP_X = 160, GAP_Y = 120
const GAME_TIME = 30 // seconds
const MOLE_UP_MIN = 0.6, MOLE_UP_MAX = 1.5, SPAWN_MIN = 0.3, SPAWN_MAX = 1.0

interface Mole { col: number; row: number; timer: number; active: boolean; hit: boolean }

let moles: Mole[] = []
let spawnTimer = 0.5
let timeLeft = GAME_TIME
let playing = false, finished = false

const score = new ScoreSystem(2)

function spawnMole() {
  const col = Math.floor(Math.random() * COLS)
  const row = Math.floor(Math.random() * ROWS)
  if (moles.some(m => m.col === col && m.row === row && m.active)) return
  const duration = MOLE_UP_MIN + Math.random() * (MOLE_UP_MAX - MOLE_UP_MIN)
  moles.push({ col, row, timer: duration, active: true, hit: false })
}

function holePos(col: number, row: number) {
  return { x: 90 + col * GAP_X, y: 120 + row * GAP_Y }
}

function restart() {
  moles = []; spawnTimer = 0.5; timeLeft = GAME_TIME
  playing = true; finished = false; score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px`, cursor: 'pointer' })
const ctx = canvas.getContext('2d')!

canvas.addEventListener('click', (e) => {
  if (!playing && !finished) { restart(); return }
  if (finished) { restart(); return }
  const r = canvas.getBoundingClientRect()
  const mx = e.clientX - r.left, my = e.clientY - r.top
  for (const m of moles) {
    if (!m.active || m.hit) continue
    const p = holePos(m.col, m.row)
    if (Math.hypot(mx - p.x, my - p.y) < HOLE_R + 10) {
      m.hit = true; m.timer = 0.3
      score.addKill()
    }
  }
})

function draw() {
  ctx.fillStyle = '#2d5a27'
  ctx.fillRect(0, 0, W, H)

  // Holes and moles
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const p = holePos(c, r)
      // Hole shadow
      ctx.fillStyle = '#1a3a15'
      ctx.beginPath(); ctx.ellipse(p.x, p.y + 10, HOLE_R + 5, 18, 0, 0, Math.PI * 2); ctx.fill()
      // Hole
      ctx.fillStyle = '#0f2a0a'
      ctx.beginPath(); ctx.ellipse(p.x, p.y, HOLE_R, 15, 0, 0, Math.PI * 2); ctx.fill()
    }
  }

  // Active moles
  for (const m of moles) {
    if (!m.active) continue
    const p = holePos(m.col, m.row)
    if (m.hit) {
      ctx.fillStyle = '#fbbf24'
      ctx.font = '20px JetBrains Mono'; ctx.textAlign = 'center'
      ctx.fillText('POW!', p.x, p.y - 20); ctx.textAlign = 'left'
    } else {
      // Mole body
      ctx.fillStyle = '#8B4513'
      ctx.beginPath(); ctx.arc(p.x, p.y - 15, 22, 0, Math.PI * 2); ctx.fill()
      // Eyes
      ctx.fillStyle = '#fff'
      ctx.beginPath(); ctx.arc(p.x - 7, p.y - 20, 4, 0, Math.PI * 2); ctx.fill()
      ctx.beginPath(); ctx.arc(p.x + 7, p.y - 20, 4, 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = '#000'
      ctx.beginPath(); ctx.arc(p.x - 7, p.y - 20, 2, 0, Math.PI * 2); ctx.fill()
      ctx.beginPath(); ctx.arc(p.x + 7, p.y - 20, 2, 0, Math.PI * 2); ctx.fill()
      // Nose
      ctx.fillStyle = '#d4956a'
      ctx.beginPath(); ctx.arc(p.x, p.y - 12, 5, 0, Math.PI * 2); ctx.fill()
    }
  }

  // HUD
  ctx.font = '18px JetBrains Mono, monospace'; ctx.fillStyle = '#fff'
  ctx.fillText(`Score: ${score.score}`, 20, 35)
  if (score.combo > 1) { ctx.fillStyle = '#fbbf24'; ctx.fillText(`x${score.combo}`, 20, 58) }
  ctx.fillStyle = timeLeft < 10 ? '#ef4444' : '#fff'
  ctx.textAlign = 'right'; ctx.fillText(`${Math.ceil(timeLeft)}s`, W - 20, 35); ctx.textAlign = 'left'

  if (!playing && !finished) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#fbbf24'; ctx.fillText('WHACK-A-MOLE', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText('Click to start', W / 2, H / 2 + 20); ctx.textAlign = 'left'
  }

  if (finished) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#4ade80'; ctx.fillText("TIME'S UP!", W / 2, H / 2 - 10)
    ctx.font = '18px JetBrains Mono, monospace'; ctx.fillStyle = '#fff'
    ctx.fillText(`Final Score: ${score.score}`, W / 2, H / 2 + 20)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText('Click to play again', W / 2, H / 2 + 50); ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (!playing) { draw(); return }

  timeLeft -= dt
  if (timeLeft <= 0) { playing = false; finished = true; draw(); return }

  // Spawn
  spawnTimer -= dt
  if (spawnTimer <= 0) { spawnMole(); spawnTimer = SPAWN_MIN + Math.random() * (SPAWN_MAX - SPAWN_MIN) }

  // Update moles
  for (const m of moles) {
    if (!m.active) continue
    m.timer -= dt
    if (m.timer <= 0) m.active = false
  }
  moles = moles.filter(m => m.active)

  score.update(dt)
  draw()
}

loop.start()
