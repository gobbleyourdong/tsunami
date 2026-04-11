import { ScoreSystem } from '@engine/systems/score'
import { FrameLoop } from '@engine/renderer/frame'

const W = 450, H = 550
const COLS = 7, ROWS = 8, CELL = 50, PAD = 25
const COLORS = ['#ef4444', '#4a9eff', '#22c55e', '#fbbf24', '#a855f7', '#ec4899']

let grid: number[][] = []
let selected: { col: number; row: number } | null = null
let animating = false
let moves = 0

const score = new ScoreSystem(3)

function randomColor(): number { return Math.floor(Math.random() * COLORS.length) }

function initGrid() {
  grid = Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => randomColor()))
  // Remove initial matches
  while (findMatches().length > 0) {
    grid = Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => randomColor()))
  }
}

function findMatches(): [number, number][] {
  const matched = new Set<string>()
  // Horizontal
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS - 2; c++) {
      if (grid[r][c] === grid[r][c+1] && grid[r][c] === grid[r][c+2]) {
        matched.add(`${r},${c}`); matched.add(`${r},${c+1}`); matched.add(`${r},${c+2}`)
      }
    }
  }
  // Vertical
  for (let c = 0; c < COLS; c++) {
    for (let r = 0; r < ROWS - 2; r++) {
      if (grid[r][c] === grid[r+1][c] && grid[r][c] === grid[r+2][c]) {
        matched.add(`${r},${c}`); matched.add(`${r+1},${c}`); matched.add(`${r+2},${c}`)
      }
    }
  }
  return [...matched].map(s => { const [r, c] = s.split(',').map(Number); return [r, c] })
}

function clearMatches(matches: [number, number][]): number {
  for (const [r, c] of matches) grid[r][c] = -1
  return matches.length
}

function dropTiles() {
  for (let c = 0; c < COLS; c++) {
    let empty = ROWS - 1
    for (let r = ROWS - 1; r >= 0; r--) {
      if (grid[r][c] !== -1) {
        grid[empty][c] = grid[r][c]
        if (empty !== r) grid[r][c] = -1
        empty--
      }
    }
    for (let r = empty; r >= 0; r--) grid[r][c] = randomColor()
  }
}

function swap(r1: number, c1: number, r2: number, c2: number) {
  const tmp = grid[r1][c1]; grid[r1][c1] = grid[r2][c2]; grid[r2][c2] = tmp
}

function isAdjacent(r1: number, c1: number, r2: number, c2: number): boolean {
  return Math.abs(r1 - r2) + Math.abs(c1 - c2) === 1
}

function cascadeResolve() {
  let totalCleared = 0
  let matches = findMatches()
  while (matches.length > 0) {
    totalCleared += clearMatches(matches)
    dropTiles()
    matches = findMatches()
  }
  if (totalCleared > 0) {
    for (let i = 0; i < Math.ceil(totalCleared / 3); i++) score.addKill()
  }
}

initGrid()

const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = W; canvas.height = H
Object.assign(canvas.style, { width: `${W}px`, height: `${H}px`, cursor: 'pointer' })
const ctx = canvas.getContext('2d')!

canvas.addEventListener('click', (e) => {
  if (animating) return
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left - PAD, my = e.clientY - rect.top - PAD - 40
  const col = Math.floor(mx / CELL), row = Math.floor(my / CELL)
  if (col < 0 || col >= COLS || row < 0 || row >= ROWS) return

  if (!selected) {
    selected = { col, row }
  } else {
    if (isAdjacent(selected.row, selected.col, row, col)) {
      swap(selected.row, selected.col, row, col)
      const matches = findMatches()
      if (matches.length > 0) {
        moves++
        cascadeResolve()
      } else {
        swap(selected.row, selected.col, row, col) // swap back
      }
    }
    selected = null
  }
})

function draw() {
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0, 0, W, H)

  // Title
  ctx.font = '20px JetBrains Mono, monospace'; ctx.fillStyle = '#e2e8f0'
  ctx.fillText('MATCH 3', PAD, 28)
  ctx.font = '14px JetBrains Mono, monospace'; ctx.fillStyle = '#94a3b8'
  ctx.fillText(`Score: ${score.score}  Moves: ${moves}`, PAD, H - 15)
  if (score.combo > 1) { ctx.fillStyle = '#fbbf24'; ctx.fillText(`Combo x${score.combo}!`, W - 120, 28) }

  // Grid
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = PAD + c * CELL, y = PAD + 40 + r * CELL
      const color = grid[r][c]
      if (color < 0) continue

      // Cell background
      ctx.fillStyle = 'rgba(255,255,255,0.03)'
      ctx.fillRect(x + 1, y + 1, CELL - 2, CELL - 2)

      // Gem
      ctx.fillStyle = COLORS[color]
      ctx.beginPath()
      ctx.arc(x + CELL / 2, y + CELL / 2, CELL / 2 - 6, 0, Math.PI * 2)
      ctx.fill()

      // Highlight
      ctx.fillStyle = 'rgba(255,255,255,0.2)'
      ctx.beginPath()
      ctx.arc(x + CELL / 2 - 4, y + CELL / 2 - 4, 6, 0, Math.PI * 2)
      ctx.fill()

      // Selection ring
      if (selected && selected.col === c && selected.row === r) {
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 3
        ctx.beginPath(); ctx.arc(x + CELL / 2, y + CELL / 2, CELL / 2 - 3, 0, Math.PI * 2); ctx.stroke()
      }
    }
  }
}

const loop = new FrameLoop()
loop.onUpdate = (stats) => {
  score.update(stats.dt)
  draw()
}

loop.start()
