import { KeyboardInput } from '@engine/input/keyboard'
import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 600, H = 700
const CAR_W = 20, CAR_H = 36
const PLAYER_SPEED = 250, AI_SPEED = 220
const ROAD_W = 300, ROAD_X = (W - ROAD_W) / 2
const LANE_COUNT = 3, LANE_W = ROAD_W / LANE_COUNT

interface AICar { x: number; y: number; lane: number; speed: number; color: string }

let playerX = W / 2, playerY = H - 100
let aiCars: AICar[] = []
let scrollY = 0, distance = 0
let spawnTimer = 0, alive = true
const AI_COLORS = ['#ef4444', '#fbbf24', '#22c55e', '#a855f7', '#ec4899']

const keyboard = new KeyboardInput()
keyboard.bind()
const score = new ScoreSystem()

function spawnAI() {
  const lane = Math.floor(Math.random() * LANE_COUNT)
  const x = ROAD_X + lane * LANE_W + LANE_W / 2
  const speed = 100 + Math.random() * 150
  const color = AI_COLORS[Math.floor(Math.random() * AI_COLORS.length)]
  aiCars.push({ x, y: -50, lane, speed, color })
}

function restart() {
  playerX = W / 2; playerY = H - 100
  aiCars = []; scrollY = 0; distance = 0; spawnTimer = 0; alive = true
  score.reset()
}

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px` })
const ctx = canvas.getContext('2d')!

function draw() {
  // Grass
  ctx.fillStyle = '#1a3a15'; ctx.fillRect(0, 0, W, H)

  // Road
  ctx.fillStyle = '#2d3748'; ctx.fillRect(ROAD_X, 0, ROAD_W, H)

  // Lane markers (scrolling)
  ctx.strokeStyle = '#475569'; ctx.lineWidth = 2; ctx.setLineDash([30, 20])
  for (let i = 1; i < LANE_COUNT; i++) {
    const x = ROAD_X + i * LANE_W
    ctx.beginPath(); ctx.moveTo(x, (scrollY % 50) - 50); ctx.lineTo(x, H + 50); ctx.stroke()
  }
  ctx.setLineDash([])

  // Road edges
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 3
  ctx.beginPath(); ctx.moveTo(ROAD_X, 0); ctx.lineTo(ROAD_X, H); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(ROAD_X + ROAD_W, 0); ctx.lineTo(ROAD_X + ROAD_W, H); ctx.stroke()

  // AI cars
  for (const c of aiCars) {
    ctx.fillStyle = c.color
    ctx.fillRect(c.x - CAR_W / 2, c.y - CAR_H / 2, CAR_W, CAR_H)
    ctx.fillStyle = 'rgba(0,0,0,0.3)'
    ctx.fillRect(c.x - CAR_W / 2 + 3, c.y - CAR_H / 2 + 4, CAR_W - 6, 8)
  }

  // Player car
  ctx.fillStyle = '#4a9eff'
  ctx.fillRect(playerX - CAR_W / 2, playerY - CAR_H / 2, CAR_W, CAR_H)
  ctx.fillStyle = 'rgba(255,255,255,0.3)'
  ctx.fillRect(playerX - CAR_W / 2 + 3, playerY - CAR_H / 2 + 4, CAR_W - 6, 8)

  // HUD
  ctx.font = '16px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText(`Distance: ${Math.floor(distance)}m`, 10, 24)
  ctx.fillText(`Passed: ${score.score}`, 10, 46)

  if (!alive) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
    ctx.textAlign = 'center'; ctx.font = '28px JetBrains Mono, monospace'
    ctx.fillStyle = '#ef4444'; ctx.fillText('CRASH!', W / 2, H / 2 - 10)
    ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
    ctx.fillText(`${Math.floor(distance)}m | ${score.score} passed | SPACE to restart`, W / 2, H / 2 + 20)
    ctx.textAlign = 'left'
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  const dt = stats.dt
  if (!alive) { if (keyboard.justPressed('Space')) restart(); keyboard.update(); draw(); return }

  distance += PLAYER_SPEED * dt * 0.1
  scrollY += PLAYER_SPEED * dt

  // Player steering
  if (keyboard.isDown('ArrowLeft') || keyboard.isDown('KeyA')) playerX -= PLAYER_SPEED * dt
  if (keyboard.isDown('ArrowRight') || keyboard.isDown('KeyD')) playerX += PLAYER_SPEED * dt
  playerX = Math.max(ROAD_X + CAR_W / 2 + 2, Math.min(ROAD_X + ROAD_W - CAR_W / 2 - 2, playerX))

  // Spawn AI
  spawnTimer += dt
  const rate = Math.max(0.4, 1.2 - distance * 0.002)
  if (spawnTimer >= rate) { spawnTimer = 0; spawnAI() }

  // Move AI (scroll toward player)
  for (const c of aiCars) {
    c.y += (PLAYER_SPEED - c.speed) * dt + PLAYER_SPEED * dt * 0.3
  }

  // Score passed cars
  for (const c of aiCars) {
    if (c.y > H + 50) score.addKill()
  }
  aiCars = aiCars.filter(c => c.y < H + 60)

  // Collision
  for (const c of aiCars) {
    if (Math.abs(c.x - playerX) < CAR_W && Math.abs(c.y - playerY) < CAR_H) {
      alive = false; break
    }
  }

  // Off-road death
  if (playerX - CAR_W / 2 < ROAD_X || playerX + CAR_W / 2 > ROAD_X + ROAD_W) alive = false

  score.update(dt); keyboard.update(); draw()
}

loop.start()
