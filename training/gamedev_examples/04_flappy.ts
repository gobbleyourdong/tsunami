import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 400, H = 600
const BIRD_R = 15, GRAVITY = 900, JUMP_VEL = -320
const PIPE_W = 50, PIPE_GAP = 150, PIPE_SPEED = 160, PIPE_INTERVAL = 1.8

interface Pipe { x: number; gapY: number; scored: boolean }

let birdY = H / 2, birdVel = 0
let pipes: Pipe[] = []
let pipeTimer = 0
let alive = true
let started = false

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()

function spawnPipe() {
  const gapY = 100 + Math.random() * (H - 200 - PIPE_GAP)
  pipes.push({ x: W + PIPE_W, gapY, scored: false })
}

function restart() {
  birdY = H / 2
  birdVel = 0
  pipes = []
  pipeTimer = 0
  alive = true
  started = false
  score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  // Sky gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H)
  grad.addColorStop(0, '#1a1a2e')
  grad.addColorStop(1, '#16213e')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H)

  // Pipes
  for (const p of pipes) {
    ctx.fillStyle = '#22c55e'
    ctx.fillRect(p.x, 0, PIPE_W, p.gapY) // top pipe
    ctx.fillRect(p.x, p.gapY + PIPE_GAP, PIPE_W, H - p.gapY - PIPE_GAP) // bottom pipe
    ctx.fillStyle = '#16a34a'
    ctx.fillRect(p.x - 3, p.gapY - 20, PIPE_W + 6, 20) // top cap
    ctx.fillRect(p.x - 3, p.gapY + PIPE_GAP, PIPE_W + 6, 20) // bottom cap
  }

  // Bird
  ctx.fillStyle = '#fbbf24'
  ctx.beginPath()
  ctx.arc(80, birdY, BIRD_R, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#f59e0b'
  ctx.beginPath()
  ctx.arc(80 + 5, birdY - 3, 5, 0, Math.PI * 2)
  ctx.fill()

  // Score
  ctx.font = '24px JetBrains Mono, monospace'
  ctx.textAlign = 'center'
  ctx.fillStyle = '#fff'
  ctx.fillText(String(score.score), W / 2, 40)
  ctx.textAlign = 'left'

  if (!started) {
    ctx.font = '16px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.textAlign = 'center'
    ctx.fillText('SPACE to start', W / 2, H / 2 + 60)
    ctx.textAlign = 'left'
  }

  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)'
    ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'
    ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'
    ctx.fillText('GAME OVER', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.fillText(`Score: ${score.score}  |  SPACE to restart`, W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (!alive && keyboard.justPressed('Space')) { restart(); return }
  if (!started && keyboard.justPressed('Space')) { started = true; birdVel = JUMP_VEL }

  if (!started || !alive) { keyboard.update(); draw(); return }

  // Flap
  if (keyboard.justPressed('Space') || keyboard.justPressed('ArrowUp')) birdVel = JUMP_VEL

  // Physics
  birdVel += GRAVITY * dt
  birdY += birdVel * dt

  // Floor/ceiling death
  if (birdY - BIRD_R < 0 || birdY + BIRD_R > H) alive = false

  // Spawn pipes
  pipeTimer += dt
  if (pipeTimer >= PIPE_INTERVAL) { pipeTimer = 0; spawnPipe() }

  // Update pipes
  for (const p of pipes) {
    p.x -= PIPE_SPEED * dt

    // Score
    if (!p.scored && p.x + PIPE_W < 80) { score.addKill(); p.scored = true }

    // Collision
    if (80 + BIRD_R > p.x && 80 - BIRD_R < p.x + PIPE_W) {
      if (birdY - BIRD_R < p.gapY || birdY + BIRD_R > p.gapY + PIPE_GAP) alive = false
    }
  }

  // Remove offscreen pipes
  pipes = pipes.filter(p => p.x + PIPE_W > 0)

  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
