import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 500, H = 600
const LANES = 4
const LANE_W = W / LANES
const HIT_Y = H - 80, HIT_TOLERANCE = 40
const NOTE_SPEED = 280
const KEYS = ['KeyD', 'KeyF', 'KeyJ', 'KeyK']
const LANE_COLORS = ['#ef4444', '#4a9eff', '#22c55e', '#fbbf24']
const LANE_LABELS = ['D', 'F', 'J', 'K']

interface Note { lane: number; y: number; active: boolean; hit: boolean }

let notes: Note[] = []
let spawnTimer = 0
let bpm = 120
let beatInterval = 60 / bpm
let songTimer = 0
let misses = 0
let streak = 0, maxStreak = 0
let playing = false

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem(3) // combo at 3 hits

// Simple song pattern (lane, beat offset)
const SONG: [number, number][] = []
for (let i = 0; i < 60; i++) {
  SONG.push([Math.floor(Math.random() * LANES), i * beatInterval])
}

function restart() {
  notes = []; spawnTimer = 0; songTimer = 0; misses = 0; streak = 0; maxStreak = 0
  playing = true; score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  ctx.fillStyle = '#0a0a1a'
  ctx.fillRect(0, 0, W, H)

  // Lane dividers
  ctx.strokeStyle = 'rgba(255,255,255,0.05)'
  for (let i = 1; i < LANES; i++) {
    ctx.beginPath(); ctx.moveTo(i * LANE_W, 0); ctx.lineTo(i * LANE_W, H); ctx.stroke()
  }

  // Hit zone
  ctx.fillStyle = 'rgba(255,255,255,0.03)'
  ctx.fillRect(0, HIT_Y - HIT_TOLERANCE, W, HIT_TOLERANCE * 2)
  ctx.strokeStyle = 'rgba(255,255,255,0.2)'
  ctx.beginPath(); ctx.moveTo(0, HIT_Y); ctx.lineTo(W, HIT_Y); ctx.stroke()

  // Notes
  for (const n of notes) {
    if (!n.active) continue
    const x = n.lane * LANE_W + LANE_W / 2
    ctx.fillStyle = n.hit ? '#fff' : LANE_COLORS[n.lane]
    ctx.beginPath()
    ctx.roundRect(x - 22, n.y - 12, 44, 24, 6)
    ctx.fill()
  }

  // Lane labels at bottom
  for (let i = 0; i < LANES; i++) {
    const x = i * LANE_W + LANE_W / 2
    ctx.font = '20px JetBrains Mono, monospace'
    ctx.textAlign = 'center'
    ctx.fillStyle = keyboard.isDown(KEYS[i]) ? LANE_COLORS[i] : '#475569'
    ctx.fillText(LANE_LABELS[i], x, H - 20)
  }
  ctx.textAlign = 'left'

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'
  ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}`, 10, 30)
  ctx.fillStyle = '#ef4444'
  ctx.fillText(`Miss: ${misses}`, 10, 52)
  if (streak > 2) {
    ctx.fillStyle = '#fbbf24'
    ctx.fillText(`Streak: ${streak}`, W - 120, 30)
  }

  if (!playing) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'
    ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#4a9eff'; ctx.fillText('RHYTHM', W / 2, H / 2 - 30)
    ctx.font = '16px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'; ctx.fillText('D F J K — hit notes on the line', W / 2, H / 2 + 5)
    ctx.fillText('SPACE to start', W / 2, H / 2 + 35)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (!playing) {
    if (keyboard.justPressed('Space')) restart()
    keyboard.update(); draw(); return
  }

  // Spawn notes from song
  songTimer += dt
  while (SONG.length > 0 && SONG[0][1] <= songTimer) {
    const [lane] = SONG.shift()!
    notes.push({ lane, y: -20, active: true, hit: false })
  }

  // Move notes
  for (const n of notes) {
    if (!n.active) continue
    n.y += NOTE_SPEED * dt

    // Missed
    if (n.y > HIT_Y + HIT_TOLERANCE * 2 && !n.hit) {
      n.active = false; misses++; streak = 0
    }
  }

  // Input — check hits
  for (let i = 0; i < LANES; i++) {
    if (keyboard.justPressed(KEYS[i])) {
      let bestNote: Note | null = null
      let bestDist = Infinity
      for (const n of notes) {
        if (!n.active || n.hit || n.lane !== i) continue
        const d = Math.abs(n.y - HIT_Y)
        if (d < HIT_TOLERANCE && d < bestDist) { bestNote = n; bestDist = d }
      }
      if (bestNote) {
        bestNote.hit = true; bestNote.active = false
        streak++; maxStreak = Math.max(maxStreak, streak)
        score.addKill()
      }
    }
  }

  // Song end
  if (SONG.length === 0 && notes.every(n => !n.active)) {
    playing = false
  }

  notes = notes.filter(n => n.active || n.hit)
  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
