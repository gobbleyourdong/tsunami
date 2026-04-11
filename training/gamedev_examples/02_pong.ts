import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 800, H = 500
const PADDLE_W = 12, PADDLE_H = 80, BALL_R = 8
const PADDLE_SPEED = 350, BALL_SPEED = 320
const AI_SPEED = 280

let playerY = H / 2 - PADDLE_H / 2
let aiY = H / 2 - PADDLE_H / 2
let ballX = W / 2, ballY = H / 2
let ballDX = BALL_SPEED, ballDY = BALL_SPEED * 0.5
let playerScore = 0, aiScore = 0
let serving = true

const keyboard = new KeyboardInput()
keyboard.bind()

function resetBall(dir: number) {
  ballX = W / 2
  ballY = H / 2
  const angle = (Math.random() - 0.5) * 1.2
  ballDX = dir * BALL_SPEED * Math.cos(angle)
  ballDY = BALL_SPEED * Math.sin(angle)
  serving = true
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  ctx.fillStyle = '#0a0a1a'
  ctx.fillRect(0, 0, W, H)

  // Center line
  ctx.setLineDash([8, 8])
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'
  ctx.beginPath()
  ctx.moveTo(W / 2, 0)
  ctx.lineTo(W / 2, H)
  ctx.stroke()
  ctx.setLineDash([])

  // Paddles
  ctx.fillStyle = '#4a9eff'
  ctx.fillRect(20, playerY, PADDLE_W, PADDLE_H)
  ctx.fillStyle = '#ef4444'
  ctx.fillRect(W - 20 - PADDLE_W, aiY, PADDLE_W, PADDLE_H)

  // Ball
  ctx.beginPath()
  ctx.arc(ballX, ballY, BALL_R, 0, Math.PI * 2)
  ctx.fillStyle = '#fff'
  ctx.fill()

  // Score
  ctx.font = '36px JetBrains Mono, monospace'
  ctx.textAlign = 'center'
  ctx.fillStyle = '#4a9eff'
  ctx.fillText(String(playerScore), W / 2 - 60, 50)
  ctx.fillStyle = '#ef4444'
  ctx.fillText(String(aiScore), W / 2 + 60, 50)
  ctx.textAlign = 'left'

  if (serving) {
    ctx.font = '14px JetBrains Mono, monospace'
    ctx.fillStyle = '#94a3b8'
    ctx.textAlign = 'center'
    ctx.fillText('SPACE to serve', W / 2, H - 30)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt

  if (serving && keyboard.justPressed('Space')) serving = false

  // Player paddle
  if (keyboard.isDown('ArrowUp') || keyboard.isDown('KeyW'))
    playerY = Math.max(0, playerY - PADDLE_SPEED * dt)
  if (keyboard.isDown('ArrowDown') || keyboard.isDown('KeyS'))
    playerY = Math.min(H - PADDLE_H, playerY + PADDLE_SPEED * dt)

  if (!serving) {
    // Ball movement
    ballX += ballDX * dt
    ballY += ballDY * dt

    // Top/bottom bounce
    if (ballY - BALL_R <= 0 || ballY + BALL_R >= H) ballDY = -ballDY

    // Player paddle collision
    if (ballX - BALL_R <= 32 && ballY >= playerY && ballY <= playerY + PADDLE_H && ballDX < 0) {
      ballDX = -ballDX * 1.05
      const offset = (ballY - playerY - PADDLE_H / 2) / (PADDLE_H / 2)
      ballDY = offset * BALL_SPEED
    }

    // AI paddle collision
    if (ballX + BALL_R >= W - 32 && ballY >= aiY && ballY <= aiY + PADDLE_H && ballDX > 0) {
      ballDX = -ballDX * 1.05
      const offset = (ballY - aiY - PADDLE_H / 2) / (PADDLE_H / 2)
      ballDY = offset * BALL_SPEED
    }

    // Scoring
    if (ballX < 0) { aiScore++; resetBall(1) }
    if (ballX > W) { playerScore++; resetBall(-1) }

    // AI movement
    const aiCenter = aiY + PADDLE_H / 2
    const diff = ballY - aiCenter
    if (Math.abs(diff) > 10) {
      aiY += Math.sign(diff) * Math.min(AI_SPEED * dt, Math.abs(diff))
      aiY = Math.max(0, Math.min(H - PADDLE_H, aiY))
    }
  }

  keyboard.update()
  draw()
}

loop.start()
