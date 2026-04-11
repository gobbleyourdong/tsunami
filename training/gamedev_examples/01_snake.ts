import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 600, H = 600, CELL = 20, COLS = W / CELL, ROWS = H / CELL
type Pos = { x: number; y: number }

let snake: Pos[] = [{ x: 10, y: 10 }]
let food: Pos = spawnFood()
let dir: Pos = { x: 1, y: 0 }
let nextDir: Pos = { x: 1, y: 0 }
let moveTimer = 0
let speed = 0.12
let alive = true

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()

function spawnFood(): Pos {
  return { x: Math.floor(Math.random() * COLS), y: Math.floor(Math.random() * ROWS) }
}

function restart() {
  snake = [{ x: 10, y: 10 }]
  food = spawnFood()
  dir = { x: 1, y: 0 }
  nextDir = { x: 1, y: 0 }
  speed = 0.12
  alive = true
  score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  ctx.fillStyle = '#0f1117'
  ctx.fillRect(0, 0, W, H)

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.02)'
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS; c++)
      ctx.strokeRect(c * CELL, r * CELL, CELL, CELL)

  // Snake
  for (let i = 0; i < snake.length; i++) {
    ctx.fillStyle = i === 0 ? '#4ade80' : '#22c55e'
    ctx.fillRect(snake[i].x * CELL + 1, snake[i].y * CELL + 1, CELL - 2, CELL - 2)
  }

  // Food
  ctx.fillStyle = '#ef4444'
  ctx.beginPath()
  ctx.arc(food.x * CELL + CELL / 2, food.y * CELL + CELL / 2, CELL / 2 - 2, 0, Math.PI * 2)
  ctx.fill()

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'
  ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Score: ${score.score}`, 10, 24)

  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'
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

  if (keyboard.justPressed('Space') && !alive) { restart(); return }
  if (!alive) { keyboard.update(); draw(); return }

  // Input (queue direction, prevent 180° reversal)
  if ((keyboard.justPressed('ArrowLeft') || keyboard.justPressed('KeyA')) && dir.x !== 1) nextDir = { x: -1, y: 0 }
  if ((keyboard.justPressed('ArrowRight') || keyboard.justPressed('KeyD')) && dir.x !== -1) nextDir = { x: 1, y: 0 }
  if ((keyboard.justPressed('ArrowUp') || keyboard.justPressed('KeyW')) && dir.y !== 1) nextDir = { x: 0, y: -1 }
  if ((keyboard.justPressed('ArrowDown') || keyboard.justPressed('KeyS')) && dir.y !== -1) nextDir = { x: 0, y: 1 }

  moveTimer += dt
  if (moveTimer >= speed) {
    moveTimer = 0
    dir = nextDir
    const head: Pos = { x: (snake[0].x + dir.x + COLS) % COLS, y: (snake[0].y + dir.y + ROWS) % ROWS }

    // Self collision
    if (snake.some(s => s.x === head.x && s.y === head.y)) { alive = false; keyboard.update(); draw(); return }

    snake.unshift(head)
    if (head.x === food.x && head.y === food.y) {
      score.addKill()
      food = spawnFood()
      speed = Math.max(0.04, speed - 0.003)
    } else {
      snake.pop()
    }
  }

  score.update(dt)
  keyboard.update()
  draw()
}

loop.start()
