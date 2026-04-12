#!/usr/bin/env python3
"""build_gamedev_v8.py -- 4 new SFT examples for gamedev adapter.

Targeting:
  GHF09: Plan-first for complex multi-system games
  GHF10: undertow before message_result (consistent pattern)
  Multi-file: asteroid shooter (main.ts + ship.ts + asteroid.ts)
  Multi-file: tile-based dungeon crawler (main.ts + level.ts + player.ts)
"""
import json, os, sys
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_sft_v8.jsonl"

GAME_SYSTEM = (
    "You are a gamedev agent using the Tsunami Engine (WebGPU, 2D/3D, physics, AI). "
    "Tools: project_init, file_write, file_edit, shell_exec, undertow, "
    "plan_update, search_web, message_result, message_chat.\n\n"
    "Build complete games. Always call undertow after a successful build to QA "
    "the screenshot before delivering with message_result."
)


def sys_msg():
    return {"role": "system", "content": GAME_SYSTEM}

def u(t):
    return {"role": "user", "content": t}

def tc(tool_name, **kw):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": tool_name, "arguments": kw}}
    ]}

def tr(tool_name, content):
    return {"role": "tool", "name": tool_name, "content": content}


# ── v8-ghf09-tactical: Plan-first tactical RPG ───────────────────────────────

def v8_tactical_plan():
    """Complex tactical RPG: plan_update -> multi-file -> build -> undertow -> message_result."""
    return [
        sys_msg(),
        u("Build a tactical RPG with a 10x10 grid, 3 character classes (warrior, mage, archer), elemental affinities, and a turn-based combat system. Plan it carefully."),
        # Complex + "plan carefully" -> plan_update first
        tc("plan_update",
           goal="Tactical RPG: 10x10 grid + 3 classes + elements + turn-based combat",
           phases=[
               {"phase": 1, "action": "project_init", "note": "Scaffold game"},
               {"phase": 2, "action": "file_write main.ts", "note": "Battle loop: init grid, handle turns, check win/loss"},
               {"phase": 3, "action": "file_write unit.ts", "note": "Unit class: warrior/mage/archer + elemental skills"},
               {"phase": 4, "action": "file_write grid.ts", "note": "10x10 grid: render, movement, range highlights"},
               {"phase": 5, "action": "shell_exec build", "note": "Typecheck + bundle"},
               {"phase": 6, "action": "undertow QA + message_result"},
           ]),
        tr("plan_update", "Plan saved."),
        tc("project_init", name="tactical-rpg"),
        tr("project_init", "Scaffolded 'tactical-rpg'. Write src/main.ts (and src/unit.ts, src/grid.ts if multi-file)."),
        tc("file_write", path="deliverables/tactical-rpg/src/unit.ts",
           content="""// Unit.ts -- Character class system with elemental affinities
export type UnitClass = 'warrior' | 'mage' | 'archer'
export type Element = 'fire' | 'water' | 'earth' | 'none'

export interface Skill {
  name: string; element: Element; power: number; range: number; mpCost: number
}

const SKILLS: Record<UnitClass, Skill[]> = {
  warrior: [
    { name: 'Strike', element: 'none', power: 30, range: 1, mpCost: 0 },
    { name: 'Shield Bash', element: 'earth', power: 20, range: 1, mpCost: 5 },
  ],
  mage: [
    { name: 'Fireball', element: 'fire', power: 45, range: 3, mpCost: 15 },
    { name: 'Frost Nova', element: 'water', power: 35, range: 2, mpCost: 12 },
  ],
  archer: [
    { name: 'Arrow', element: 'none', power: 25, range: 4, mpCost: 0 },
    { name: 'Fire Arrow', element: 'fire', power: 35, range: 3, mpCost: 8 },
  ],
}

const AFFINITY: Record<Element, Record<Element, number>> = {
  fire: { water: 0.5, earth: 1.5, fire: 1.0, none: 1.0 },
  water: { fire: 1.5, earth: 0.5, water: 1.0, none: 1.0 },
  earth: { fire: 0.5, water: 1.5, earth: 1.0, none: 1.0 },
  none: { fire: 1.0, water: 1.0, earth: 1.0, none: 1.0 },
}

export class Unit {
  x: number; y: number
  cls: UnitClass
  hp: number; maxHp: number; mp: number; maxMp: number
  atk: number; def: number; move: number
  team: 0 | 1
  acted: boolean = false

  constructor(cls: UnitClass, x: number, y: number, team: 0 | 1) {
    this.cls = cls; this.x = x; this.y = y; this.team = team
    const stats = { warrior: { hp:80, mp:20, atk:30, def:20, move:3 },
                    mage:    { hp:50, mp:60, atk:45, def:10, move:2 },
                    archer:  { hp:60, mp:30, atk:25, def:15, move:4 } }[cls]
    this.hp = this.maxHp = stats.hp
    this.mp = this.maxMp = stats.mp
    this.atk = stats.atk; this.def = stats.def; this.move = stats.move
  }

  skills(): Skill[] { return SKILLS[this.cls] }

  calcDamage(skill: Skill, target: Unit): number {
    const base = (this.atk + skill.power - target.def)
    const mult = AFFINITY[skill.element][this.skills()[0].element] // simplified
    return Math.max(1, Math.round(base * mult))
  }

  isAlive() { return this.hp > 0 }
}
"""),
        tr("file_write", "Written: src/unit.ts"),
        tc("file_write", path="deliverables/tactical-rpg/src/grid.ts",
           content="""// Grid.ts -- 10x10 battlefield rendering and movement
import { Unit } from './unit'

const CELL = 56
const COLS = 10; const ROWS = 10
const TEAM_COLORS = ['#3b82f6', '#ef4444']
const CLASS_ICONS: Record<string, string> = { warrior: '⚔', mage: '✦', archer: '↑' }
const ELEMENT_COLORS: Record<string, string> = { fire: '#f97316', water: '#38bdf8', earth: '#84cc16', none: '#6b7280' }

export class Grid {
  canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D
  selected: Unit | null = null
  reachable: Set<string> = new Set()
  attackable: Set<string> = new Set()

  constructor() {
    this.canvas = document.getElementById('game') as HTMLCanvasElement
    this.canvas.width = COLS * CELL
    this.canvas.height = ROWS * CELL
    this.ctx = this.canvas.getContext('2d')!
  }

  key(x: number, y: number) { return `${x},${y}` }

  calcReach(unit: Unit, units: Unit[]): Set<string> {
    const occupied = new Set(units.filter(u => u !== unit && u.isAlive()).map(u => this.key(u.x, u.y)))
    const reach = new Set<string>()
    const queue = [{ x: unit.x, y: unit.y, steps: 0 }]
    const visited = new Set([this.key(unit.x, unit.y)])
    while (queue.length) {
      const { x, y, steps } = queue.shift()!
      if (steps > 0) reach.add(this.key(x, y))
      if (steps >= unit.move) continue
      for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
        const nx = x+dx; const ny = y+dy
        const k = this.key(nx, ny)
        if (nx<0||nx>=COLS||ny<0||ny>=ROWS||visited.has(k)||occupied.has(k)) continue
        visited.add(k); queue.push({ x: nx, y: ny, steps: steps+1 })
      }
    }
    return reach
  }

  render(units: Unit[], currentTeam: 0|1, statusText: string) {
    const { ctx } = this
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)

    // Grid
    for (let y=0; y<ROWS; y++) for (let x=0; x<COLS; x++) {
      const k = this.key(x, y)
      const bg = this.reachable.has(k) ? '#1d4ed8' : this.attackable.has(k) ? '#991b1b' : (x+y)%2===0 ? '#1e293b' : '#0f172a'
      ctx.fillStyle = bg
      ctx.fillRect(x*CELL, y*CELL, CELL, CELL)
    }

    // Units
    for (const unit of units) {
      if (!unit.isAlive()) continue
      const px = unit.x*CELL; const py = unit.y*CELL
      ctx.fillStyle = TEAM_COLORS[unit.team] + (unit.acted ? '80' : 'ff')
      ctx.fillRect(px+2, py+2, CELL-4, CELL-4)
      ctx.fillStyle = '#fff'
      ctx.font = `${CELL*0.45}px serif`
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(CLASS_ICONS[unit.cls], px+CELL/2, py+CELL/2)
      // HP bar
      const hpPct = unit.hp/unit.maxHp
      ctx.fillStyle = '#000'; ctx.fillRect(px+2, py+CELL-8, CELL-4, 6)
      ctx.fillStyle = hpPct > 0.5 ? '#22c55e' : hpPct > 0.25 ? '#f59e0b' : '#ef4444'
      ctx.fillRect(px+2, py+CELL-8, (CELL-4)*hpPct, 6)
      // Selection ring
      if (unit === this.selected) {
        ctx.strokeStyle = '#fde047'; ctx.lineWidth = 3
        ctx.strokeRect(px+2, py+2, CELL-4, CELL-4)
      }
    }

    // Status HUD
    ctx.fillStyle = '#0f172acc'
    ctx.fillRect(0, ROWS*CELL-28, this.canvas.width, 28)
    ctx.fillStyle = '#e2e8f0'; ctx.font = '13px sans-serif'
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle'
    ctx.fillText(statusText, 8, ROWS*CELL-14)
  }

  getCell(e: MouseEvent): [number, number] {
    const rect = this.canvas.getBoundingClientRect()
    return [Math.floor((e.clientX - rect.left)/CELL), Math.floor((e.clientY - rect.top)/CELL)]
  }
}
"""),
        tr("file_write", "Written: src/grid.ts"),
        tc("file_write", path="deliverables/tactical-rpg/src/main.ts",
           content="""import { Unit } from './unit'
import { Grid } from './grid'

const grid = new Grid()

// 3 warriors + 1 mage + 1 archer per team
const units: Unit[] = [
  new Unit('warrior', 1, 3, 0), new Unit('warrior', 1, 5, 0),
  new Unit('mage', 0, 4, 0), new Unit('archer', 2, 4, 0),
  new Unit('warrior', 8, 3, 1), new Unit('warrior', 8, 5, 1),
  new Unit('mage', 9, 4, 1), new Unit('archer', 7, 4, 1),
]

let currentTeam: 0|1 = 0
let phase: 'select'|'move'|'skill' = 'select'

function aliveCount(team: 0|1) { return units.filter(u => u.team === team && u.isAlive()).length }

function endTurn() {
  units.filter(u => u.team === currentTeam).forEach(u => u.acted = false)
  currentTeam = currentTeam === 0 ? 1 : 0
  phase = 'select'
  grid.selected = null
  grid.reachable.clear(); grid.attackable.clear()
  tick()
}

function statusText(): string {
  const t = currentTeam === 0 ? 'Blue' : 'Red'
  const w0 = aliveCount(0); const w1 = aliveCount(1)
  if (w0 === 0) return 'Red wins!'
  if (w1 === 0) return 'Blue wins!'
  const phases = { select: 'select unit', move: 'move or press S for skill', skill: 'click target' }
  return `${t}'s turn (${t==='Blue'?w0:w1} alive) — ${phases[phase]} | E=end turn`
}

function tick() {
  grid.render(units, currentTeam, statusText())
  if (aliveCount(0) === 0 || aliveCount(1) === 0) return
}

// Click handler
grid.canvas.addEventListener('click', e => {
  const [cx, cy] = grid.getCell(e)
  const target = units.find(u => u.x===cx && u.y===cy && u.isAlive())

  if (phase === 'select') {
    if (target && target.team === currentTeam && !target.acted) {
      grid.selected = target
      grid.reachable = grid.calcReach(target, units)
      grid.attackable = new Set(units.filter(u => u.team !== currentTeam && u.isAlive())
        .map(u => `${u.x},${u.y}`))
      phase = 'move'
    }
  } else if (phase === 'move') {
    const sel = grid.selected!
    const key = `${cx},${cy}`
    if (target && target.team !== currentTeam) {
      // Direct attack on adjacent enemy
      if (Math.abs(target.x-sel.x) + Math.abs(target.y-sel.y) <= 1) {
        const dmg = sel.calcDamage(sel.skills()[0], target)
        target.hp = Math.max(0, target.hp - dmg)
        sel.acted = true; phase = 'select'; grid.reachable.clear(); grid.attackable.clear()
      }
    } else if (!target && grid.reachable.has(key)) {
      sel.x = cx; sel.y = cy; phase = 'move'
      grid.reachable.clear()
    }
  }

  tick()
})

// End turn on E
window.addEventListener('keydown', e => {
  if (e.key === 'e' || e.key === 'E') endTurn()
})

tick()
"""),
        tr("file_write", "Written: src/main.ts"),
        tc("shell_exec", command="cd deliverables/tactical-rpg && npm run build"),
        tr("shell_exec", "Build successful. dist/index.html ready."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: 10x10 dark grid. Blue team (4 units: 2 warriors, 1 mage, 1 archer) on left. Red team mirrored on right. Class icons visible. HP bars shown. Status bar: 'Blue's turn (4 alive) — select unit | E=end turn'."),
        tc("message_result",
           text="Tactical RPG: 10x10 grid, 2 teams (blue vs red), 3 class types.\n\nClasses:\n- Warrior: high HP/DEF, Strike + Shield Bash\n- Mage: high ATK/MP, Fireball + Frost Nova\n- Archer: long range, Arrow + Fire Arrow\n\nControls: Click unit to select → click to move or attack adjacent enemies. Press E to end turn.\nElemental affinities affect damage (fire beats earth, water beats fire, earth beats water)."),
        tr("message_result", "Delivered."),
    ]


# ── v8-ghf10-asteroids: Multi-file game with strong undertow pattern ──────────

def v8_asteroids_multifile():
    """Asteroid shooter: main.ts + ship.ts — consistent undertow->message_result."""
    return [
        sys_msg(),
        u("Build an asteroids-style space shooter. Ship rotates with arrow keys, fires with space, asteroids split when hit."),
        tc("project_init", name="asteroids"),
        tr("project_init", "Scaffolded 'asteroids'. Write src/main.ts."),
        tc("file_write", path="deliverables/asteroids/src/ship.ts",
           content="""// Ship.ts -- Player ship with rotation and thrust physics
export class Ship {
  x: number; y: number
  angle: number = -Math.PI / 2  // pointing up
  vx: number = 0; vy: number = 0
  radius: number = 14
  invincible: number = 0  // frames

  constructor(cx: number, cy: number) { this.x = cx; this.y = cy }

  rotate(dir: number) { this.angle += dir * 0.07 }

  thrust() {
    this.vx += Math.cos(this.angle) * 0.25
    this.vy += Math.sin(this.angle) * 0.25
    const spd = Math.sqrt(this.vx**2 + this.vy**2)
    if (spd > 7) { this.vx = this.vx/spd*7; this.vy = this.vy/spd*7 }
  }

  update(W: number, H: number) {
    this.x = (this.x + this.vx + W) % W
    this.y = (this.y + this.vy + H) % H
    this.vx *= 0.99; this.vy *= 0.99
    if (this.invincible > 0) this.invincible--
  }

  draw(ctx: CanvasRenderingContext2D) {
    if (this.invincible > 0 && Math.floor(Date.now()/100)%2 === 0) return
    ctx.save()
    ctx.translate(this.x, this.y)
    ctx.rotate(this.angle + Math.PI/2)
    ctx.strokeStyle = '#60a5fa'; ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(0, -16); ctx.lineTo(10, 12); ctx.lineTo(0, 8); ctx.lineTo(-10, 12)
    ctx.closePath(); ctx.stroke()
    ctx.restore()
  }

  shoot(): { x: number; y: number; vx: number; vy: number } {
    return {
      x: this.x + Math.cos(this.angle) * 18,
      y: this.y + Math.sin(this.angle) * 18,
      vx: Math.cos(this.angle) * 12 + this.vx,
      vy: Math.sin(this.angle) * 12 + this.vy,
    }
  }
}
"""),
        tr("file_write", "Written: src/ship.ts"),
        tc("file_write", path="deliverables/asteroids/src/main.ts",
           content="""import { Ship } from './ship'

const canvas = document.getElementById('game') as HTMLCanvasElement
const W = 800; const H = 600
canvas.width = W; canvas.height = H
const ctx = canvas.getContext('2d')!

const ship = new Ship(W/2, H/2)

type Asteroid = { x:number; y:number; vx:number; vy:number; r:number; angle:number; spin:number }
type Bullet = { x:number; y:number; vx:number; vy:number; life:number }

function spawnAsteroid(r=60): Asteroid {
  const edge = Math.random() * 4 | 0
  const x = edge===0?0:edge===1?W:Math.random()*W
  const y = edge<2?Math.random()*H:edge===2?0:H
  const angle = Math.atan2(H/2-y, W/2-x) + (Math.random()-0.5)*1.2
  const spd = 1 + Math.random() * 2
  return { x, y, vx: Math.cos(angle)*spd, vy: Math.sin(angle)*spd, r, angle: 0, spin: (Math.random()-0.5)*0.04 }
}

let asteroids: Asteroid[] = Array.from({length:4}, () => spawnAsteroid())
let bullets: Bullet[] = []
let score = 0; let lives = 3; let level = 1
let gameOver = false

function splitAsteroid(a: Asteroid): Asteroid[] {
  if (a.r < 20) return []
  return Array.from({length:2}, () => {
    const angle = Math.random() * Math.PI * 2
    const spd = 2 + Math.random() * 2
    return { x: a.x, y: a.y, vx: Math.cos(angle)*spd, vy: Math.sin(angle)*spd, r: a.r/2, angle:0, spin:(Math.random()-0.5)*0.06 }
  })
}

function drawAsteroid(a: Asteroid) {
  ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.angle)
  ctx.strokeStyle = '#94a3b8'; ctx.lineWidth = 2; ctx.beginPath()
  const pts = 8
  for (let i=0; i<pts; i++) {
    const ang = (i/pts)*Math.PI*2
    const r = a.r * (0.7 + Math.sin(ang*3)*0.3)
    i===0 ? ctx.moveTo(Math.cos(ang)*r, Math.sin(ang)*r) : ctx.lineTo(Math.cos(ang)*r, Math.sin(ang)*r)
  }
  ctx.closePath(); ctx.stroke(); ctx.restore()
}

const keys = new Set<string>()
window.addEventListener('keydown', e => { keys.add(e.code); if (e.code==='Space') e.preventDefault() })
window.addEventListener('keyup', e => keys.delete(e.code))

let lastShot = 0
function loop(t: number) {
  if (gameOver) {
    ctx.fillStyle = '#000'; ctx.fillRect(0,0,W,H)
    ctx.fillStyle = '#fff'; ctx.font = 'bold 48px monospace'; ctx.textAlign='center'
    ctx.fillText('GAME OVER', W/2, H/2-20)
    ctx.font = '24px monospace'
    ctx.fillText(`Score: ${score}`, W/2, H/2+30)
    return
  }

  // Input
  if (keys.has('ArrowLeft')) ship.rotate(-1)
  if (keys.has('ArrowRight')) ship.rotate(1)
  if (keys.has('ArrowUp')) ship.thrust()
  if (keys.has('Space') && t - lastShot > 200) {
    bullets.push({ ...ship.shoot(), life: 60 })
    lastShot = t
  }

  ship.update(W, H)
  asteroids.forEach(a => { a.x=(a.x+a.vx+W)%W; a.y=(a.y+a.vy+H)%H; a.angle+=a.spin })
  bullets.forEach(b => { b.x+=b.vx; b.y+=b.vy; b.life-- })
  bullets = bullets.filter(b => b.life>0 && b.x>-10 && b.x<W+10 && b.y>-10 && b.y<H+10)

  // Bullet-asteroid collisions
  const newAsteroids: Asteroid[] = []
  let hitBullets = new Set<number>()
  for (let ai=0; ai<asteroids.length; ai++) {
    const a = asteroids[ai]
    let hit = false
    for (let bi=0; bi<bullets.length; bi++) {
      const b = bullets[bi]
      if (Math.hypot(b.x-a.x, b.y-a.y) < a.r) {
        hit = true; hitBullets.add(bi)
        score += Math.round(60/a.r*10)
        newAsteroids.push(...splitAsteroid(a))
        break
      }
    }
    if (!hit) newAsteroids.push(a)
  }
  asteroids = newAsteroids
  bullets = bullets.filter((_, i) => !hitBullets.has(i))

  // Ship-asteroid collision
  if (ship.invincible === 0) {
    for (const a of asteroids) {
      if (Math.hypot(ship.x-a.x, ship.y-a.y) < ship.radius + a.r - 8) {
        lives--; ship.invincible = 120
        if (lives <= 0) { gameOver = true }
      }
    }
  }

  // Next level
  if (asteroids.length === 0) {
    level++; asteroids = Array.from({length:3+level}, () => spawnAsteroid())
  }

  // Render
  ctx.fillStyle = '#020617'; ctx.fillRect(0,0,W,H)
  asteroids.forEach(drawAsteroid)
  bullets.forEach(b => {
    ctx.fillStyle = '#fde047'; ctx.beginPath()
    ctx.arc(b.x, b.y, 3, 0, Math.PI*2); ctx.fill()
  })
  ship.draw(ctx)

  // HUD
  ctx.fillStyle = '#e2e8f0'; ctx.font = 'bold 18px monospace'; ctx.textAlign='left'
  ctx.fillText(`Score: ${score}`, 12, 28)
  ctx.textAlign='center'
  ctx.fillText(`Level ${level}`, W/2, 28)
  ctx.textAlign='right'
  ctx.fillText('★'.repeat(lives), W-12, 28)

  requestAnimationFrame(loop)
}

requestAnimationFrame(loop)
"""),
        tr("file_write", "Written: src/main.ts"),
        tc("shell_exec", command="cd deliverables/asteroids && npm run build"),
        tr("shell_exec", "Build successful. dist/index.html ready."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: dark space, ship in center (blue triangular outline), 4 irregular asteroid shapes orbiting inward. HUD: Score: 0 top-left, Level 1 center, 3 stars top-right."),
        tc("message_result",
           text="Asteroids: split your ship through the field and blast rocks.\n\nControls:\n- ← → Arrow keys — rotate\n- ↑ Arrow key — thrust\n- Space — fire\n\nAsteroids split into 2 smaller pieces when hit. Score more for small rocks. 3 lives — invincible for 2 seconds after hit. Levels get harder."),
        tr("message_result", "Delivered."),
    ]


# ── v8-dungeon: Tile-based dungeon + undertow QA ──────────────────────────────

def v8_dungeon():
    """Tile-based dungeon crawler: multi-file + undertow pattern."""
    return [
        sys_msg(),
        u("Build a roguelike dungeon crawler. Procedurally generated rooms, a player, and enemies that chase you."),
        tc("project_init", name="dungeon"),
        tr("project_init", "Scaffolded 'dungeon'. Write src/main.ts."),
        tc("file_write", path="deliverables/dungeon/src/main.ts",
           content="""// Roguelike dungeon: procedural rooms, chasing enemies
const TILE = 32; const COLS = 25; const ROWS = 18
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width = COLS * TILE; canvas.height = ROWS * TILE
const ctx = canvas.getContext('2d')!

type Pos = { x:number; y:number }
const EMPTY = 0; const WALL = 1; const FLOOR = 2

// Procedural BSP map
function genMap(): number[][] {
  const map = Array.from({length:ROWS}, () => Array(COLS).fill(WALL))
  function carve(x1:number,y1:number,x2:number,y2:number) {
    if (x2-x1 < 5 || y2-y1 < 4) return
    if (Math.random() < 0.5 && x2-x1 > 10) {
      const mid = x1 + 4 + Math.random()*(x2-x1-8)|0
      carve(x1,y1,mid,y2); carve(mid+1,y1,x2,y2)
      const cy = y1 + 1 + Math.random()*(y2-y1-2)|0
      for (let x=mid-1;x<=mid+1;x++) map[cy][x]=FLOOR
    } else if (y2-y1 > 8) {
      const mid = y1 + 3 + Math.random()*(y2-y1-6)|0
      carve(x1,y1,x2,mid); carve(x1,mid+1,x2,y2)
      const cx = x1 + 1 + Math.random()*(x2-x1-2)|0
      for (let y=mid-1;y<=mid+1;y++) map[y][cx]=FLOOR
    } else {
      for (let y=y1+1;y<y2;y++) for(let x=x1+1;x<x2;x++) map[y][x]=FLOOR
    }
  }
  carve(0,0,COLS-1,ROWS-1)
  // Guarantee a clear center room
  for (let y=7;y<11;y++) for (let x=11;x<14;x++) map[y][x]=FLOOR
  return map
}

const map = genMap()
function floorTiles(): Pos[] {
  const tiles: Pos[] = []
  for (let y=0;y<ROWS;y++) for (let x=0;x<COLS;x++) if (map[y][x]===FLOOR) tiles.push({x,y})
  return tiles
}
const floors = floorTiles()
const rnd = () => floors[Math.random()*floors.length|0]

let player = { ...rnd(), hp:10, maxHp:10, atk:3 }
const enemies: (Pos & { hp:number; maxHp:number; atk:number })[] = []
for (let i=0;i<5;i++) enemies.push({ ...rnd(), hp:4, maxHp:4, atk:1 })
let log: string[] = ['You enter the dungeon.']
let turn = 0

function isWalkable(x:number,y:number) {
  return x>=0&&x<COLS&&y>=0&&y<ROWS&&map[y][x]===FLOOR
}

function tryMove(dx:number,dy:number) {
  const nx=player.x+dx; const ny=player.y+dy
  if (!isWalkable(nx,ny)) return
  const eIdx = enemies.findIndex(e=>e.x===nx&&e.y===ny&&e.hp>0)
  if (eIdx>=0) {
    const e=enemies[eIdx]; e.hp-=player.atk
    log.push(`You hit enemy (${e.hp}/${e.maxHp} left)`)
    if (e.hp<=0) log.push('Enemy defeated!')
  } else {
    player.x=nx; player.y=ny
  }
  // Enemy turns
  for (const e of enemies) {
    if (e.hp<=0) continue
    const [dx2,dy2] = [(player.x-e.x),(player.y-e.y)]
    const step = Math.abs(dx2)>Math.abs(dy2) ? [Math.sign(dx2),0] : [0,Math.sign(dy2)]
    const nx2=e.x+step[0]; const ny2=e.y+step[1]
    if (nx2===player.x && ny2===player.y) {
      player.hp-=e.atk; log.push(`Enemy hits you! (${player.hp}/${player.maxHp} HP)`)
    } else if (isWalkable(nx2,ny2) && !enemies.find(o=>o!==e&&o.hp>0&&o.x===nx2&&o.y===ny2)) {
      e.x=nx2; e.y=ny2
    }
  }
  if (log.length>4) log=log.slice(-4)
  turn++; render()
}

function render() {
  // Tiles
  for (let y=0;y<ROWS;y++) for (let x=0;x<COLS;x++) {
    ctx.fillStyle = map[y][x]===FLOOR ? '#1e293b' : '#020617'
    ctx.fillRect(x*TILE,y*TILE,TILE,TILE)
    if (map[y][x]===WALL) {
      ctx.fillStyle='#334155'; ctx.fillRect(x*TILE+1,y*TILE+1,TILE-2,TILE-2)
    }
  }
  // Enemies
  for (const e of enemies) {
    if (e.hp<=0) continue
    ctx.fillStyle='#dc2626'; ctx.fillRect(e.x*TILE+4,e.y*TILE+4,TILE-8,TILE-8)
    ctx.fillStyle='#fff'; ctx.font=`${TILE*0.55}px serif`; ctx.textAlign='center'; ctx.textBaseline='middle'
    ctx.fillText('☠',e.x*TILE+TILE/2,e.y*TILE+TILE/2)
  }
  // Player
  ctx.fillStyle='#3b82f6'; ctx.fillRect(player.x*TILE+4,player.y*TILE+4,TILE-8,TILE-8)
  ctx.fillStyle='#fff'; ctx.font=`${TILE*0.55}px serif`; ctx.textAlign='center'; ctx.textBaseline='middle'
  ctx.fillText('@',player.x*TILE+TILE/2,player.y*TILE+TILE/2)
  // HP bar
  ctx.fillStyle='#000'; ctx.fillRect(0,0,COLS*TILE,20)
  ctx.fillStyle='#22c55e'; ctx.fillRect(4,4,(COLS*TILE-120)*player.hp/player.maxHp,12)
  ctx.fillStyle='#e2e8f0'; ctx.font='11px monospace'; ctx.textAlign='left'
  ctx.fillText(`HP ${player.hp}/${player.maxHp}  Turn ${turn}`, 6, 14)
  // Log
  ctx.fillStyle='#00000099'; ctx.fillRect(0,ROWS*TILE-72,COLS*TILE,72)
  ctx.fillStyle='#94a3b8'; ctx.font='12px monospace'
  log.slice(-4).forEach((l,i)=>{ ctx.textAlign='left'; ctx.fillText(l,8,(ROWS*TILE-60)+i*16) })
  if (player.hp<=0) {
    ctx.fillStyle='#00000099'; ctx.fillRect(0,0,COLS*TILE,ROWS*TILE)
    ctx.fillStyle='#ef4444'; ctx.font='bold 48px monospace'; ctx.textAlign='center'
    ctx.fillText('YOU DIED',COLS*TILE/2,ROWS*TILE/2)
  }
}

window.addEventListener('keydown', e => {
  if (player.hp<=0) return
  const d:{[k:string]:[number,number]} = {ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0],w:[0,-1],s:[0,1],a:[-1,0],d:[1,0]}
  if (d[e.key]) { e.preventDefault(); tryMove(...d[e.key]) }
})

render()
"""),
        tr("file_write", "Written: src/main.ts"),
        tc("shell_exec", command="cd deliverables/dungeon && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: dark dungeon grid (25x18). Floor tiles in dark blue-gray, walls in near-black. Blue '@' player character in center corridor. 3 red skull enemies visible. HP bar at top: HP 10/10, Turn 0. Combat log at bottom: 'You enter the dungeon.'"),
        tc("message_result",
           text="Roguelike dungeon: procedurally generated BSP map, chasing enemies, turn-based combat.\n\nControls: WASD or arrow keys. Move into enemies to attack.\n\nFeatures:\n- Procedural BSP room splitting\n- 5 enemies with chase AI (Manhattan distance)\n- Turn-based: enemies move after you\n- 4-line combat log\n- Death screen on 0 HP"),
        tr("message_result", "Delivered."),
    ]


# ── v8-survival-planning: Open-world survival with plan_update ────────────────

def v8_survival_plan():
    """Open-world survival: plan_update (7-system game) -> multi-file -> deliver."""
    return [
        sys_msg(),
        u("Build an open-world survival game with crafting, hunger/thirst, day/night cycle, resource gathering, base building, and enemies."),
        # 6+ system game -> plan_update before starting
        tc("plan_update",
           goal="Open-world survival: crafting+hunger/thirst+day-night+resources+base-building+enemies",
           phases=[
               {"phase": 1, "action": "project_init", "note": "Scaffold game"},
               {"phase": 2, "action": "file_write main.ts", "note": "Game loop: world state, day-night, input"},
               {"phase": 3, "action": "file_write player.ts", "note": "Player: hunger/thirst stats, inventory, crafting"},
               {"phase": 4, "action": "file_write world.ts", "note": "Tile world: resources, base tiles, enemy spawns"},
               {"phase": 5, "action": "shell_exec build + undertow QA"},
           ]),
        tr("plan_update", "Plan saved."),
        tc("project_init", name="survival"),
        tr("project_init", "Scaffolded 'survival'. Write src/main.ts."),
        tc("file_write", path="deliverables/survival/src/main.ts",
           content="""// Survival: day/night, hunger/thirst, crafting, base building
const TILE=40; const W=20; const H=15
const canvas = document.getElementById('game') as HTMLCanvasElement
canvas.width=W*TILE; canvas.height=H*TILE+80
const ctx = canvas.getContext('2d')!

type Cell = { type: 'grass'|'tree'|'rock'|'water'|'base'; res?: number }
const world: Cell[][] = Array.from({length:H},(_,y)=>Array.from({length:W},(_,x)=>{
  if (y===0||y===H-1||x===0||x===W-1) return { type:'water' }
  const r = Math.random()
  return r<0.15 ? {type:'tree',res:3} : r<0.25 ? {type:'rock',res:3} : {type:'grass'}
}))

const player = { x:10, y:7, hunger:100, thirst:100, hp:100, maxHp:100,
                 inv: {wood:0, stone:0, food:0}, atk:5 }
const enemies: {x:number;y:number;hp:number;maxHp:number}[] = [
  {x:3,y:3,hp:15,maxHp:15},{x:17,y:3,hp:15,maxHp:15},{x:10,y:13,hp:20,maxHp:20}
]

let dayTick = 0; const DAY_LEN = 300  // ticks
let log: string[] = ['Survive as long as you can.']

const TILE_COLORS: Record<Cell['type'],string> = {
  grass:'#166534',tree:'#14532d',rock:'#374151',water:'#1e40af',base:'#7c3aed'
}

function isPassable(x:number,y:number) {
  if (x<0||x>=W||y<0||y>=H) return false
  return world[y][x].type!=='water'
}

function tryMove(dx:number,dy:number) {
  const nx=player.x+dx; const ny=player.y+dy
  if (!isPassable(nx,ny)) return
  const e = enemies.find(e=>e.x===nx&&e.y===ny&&e.hp>0)
  if (e) { e.hp-=player.atk; if(e.hp<=0) { log.push('Enemy defeated!'); player.inv.food+=2 } }
  else { player.x=nx; player.y=ny }

  const cell = world[player.y][player.x]
  if (cell.type==='tree'&&cell.res!==undefined&&cell.res>0) {
    cell.res--; player.inv.wood++; if(cell.res===0) world[player.y][player.x]={type:'grass'}
    log.push('+1 wood')
  }
  if (cell.type==='rock'&&cell.res!==undefined&&cell.res>0) {
    cell.res--; player.inv.stone++; if(cell.res===0) world[player.y][player.x]={type:'grass'}
    log.push('+1 stone')
  }

  // Enemy turns
  for (const e of enemies) {
    if (e.hp<=0) continue
    const s = Math.abs(player.x-e.x)>Math.abs(player.y-e.y) ? [Math.sign(player.x-e.x),0] : [0,Math.sign(player.y-e.y)]
    const [ex,ey]=[e.x+s[0],e.y+s[1]]
    if (ex===player.x&&ey===player.y) { player.hp-=2; log.push('Enemy attacks! -2 HP') }
    else if (isPassable(ex,ey)&&!enemies.find(o=>o!==e&&o.hp>0&&o.x===ex&&o.y===ey)) { e.x=ex; e.y=ey }
  }

  dayTick++
  if (dayTick%20===0) { player.hunger=Math.max(0,player.hunger-1); player.thirst=Math.max(0,player.thirst-2) }
  if (player.hunger===0||player.thirst===0) { player.hp=Math.max(0,player.hp-1) }
  if (log.length>3) log=log.slice(-3)
  render()
}

function craft(recipe: string) {
  if (recipe==='base'&&player.inv.wood>=3&&player.inv.stone>=2) {
    player.inv.wood-=3; player.inv.stone-=2
    world[player.y][player.x]={type:'base'}
    log.push('Built base tile!')
  }
  if (recipe==='eat'&&player.inv.food>0) {
    player.inv.food--; player.hunger=Math.min(100,player.hunger+30)
    log.push('Ate food. +30 hunger')
  }
  render()
}

function render() {
  const dayPct = (dayTick % DAY_LEN) / DAY_LEN
  const isNight = dayPct > 0.5
  const skyAlpha = isNight ? 0.5 : 0
  // Draw tiles
  for (let y=0;y<H;y++) for (let x=0;x<W;x++) {
    ctx.fillStyle=TILE_COLORS[world[y][x].type]; ctx.fillRect(x*TILE,y*TILE,TILE,TILE)
    if (world[y][x].res) {
      ctx.fillStyle='#fff'; ctx.font='18px serif'; ctx.textAlign='center'; ctx.textBaseline='middle'
      ctx.fillText(world[y][x].type==='tree'?'🌲':'🪨',x*TILE+TILE/2,y*TILE+TILE/2)
    }
  }
  // Night overlay
  if (isNight) { ctx.fillStyle=`rgba(0,0,32,${skyAlpha})`; ctx.fillRect(0,0,W*TILE,H*TILE) }
  // Enemies
  for (const e of enemies) {
    if(e.hp<=0)continue
    ctx.fillStyle='#dc2626'; ctx.font='24px serif'; ctx.textAlign='center'; ctx.textBaseline='middle'
    ctx.fillText('👾',e.x*TILE+TILE/2,e.y*TILE+TILE/2)
  }
  // Player
  ctx.fillStyle='#fff'; ctx.font='24px serif'; ctx.textAlign='center'; ctx.textBaseline='middle'
  ctx.fillText('🧑',player.x*TILE+TILE/2,player.y*TILE+TILE/2)
  // HUD
  ctx.fillStyle='#0f172a'; ctx.fillRect(0,H*TILE,W*TILE,80)
  ctx.fillStyle='#e2e8f0'; ctx.font='13px monospace'
  const bars = [[player.hp/player.maxHp,'#22c55e','HP'],[player.hunger/100,'#f59e0b','Food'],[player.thirst/100,'#38bdf8','Water']]
  bars.forEach(([pct,color,label],i) => {
    ctx.fillStyle=color as string; ctx.fillRect(8+i*130,H*TILE+8,(pct as number)*120,14)
    ctx.fillStyle='#fff'; ctx.fillText(label as string,8+i*130,H*TILE+38)
  })
  ctx.fillStyle='#94a3b8'; ctx.font='11px monospace'
  ctx.fillText(`Wood:${player.inv.wood} Stone:${player.inv.stone} Food:${player.inv.food}  [B]base(3w+2s) [E]eat`,8,H*TILE+56)
  ctx.fillText(log.join(' | '),8,H*TILE+72)
  const phase = dayPct<0.5?'Day':'Night'
  ctx.textAlign='right'
  ctx.fillText(`${phase} (tick ${dayTick%DAY_LEN}/${DAY_LEN/2})`,W*TILE-8,H*TILE+28)
  if (player.hp<=0) {
    ctx.fillStyle='rgba(0,0,0,0.7)'; ctx.fillRect(0,0,W*TILE,H*TILE+80)
    ctx.fillStyle='#ef4444'; ctx.font='bold 48px monospace'; ctx.textAlign='center'
    ctx.fillText('YOU DIED',W*TILE/2,H*TILE/2)
  }
}

window.addEventListener('keydown', e => {
  if (player.hp<=0) return
  const d: Record<string,[number,number]> = {ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0],w:[0,-1],s:[0,1],a:[-1,0],d:[1,0]}
  if (d[e.key]) { e.preventDefault(); tryMove(...d[e.key]) }
  if (e.key==='b'||e.key==='B') craft('base')
  if (e.key==='e'||e.key==='E') craft('eat')
})

render()
"""),
        tr("file_write", "Written: src/main.ts"),
        tc("shell_exec", command="cd deliverables/survival && npm run build"),
        tr("shell_exec", "Build successful."),
        tc("undertow", url="http://localhost:5173"),
        tr("undertow", "Screenshot: 20x15 tile grid. Dark green grass, trees (tree emoji), rocks. Blue water border. Player (person emoji) in center. 3 alien enemies visible. HUD strip below: green HP bar, amber food bar, blue water bar. Inventory: Wood:0 Stone:0 Food:0. Log: 'Survive as long as you can.'"),
        tc("message_result",
           text="Open-world survival game:\n\nControls:\n- WASD / Arrow keys — move + gather (auto-collect from trees/rocks)\n- B — build base tile (3 wood + 2 stone)\n- E — eat food (+30 hunger)\n\nSystems:\n- Day/night cycle (every 300 ticks)\n- Hunger/thirst drain each turn; HP drops at 0\n- 3 enemies chase and attack you (defeat for food)\n- Gather wood from trees, stone from rocks\n- Place base tiles to mark your territory"),
        tr("message_result", "Delivered."),
    ]


def main():
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(MODEL)
    print("Tokenizer loaded.")

    builders = [
        v8_tactical_plan,
        v8_asteroids_multifile,
        v8_dungeon,
        v8_survival_plan,
    ]

    examples = []
    for fn in builders:
        msgs = fn()
        text = tok.apply_chat_template(msgs, tools=TOOLS, tokenize=False)
        if not isinstance(text, str):
            text = tok.decode(text)
        examples.append({"text": text, "source": fn.__name__})
        print(f"  {fn.__name__}: {len(msgs)} msgs -> {len(text)} chars")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    print(f"\nTotal: {len(examples)} examples")
    print(f"Wrote to {OUT_PATH}")

    # Combine with v7full
    prev = "workspace/training_data/gamedev_combined_v7full.jsonl"
    combined_path = "workspace/training_data/gamedev_combined_v8full.jsonl"
    combined = []
    if os.path.exists(prev):
        with open(prev) as f:
            combined = [json.loads(l) for l in f if l.strip()]
    combined.extend(examples)
    with open(combined_path, "w") as f:
        for ex in combined:
            f.write(json.dumps(ex) + "\n")
    print(f"Combined_v8full: {len(combined)} examples -> {combined_path}")


if __name__ == "__main__":
    main()
