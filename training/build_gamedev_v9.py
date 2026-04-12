#!/usr/bin/env python3
"""build_gamedev_v9.py -- 4 new SFT examples for gamedev adapter.

Targeting:
  GH-ECS: Entity-Component-System architecture (entity.ts + components.ts + systems.ts + main.ts)
  GH-SAVE: Save/load game state via localStorage
  GH-PROC: Procedural dungeon generation (BSP rooms + corridors)
  GH-MENU: Full game loop with menus (main menu -> gameplay -> game over -> retry)
"""
import json, os, sys
from pathlib import Path
from transformers import AutoTokenizer

sys.path.insert(0, 'training')
from build_v69 import TOOLS

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/gamedev_sft_v9.jsonl"

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


# ── v9-ecs: Entity-Component-System zombie survival ──────────────────────────

def v9_ecs_zombie():
    """ECS pattern: entity.ts + components.ts + systems.ts + main.ts"""
    return [
        sys_msg(),
        u("Build a 2D top-down zombie survival game with an ECS architecture. Use separate files: entity.ts for the entity manager, components.ts for component types (Position, Velocity, Health, Sprite, AI), and systems.ts for game systems (move, render, AI, collision). Spawn waves of zombies."),
        tc("plan_update",
           goal="ECS zombie survival: entity manager + component types + systems + main game loop",
           phases=[
               {"phase": 1, "action": "project_init", "note": "Scaffold game"},
               {"phase": 2, "action": "file_write entity.ts", "note": "Entity: auto-incrementing ID, component Map, EntityManager class"},
               {"phase": 3, "action": "file_write components.ts", "note": "Component types: Position, Velocity, Health, Sprite, AITag, PlayerTag"},
               {"phase": 4, "action": "file_write systems.ts", "note": "Systems: moveSystem, renderSystem, aiSystem (zombies chase player), collisionSystem, spawnSystem (wave counter)"},
               {"phase": 5, "action": "file_write main.ts", "note": "Game loop: create player, run systems, draw HUD, handle game over"},
               {"phase": 6, "action": "shell_exec build"},
               {"phase": 7, "action": "undertow QA + message_result"},
           ]),
        tr("plan_update", "Plan saved."),
        tc("project_init", name="zombie-survival"),
        tr("project_init", "Scaffolded 'zombie-survival'. Write src files."),

        tc("file_write", path="deliverables/zombie-survival/src/entity.ts",
           content="""// entity.ts -- Lightweight ECS entity manager
export type EntityId = number

export class EntityManager {
  private nextId = 1
  private components = new Map<EntityId, Map<string, unknown>>()

  create(): EntityId {
    const id = this.nextId++
    this.components.set(id, new Map())
    return id
  }

  destroy(id: EntityId) {
    this.components.delete(id)
  }

  add<T>(id: EntityId, type: string, data: T): void {
    this.components.get(id)?.set(type, data)
  }

  get<T>(id: EntityId, type: string): T | undefined {
    return this.components.get(id)?.get(type) as T | undefined
  }

  has(id: EntityId, type: string): boolean {
    return this.components.get(id)?.has(type) ?? false
  }

  /** All entities that have all of the given component types. */
  query(...types: string[]): EntityId[] {
    const result: EntityId[] = []
    for (const [id, comps] of this.components) {
      if (types.every(t => comps.has(t))) result.push(id)
    }
    return result
  }

  all(): EntityId[] {
    return [...this.components.keys()]
  }
}
"""),
        tr("file_write", "Written: src/entity.ts"),

        tc("file_write", path="deliverables/zombie-survival/src/components.ts",
           content="""// components.ts -- Component type definitions
export interface Position  { x: number; y: number }
export interface Velocity  { dx: number; dy: number }
export interface Health    { current: number; max: number }
export interface Sprite    { color: string; radius: number }
export interface AIState   { target?: number; speed: number }
export interface PlayerTag {}  // marker component — no data

// Component type name constants (avoids string typos)
export const C = {
  Position: 'Position',
  Velocity: 'Velocity',
  Health:   'Health',
  Sprite:   'Sprite',
  AI:       'AI',
  Player:   'Player',
} as const
"""),
        tr("file_write", "Written: src/components.ts"),

        tc("file_write", path="deliverables/zombie-survival/src/systems.ts",
           content="""// systems.ts -- Game systems (pure functions over EntityManager)
import { EntityManager, EntityId } from './entity'
import { C, Position, Velocity, Health, AIState, Sprite } from './components'

const W = 800, H = 600

export function moveSystem(em: EntityManager, dt: number) {
  for (const id of em.query(C.Position, C.Velocity)) {
    const pos = em.get<Position>(id, C.Position)!
    const vel = em.get<Velocity>(id, C.Velocity)!
    pos.x = Math.max(0, Math.min(W, pos.x + vel.dx * dt))
    pos.y = Math.max(0, Math.min(H, pos.y + vel.dy * dt))
    // Friction
    vel.dx *= 0.85
    vel.dy *= 0.85
  }
}

export function aiSystem(em: EntityManager) {
  const [player] = em.query(C.Player, C.Position)
  if (!player) return
  const pPos = em.get<Position>(player, C.Position)!

  for (const id of em.query(C.AI, C.Position, C.Velocity)) {
    const ai = em.get<AIState>(id, C.AI)!
    const pos = em.get<Position>(id, C.Position)!
    const vel = em.get<Velocity>(id, C.Velocity)!
    const dx = pPos.x - pos.x
    const dy = pPos.y - pos.y
    const len = Math.hypot(dx, dy) || 1
    vel.dx += (dx / len) * ai.speed
    vel.dy += (dy / len) * ai.speed
  }
}

export function collisionSystem(em: EntityManager): boolean {
  const [player] = em.query(C.Player, C.Position, C.Health)
  if (!player) return false
  const pPos = em.get<Position>(player, C.Position)!
  const pHp  = em.get<Health>(player, C.Health)!
  const pSpr = em.get<Sprite>(player, C.Sprite)!

  for (const id of em.query(C.AI, C.Position, C.Sprite)) {
    const zPos = em.get<Position>(id, C.Position)!
    const zSpr = em.get<Sprite>(id, C.Sprite)!
    const dist = Math.hypot(pPos.x - zPos.x, pPos.y - zPos.y)
    if (dist < pSpr.radius + zSpr.radius) {
      pHp.current -= 0.5
      if (pHp.current <= 0) return true  // game over
    }
  }
  return false
}

export function spawnSystem(em: EntityManager, wave: number) {
  const count = 3 + wave * 2
  for (let i = 0; i < count; i++) {
    const side = Math.floor(Math.random() * 4)
    let x = 0, y = 0
    if (side === 0) { x = Math.random() * W; y = -20 }
    else if (side === 1) { x = W + 20; y = Math.random() * H }
    else if (side === 2) { x = Math.random() * W; y = H + 20 }
    else { x = -20; y = Math.random() * H }

    const z = em.create()
    em.add(z, C.Position, { x, y })
    em.add(z, C.Velocity, { dx: 0, dy: 0 })
    em.add(z, C.Health,   { current: 3, max: 3 })
    em.add(z, C.Sprite,   { color: '#22c55e', radius: 14 })
    em.add(z, C.AI,       { speed: 1.5 + wave * 0.3 })
  }
}

export function renderSystem(em: EntityManager, ctx: CanvasRenderingContext2D) {
  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#111'
  ctx.fillRect(0, 0, W, H)

  for (const id of em.query(C.Position, C.Sprite)) {
    const pos = em.get<Position>(id, C.Position)!
    const spr = em.get<Sprite>(id, C.Sprite)!
    ctx.beginPath()
    ctx.arc(pos.x, pos.y, spr.radius, 0, Math.PI * 2)
    ctx.fillStyle = spr.color
    ctx.fill()
  }
}
"""),
        tr("file_write", "Written: src/systems.ts"),

        tc("file_write", path="deliverables/zombie-survival/src/main.ts",
           content="""// main.ts -- ECS zombie survival game loop
import { EntityManager } from './entity'
import { C } from './components'
import { moveSystem, aiSystem, collisionSystem, spawnSystem, renderSystem } from './systems'

const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!
canvas.width = 800; canvas.height = 600

const em = new EntityManager()
const keys = new Set<string>()
window.addEventListener('keydown', e => keys.add(e.code))
window.addEventListener('keyup', e => keys.delete(e.code))

// Create player
const player = em.create()
em.add(player, C.Position, { x: 400, y: 300 })
em.add(player, C.Velocity, { dx: 0, dy: 0 })
em.add(player, C.Health,   { current: 100, max: 100 })
em.add(player, C.Sprite,   { color: '#3b82f6', radius: 16 })
em.add(player, C.Player,   {})

let wave = 0, surviveTime = 0, gameOver = false
spawnSystem(em, wave)

let last = performance.now()
function loop(now: number) {
  const dt = Math.min((now - last) / 16, 3)
  last = now

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.7)'
    ctx.fillRect(0, 0, 800, 600)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 48px monospace'
    ctx.textAlign = 'center'
    ctx.fillText('GAME OVER', 400, 260)
    ctx.font = '24px monospace'
    ctx.fillText(`Survived ${Math.floor(surviveTime)}s — Wave ${wave + 1}`, 400, 320)
    ctx.fillText('Press R to restart', 400, 370)
    if (keys.has('KeyR')) location.reload()
    requestAnimationFrame(loop)
    return
  }

  // Input -> player velocity
  const vel = em.get<{dx:number,dy:number}>(player, C.Velocity)!
  const speed = 5
  if (keys.has('ArrowLeft') || keys.has('KeyA')) vel.dx -= speed
  if (keys.has('ArrowRight') || keys.has('KeyD')) vel.dx += speed
  if (keys.has('ArrowUp') || keys.has('KeyW')) vel.dy -= speed
  if (keys.has('ArrowDown') || keys.has('KeyS')) vel.dy += speed

  aiSystem(em)
  moveSystem(em, dt)
  gameOver = collisionSystem(em)

  surviveTime += dt / 60
  // Next wave every 15 seconds
  if (Math.floor(surviveTime) > 0 && Math.floor(surviveTime) % 15 === 0 &&
      em.query('AI').length < (wave + 1) * 5) {
    wave++
    spawnSystem(em, wave)
  }

  renderSystem(em, ctx)

  // HUD
  const hp = em.get<{current:number, max:number}>(player, C.Health)!
  ctx.fillStyle = '#fff'
  ctx.font = '16px monospace'
  ctx.textAlign = 'left'
  ctx.fillText(`HP: ${Math.ceil(hp.current)} / ${hp.max}`, 16, 28)
  ctx.fillText(`Wave: ${wave + 1}  Time: ${Math.floor(surviveTime)}s`, 16, 50)

  // HP bar
  ctx.fillStyle = '#333'
  ctx.fillRect(16, 56, 200, 12)
  ctx.fillStyle = hp.current > 50 ? '#22c55e' : hp.current > 25 ? '#f59e0b' : '#ef4444'
  ctx.fillRect(16, 56, (hp.current / hp.max) * 200, 12)

  requestAnimationFrame(loop)
}
requestAnimationFrame(loop)
"""),
        tr("file_write", "Written: src/main.ts"),

        tc("shell_exec", command="cd deliverables/zombie-survival && npm run build 2>&1 | tail -5"),
        tr("shell_exec", "✓ built successfully (tsc + vite)"),

        tc("undertow", path="deliverables/zombie-survival/dist/index.html"),
        tr("undertow", "[screenshot: dark canvas, blue player circle in center, green zombie circles approaching from edges, HP bar top-left, wave counter]"),

        tc("message_result", text="Built zombie-survival — ECS architecture: EntityManager (entity.ts), component types (components.ts), systems (systems.ts: move/AI/collision/spawn/render), game loop (main.ts). WASD moves the player, zombies chase. Wave 2+ spawns faster enemies. Press R to restart."),
        tr("message_result", "Delivered."),
    ]


# ── v9-save: platformer with save/load via localStorage ─────────────────────

def v9_save_platformer():
    """Save/load game state: saveState.ts + game logic + localStorage persistence."""
    return [
        sys_msg(),
        u("Build a 2D platformer with collectible coins and save/load game state using localStorage. The player should be able to press P to save progress (coins collected, current level) and S to save + R to restore on page reload."),

        tc("project_init", name="platformer-save"),
        tr("project_init", "Scaffolded 'platformer-save'. Write src files."),

        tc("file_write", path="deliverables/platformer-save/src/saveState.ts",
           content="""// saveState.ts -- localStorage save/load for game state
const SAVE_KEY = 'platformer_save'

export interface SaveData {
  coins: number
  level: number
  playerX: number
  playerY: number
  timestamp: number
}

export function saveGame(data: Omit<SaveData, 'timestamp'>): void {
  const save: SaveData = { ...data, timestamp: Date.now() }
  localStorage.setItem(SAVE_KEY, JSON.stringify(save))
}

export function loadGame(): SaveData | null {
  const raw = localStorage.getItem(SAVE_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as SaveData }
  catch { return null }
}

export function deleteSave(): void {
  localStorage.removeItem(SAVE_KEY)
}

export function hasSave(): boolean {
  return localStorage.getItem(SAVE_KEY) !== null
}
"""),
        tr("file_write", "Written: src/saveState.ts"),

        tc("file_write", path="deliverables/platformer-save/src/main.ts",
           content="""// main.ts -- 2D platformer with coin collection + save/load
import { saveGame, loadGame, hasSave } from './saveState'

const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!
canvas.width = 800; canvas.height = 500

// Game state
let px = 100, py = 380, vx = 0, vy = 0
let coins = 0, level = 1, onGround = false
const keys = new Set<string>()
window.addEventListener('keydown', e => keys.add(e.code))
window.addEventListener('keyup', e => keys.delete(e.code))

// Platforms: [x, y, w, h]
const platforms = [
  [0, 460, 800, 40],   // ground
  [100, 360, 150, 16], [350, 280, 150, 16], [560, 360, 150, 16],
  [200, 200, 120, 16], [500, 180, 120, 16],
]

// Coins: {x, y, collected}
const coinList = [
  {x:160, y:340}, {x:380, y:260}, {x:600, y:340},
  {x:240, y:180}, {x:540, y:160}, {x:700, y:440},
].map(c => ({...c, collected: false}))

// Load save on startup
const save = loadGame()
if (save) {
  px = save.playerX; py = save.playerY
  coins = save.coins; level = save.level
  // Mark already-collected coins (simple: by index for now)
  coinList.forEach((c, i) => { if (i < coins) c.collected = true })
}

let notification = '', notifyTimer = 0

function showNotify(msg: string) {
  notification = msg; notifyTimer = 180
}

function loop() {
  // Input
  if (keys.has('ArrowLeft') || keys.has('KeyA')) vx -= 1
  if (keys.has('ArrowRight') || keys.has('KeyD')) vx += 1
  if ((keys.has('ArrowUp') || keys.has('Space') || keys.has('KeyW')) && onGround) {
    vy = -14; onGround = false
  }

  // Save/load
  if (keys.has('KeyP')) {
    saveGame({ coins, level, playerX: px, playerY: py })
    showNotify('Game saved! (P)')
    keys.delete('KeyP')
  }

  // Physics
  vy += 0.6
  vx *= 0.8
  px += vx; py += vy
  onGround = false

  // Platform collision
  for (const [bx, by, bw, bh] of platforms) {
    if (px+12 > bx && px-12 < bx+bw && py+20 > by && py-20 < by+bh) {
      if (vy > 0 && py < by+bh/2) {
        py = by - 20; vy = 0; onGround = true
      }
    }
  }

  // Bounds
  if (px < 12) px = 12
  if (px > 788) px = 788
  if (py > 600) { py = 380; px = 100; showNotify('Fell! Respawning...') }

  // Coin collection
  for (const c of coinList) {
    if (!c.collected && Math.hypot(px - c.x, py - c.y) < 20) {
      c.collected = true; coins++
      if (coins === coinList.length) {
        level++; showNotify(`Level ${level}! All coins collected!`)
        coinList.forEach(c => c.collected = false); coins = 0
      }
    }
  }

  // Render
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0, 0, 800, 500)

  // Platforms
  ctx.fillStyle = '#4a4a8a'
  for (const [bx, by, bw, bh] of platforms) {
    ctx.fillRect(bx, by, bw, bh)
    ctx.fillStyle = '#5a5a9a'; ctx.fillRect(bx, by, bw, 4); ctx.fillStyle = '#4a4a8a'
  }

  // Coins
  for (const c of coinList) {
    if (c.collected) continue
    ctx.beginPath(); ctx.arc(c.x, c.y, 8, 0, Math.PI*2)
    ctx.fillStyle = '#fbbf24'; ctx.fill()
    ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 2; ctx.stroke()
  }

  // Player
  ctx.fillStyle = '#3b82f6'
  ctx.fillRect(px-12, py-20, 24, 20)
  ctx.fillStyle = '#1d4ed8'
  ctx.fillRect(px-10, py-20, 24, 6)

  // HUD
  ctx.fillStyle = '#fff'; ctx.font = '16px monospace'; ctx.textAlign = 'left'
  ctx.fillText(`Coins: ${coins}/${coinList.length}  Level: ${level}`, 16, 28)
  ctx.fillText('WASD/Arrows: Move  Space: Jump  P: Save', 16, 50)
  if (hasSave()) {
    ctx.fillStyle = '#86efac'; ctx.fillText('● Saved', 700, 28)
  }

  // Notification
  if (notifyTimer > 0) {
    notifyTimer--
    ctx.globalAlpha = Math.min(1, notifyTimer / 30)
    ctx.fillStyle = '#fbbf24'; ctx.font = 'bold 20px monospace'; ctx.textAlign = 'center'
    ctx.fillText(notification, 400, 80)
    ctx.globalAlpha = 1; ctx.textAlign = 'left'
  }

  requestAnimationFrame(loop)
}
requestAnimationFrame(loop)
"""),
        tr("file_write", "Written: src/main.ts"),

        tc("shell_exec", command="cd deliverables/platformer-save && npm run build 2>&1 | tail -5"),
        tr("shell_exec", "✓ built successfully"),

        tc("undertow", path="deliverables/platformer-save/dist/index.html"),
        tr("undertow", "[screenshot: dark purple platformer, blue player sprite, yellow coins on platforms, HUD shows Coins 0/6 Level 1, 'Saved' indicator top-right]"),

        tc("message_result", text="Built platformer-save — 2D platformer with localStorage save/load. saveState.ts exports saveGame/loadGame/hasSave. Press P to save, state persists across page reloads. Collect all 6 coins to advance levels. WASD + Space to play."),
        tr("message_result", "Delivered."),
    ]


# ── v9-proc: Procedural dungeon with BSP rooms ──────────────────────────────

def v9_proc_dungeon():
    """Procedural dungeon generation with BSP rooms and corridors."""
    return [
        sys_msg(),
        u("Build a top-down dungeon explorer with procedurally generated rooms connected by corridors. Use a simple BSP (binary space partitioning) algorithm. The player explores a new dungeon each time. Include fog of war."),

        tc("plan_update",
           goal="Procedural dungeon: BSP room generation + fog of war + top-down exploration",
           phases=[
               {"phase": 1, "action": "project_init"},
               {"phase": 2, "action": "file_write dungeon.ts", "note": "Tile map: WALL/FLOOR/DOOR + BSP generator + room connector"},
               {"phase": 3, "action": "file_write main.ts", "note": "Player, torch radius fog, minimap, camera scroll"},
               {"phase": 4, "action": "shell_exec build"},
               {"phase": 5, "action": "undertow + message_result"},
           ]),
        tr("plan_update", "Plan saved."),

        tc("project_init", name="proc-dungeon"),
        tr("project_init", "Scaffolded 'proc-dungeon'. Write src files."),

        tc("file_write", path="deliverables/proc-dungeon/src/dungeon.ts",
           content="""// dungeon.ts -- BSP procedural dungeon generation
export const TILE = { WALL: 0, FLOOR: 1, DOOR: 2 } as const
export type TileType = typeof TILE[keyof typeof TILE]
export interface Room { x: number; y: number; w: number; h: number }

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function center(r: Room): [number, number] {
  return [Math.floor(r.x + r.w / 2), Math.floor(r.y + r.h / 2)]
}

function carveRoom(tiles: TileType[][], r: Room) {
  for (let y = r.y; y < r.y + r.h; y++)
    for (let x = r.x; x < r.x + r.w; x++)
      tiles[y][x] = TILE.FLOOR
}

function carveCorridor(tiles: TileType[][], ax: number, ay: number, bx: number, by: number) {
  // L-shaped corridor: horizontal then vertical
  const x0 = Math.min(ax, bx), x1 = Math.max(ax, bx)
  const y0 = Math.min(ay, by), y1 = Math.max(ay, by)
  for (let x = x0; x <= x1; x++) tiles[ay][x] = TILE.FLOOR
  for (let y = y0; y <= y1; y++) tiles[y][bx] = TILE.FLOOR
}

/** BSP dungeon: split grid recursively, place room in each leaf, connect siblings. */
export function generateDungeon(cols: number, rows: number): { tiles: TileType[][], rooms: Room[], start: [number,number] } {
  // Init all walls
  const tiles: TileType[][] = Array.from({length: rows}, () => Array(cols).fill(TILE.WALL))
  const rooms: Room[] = []

  interface BSPNode { x: number; y: number; w: number; h: number; room?: Room; left?: BSPNode; right?: BSPNode }

  function split(node: BSPNode, depth: number): void {
    if (depth === 0 || node.w < 10 || node.h < 10) {
      // Leaf: place a room
      const rw = randInt(Math.max(4, node.w - 4), node.w - 2)
      const rh = randInt(Math.max(4, node.h - 4), node.h - 2)
      const rx = node.x + randInt(1, node.w - rw - 1)
      const ry = node.y + randInt(1, node.h - rh - 1)
      node.room = { x: rx, y: ry, w: rw, h: rh }
      carveRoom(tiles, node.room)
      rooms.push(node.room)
      return
    }

    const splitH = node.w > node.h
    if (splitH) {
      const mid = randInt(Math.floor(node.w * 0.4), Math.floor(node.w * 0.6))
      node.left  = { x: node.x, y: node.y, w: mid, h: node.h }
      node.right = { x: node.x + mid, y: node.y, w: node.w - mid, h: node.h }
    } else {
      const mid = randInt(Math.floor(node.h * 0.4), Math.floor(node.h * 0.6))
      node.left  = { x: node.x, y: node.y, w: node.w, h: mid }
      node.right = { x: node.x, y: node.y + mid, w: node.w, h: node.h - mid }
    }
    split(node.left, depth - 1)
    split(node.right, depth - 1)

    // Connect sibling rooms
    function getRoom(n: BSPNode): Room | undefined { return n.room ?? n.left && getRoom(n.left) }
    const rA = getRoom(node.left); const rB = getRoom(node.right)
    if (rA && rB) {
      const [ax, ay] = center(rA); const [bx, by] = center(rB)
      carveCorridor(tiles, ax, ay, bx, by)
    }
  }

  split({ x: 1, y: 1, w: cols - 2, h: rows - 2 }, 4)

  const start = center(rooms[0])
  return { tiles, rooms, start }
}
"""),
        tr("file_write", "Written: src/dungeon.ts"),

        tc("file_write", path="deliverables/proc-dungeon/src/main.ts",
           content="""// main.ts -- Dungeon explorer with fog of war and minimap
import { generateDungeon, TILE } from './dungeon'

const COLS = 60, ROWS = 40, TS = 16  // tile size in pixels
const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!
canvas.width = 800; canvas.height = 600

const { tiles, start } = generateDungeon(COLS, ROWS)
const fog = Array.from({length: ROWS}, () => Array(COLS).fill(false))
const visible = Array.from({length: ROWS}, () => Array(COLS).fill(false))

let [px, py] = start  // player tile position
let steps = 0

const keys = new Set<string>()
window.addEventListener('keydown', e => keys.add(e.code))
window.addEventListener('keyup', e => keys.delete(e.code))

const TORCH_RADIUS = 6

function updateFog() {
  visible.forEach(r => r.fill(false))
  for (let dy = -TORCH_RADIUS; dy <= TORCH_RADIUS; dy++) {
    for (let dx = -TORCH_RADIUS; dx <= TORCH_RADIUS; dx++) {
      if (dx*dx + dy*dy > TORCH_RADIUS*TORCH_RADIUS) continue
      const nx = px+dx, ny = py+dy
      if (nx < 0 || ny < 0 || nx >= COLS || ny >= ROWS) continue
      visible[ny][nx] = true; fog[ny][nx] = true
    }
  }
}

let lastMove = 0
function tryMove(dx: number, dy: number) {
  const nx = px + dx, ny = py + dy
  if (nx < 0 || ny < 0 || nx >= COLS || ny >= ROWS) return
  if (tiles[ny][nx] === TILE.WALL) return
  px = nx; py = ny; steps++
}

updateFog()

function loop(now: number) {
  if (now - lastMove > 120) {
    if (keys.has('ArrowLeft') || keys.has('KeyA'))  { tryMove(-1, 0); lastMove = now; updateFog() }
    if (keys.has('ArrowRight') || keys.has('KeyD')) { tryMove(1, 0);  lastMove = now; updateFog() }
    if (keys.has('ArrowUp') || keys.has('KeyW'))    { tryMove(0, -1); lastMove = now; updateFog() }
    if (keys.has('ArrowDown') || keys.has('KeyS'))  { tryMove(0, 1);  lastMove = now; updateFog() }
  }

  // Camera: center on player
  const camX = Math.max(0, Math.min(COLS * TS - 800, px * TS - 400))
  const camY = Math.max(0, Math.min(ROWS * TS - 600, py * TS - 300))

  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 800, 600)

  const startCol = Math.floor(camX / TS)
  const endCol   = Math.min(COLS, startCol + Math.ceil(800/TS) + 1)
  const startRow = Math.floor(camY / TS)
  const endRow   = Math.min(ROWS, startRow + Math.ceil(600/TS) + 1)

  for (let row = startRow; row < endRow; row++) {
    for (let col = startCol; col < endCol; col++) {
      const sx = col * TS - camX, sy = row * TS - camY
      if (!fog[row][col]) continue
      const bright = visible[row][col]
      const tile = tiles[row][col]
      if (tile === TILE.WALL) {
        ctx.fillStyle = bright ? '#4b5563' : '#1f2937'
      } else {
        ctx.fillStyle = bright ? '#d6d3d1' : '#78716c'
      }
      ctx.fillRect(sx, sy, TS, TS)
    }
  }

  // Player
  ctx.fillStyle = '#3b82f6'
  ctx.fillRect(px * TS - camX + 2, py * TS - camY + 2, TS-4, TS-4)

  // HUD
  ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, 800, 40)
  ctx.fillStyle = '#fff'; ctx.font = '14px monospace'; ctx.textAlign = 'left'
  ctx.fillText(`Steps: ${steps}  Position: (${px},${py})  WASD: Move  R: New dungeon`, 16, 26)
  if (keys.has('KeyR')) location.reload()

  // Minimap (bottom-right, 120x80)
  const mmX = 666, mmY = 508, mmW = 120, mmH = 80
  ctx.fillStyle = '#000'; ctx.fillRect(mmX, mmY, mmW, mmH)
  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) {
      if (!fog[row][col]) continue
      const sx = mmX + Math.floor(col * mmW / COLS)
      const sy = mmY + Math.floor(row * mmH / ROWS)
      ctx.fillStyle = tiles[row][col] === TILE.FLOOR ? '#a8a29e' : '#292524'
      ctx.fillRect(sx, sy, 2, 2)
    }
  }
  // Player dot on minimap
  ctx.fillStyle = '#3b82f6'
  ctx.fillRect(mmX + Math.floor(px * mmW / COLS), mmY + Math.floor(py * mmH / ROWS), 3, 3)

  requestAnimationFrame(loop)
}
requestAnimationFrame(loop)
"""),
        tr("file_write", "Written: src/main.ts"),

        tc("shell_exec", command="cd deliverables/proc-dungeon && npm run build 2>&1 | tail -5"),
        tr("shell_exec", "✓ built successfully"),

        tc("undertow", path="deliverables/proc-dungeon/dist/index.html"),
        tr("undertow", "[screenshot: dark dungeon top-down view, lit tiles within torch radius, fog of war hiding unexplored areas, blue player dot, small minimap bottom-right showing explored rooms]"),

        tc("message_result", text="Built proc-dungeon — BSP procedural generation (dungeon.ts): split grid recursively, place rooms in leaves, connect siblings with L-shaped corridors. Main loop: fog of war (torch radius 6), camera centering, minimap. WASD to explore, R for a new dungeon."),
        tr("message_result", "Delivered."),
    ]


# ── v9-menu: game with full menu flow ───────────────────────────────────────

def v9_menu_breakout():
    """Full menu flow: main menu -> gameplay -> pause -> game over -> retry."""
    return [
        sys_msg(),
        u("Build a Breakout clone with a proper game flow: main menu with instructions, gameplay, pause (Esc), and game over screen with score and retry. Make it visually polished."),

        tc("project_init", name="breakout"),
        tr("project_init", "Scaffolded 'breakout'. Write src/main.ts."),

        tc("file_write", path="deliverables/breakout/src/main.ts",
           content="""// main.ts -- Breakout with full game flow: menu -> game -> pause -> game over
const W = 800, H = 600
const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!
canvas.width = W; canvas.height = H

type Scene = 'menu' | 'game' | 'pause' | 'gameover'
let scene: Scene = 'menu'
let score = 0, lives = 3, hiScore = parseInt(localStorage.getItem('breakout_hi') || '0')

// Paddle
const pad = { x: 350, y: 560, w: 100, h: 12, speed: 6 }
// Ball
const ball = { x: 400, y: 540, r: 8, vx: 3, vy: -4 }
// Bricks: 10 cols x 6 rows
const BRICK_COLS = 10, BRICK_ROWS = 6, BW = 72, BH = 20, BGAP = 4
const COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6']
let bricks: { alive: boolean; color: string }[][] = []

function initBricks() {
  bricks = Array.from({length: BRICK_ROWS}, (_, row) =>
    Array.from({length: BRICK_COLS}, () => ({ alive: true, color: COLORS[row % COLORS.length] }))
  )
}

function resetBall() {
  ball.x = pad.x + pad.w/2; ball.y = pad.y - 20
  ball.vx = (Math.random() > 0.5 ? 1 : -1) * (3 + score/200)
  ball.vy = -(4 + score/200)
}

initBricks(); resetBall()

const keys = new Set<string>()
window.addEventListener('keydown', e => {
  if (e.code === 'Escape' && scene === 'game') { scene = 'pause'; return }
  if (e.code === 'Escape' && scene === 'pause') { scene = 'game'; return }
  keys.add(e.code)
})
window.addEventListener('keyup', e => keys.delete(e.code))

function drawText(text: string, x: number, y: number, size=24, color='#fff', align: CanvasTextAlign='center') {
  ctx.font = `bold ${size}px monospace`; ctx.fillStyle = color
  ctx.textAlign = align; ctx.fillText(text, x, y)
}

function drawMenu() {
  ctx.fillStyle = '#0f0f1a'; ctx.fillRect(0, 0, W, H)
  // Animated title
  ctx.save()
  const t = Date.now()/1000
  ctx.shadowColor = '#3b82f6'; ctx.shadowBlur = 20 + Math.sin(t*2)*10
  drawText('BREAKOUT', W/2, 180, 72, '#3b82f6')
  ctx.restore()

  drawText('Press SPACE or ENTER to play', W/2, 280, 22, '#94a3b8')
  drawText('← → Arrow keys: Move paddle', W/2, 330, 18, '#64748b')
  drawText('ESC: Pause', W/2, 360, 18, '#64748b')
  if (hiScore > 0) drawText(`High Score: ${hiScore}`, W/2, 420, 20, '#fbbf24')

  if (keys.has('Space') || keys.has('Enter')) { scene = 'game'; score = 0; lives = 3; initBricks(); resetBall() }
}

function drawGame() {
  ctx.fillStyle = '#0f0f1a'; ctx.fillRect(0, 0, W, H)

  // Paddle
  const gr = ctx.createLinearGradient(pad.x, pad.y, pad.x, pad.y + pad.h)
  gr.addColorStop(0, '#60a5fa'); gr.addColorStop(1, '#2563eb')
  ctx.fillStyle = gr
  ctx.beginPath(); ctx.roundRect(pad.x, pad.y, pad.w, pad.h, 6); ctx.fill()

  // Ball
  ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI*2)
  ctx.fillStyle = '#fff'; ctx.fill()
  ctx.shadowColor = '#60a5fa'; ctx.shadowBlur = 12; ctx.fill(); ctx.shadowBlur = 0

  // Bricks
  const bOx = (W - (BRICK_COLS*(BW+BGAP)-BGAP)) / 2
  for (let row = 0; row < BRICK_ROWS; row++) {
    for (let col = 0; col < BRICK_COLS; col++) {
      if (!bricks[row][col].alive) continue
      const bx = bOx + col*(BW+BGAP), by = 60 + row*(BH+BGAP)
      ctx.fillStyle = bricks[row][col].color
      ctx.beginPath(); ctx.roundRect(bx, by, BW, BH, 4); ctx.fill()
      ctx.fillStyle = 'rgba(255,255,255,0.3)'
      ctx.fillRect(bx+2, by+2, BW-4, 5)
    }
  }

  // Physics
  if (keys.has('ArrowLeft') || keys.has('KeyA')) pad.x = Math.max(0, pad.x - pad.speed)
  if (keys.has('ArrowRight') || keys.has('KeyD')) pad.x = Math.min(W - pad.w, pad.x + pad.speed)

  ball.x += ball.vx; ball.y += ball.vy

  if (ball.x - ball.r < 0)   { ball.x = ball.r;   ball.vx = Math.abs(ball.vx) }
  if (ball.x + ball.r > W)   { ball.x = W-ball.r; ball.vx = -Math.abs(ball.vx) }
  if (ball.y - ball.r < 0)   { ball.y = ball.r;   ball.vy = Math.abs(ball.vy) }

  // Paddle hit
  if (ball.y + ball.r >= pad.y && ball.y - ball.r <= pad.y + pad.h &&
      ball.x >= pad.x && ball.x <= pad.x + pad.w && ball.vy > 0) {
    const offset = (ball.x - (pad.x + pad.w/2)) / (pad.w/2)
    ball.vx = offset * 6; ball.vy = -Math.abs(ball.vy)
    ball.y = pad.y - ball.r - 1
  }

  // Ball out
  if (ball.y + ball.r > H + 30) {
    lives--
    if (lives <= 0) { if(score > hiScore){hiScore=score;localStorage.setItem('breakout_hi',''+hiScore)} scene = 'gameover' }
    else resetBall()
  }

  // Brick hit
  const bOx2 = (W - (BRICK_COLS*(BW+BGAP)-BGAP)) / 2
  for (let row = 0; row < BRICK_ROWS; row++) {
    for (let col = 0; col < BRICK_COLS; col++) {
      if (!bricks[row][col].alive) continue
      const bx = bOx2 + col*(BW+BGAP), by = 60 + row*(BH+BGAP)
      if (ball.x+ball.r > bx && ball.x-ball.r < bx+BW && ball.y+ball.r > by && ball.y-ball.r < by+BH) {
        bricks[row][col].alive = false; score += 10 + row*5; ball.vy *= -1
      }
    }
  }

  // All bricks cleared
  if (bricks.every(row => row.every(b => !b.alive))) {
    score += 500; initBricks(); ball.vx *= 1.1; ball.vy *= 1.1
  }

  // HUD
  drawText(`Score: ${score}`, 80, 30, 18, '#94a3b8', 'left')
  drawText(`Hi: ${hiScore}`, W/2, 30, 18, '#fbbf24')
  drawText(`Lives: ${'● '.repeat(lives).trim()}`, W-16, 30, 18, '#ef4444', 'right')
}

function drawPause() {
  drawGame()
  ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, W, H)
  drawText('PAUSED', W/2, H/2 - 40, 56, '#fff')
  drawText('Press ESC to resume', W/2, H/2 + 20, 22, '#94a3b8')
}

function drawGameOver() {
  ctx.fillStyle = '#0f0f1a'; ctx.fillRect(0, 0, W, H)
  drawText('GAME OVER', W/2, 220, 64, '#ef4444')
  drawText(`Score: ${score}`, W/2, 300, 28, '#fff')
  if (score >= hiScore && score > 0) drawText('NEW HIGH SCORE!', W/2, 340, 22, '#fbbf24')
  drawText('Press SPACE to play again', W/2, 420, 22, '#94a3b8')
  if (keys.has('Space') || keys.has('Enter')) {
    scene='game'; score=0; lives=3; initBricks(); resetBall(); pad.x=350; pad.speed=6
  }
}

function loop() {
  if (scene === 'menu') drawMenu()
  else if (scene === 'game') drawGame()
  else if (scene === 'pause') drawPause()
  else if (scene === 'gameover') drawGameOver()
  requestAnimationFrame(loop)
}
requestAnimationFrame(loop)
"""),
        tr("file_write", "Written: src/main.ts"),

        tc("shell_exec", command="cd deliverables/breakout && npm run build 2>&1 | tail -5"),
        tr("shell_exec", "✓ built successfully"),

        tc("undertow", path="deliverables/breakout/dist/index.html"),
        tr("undertow", "[screenshot: main menu screen 'BREAKOUT' in blue glowing text, 'Press SPACE to play' subtitle, clean dark background]"),

        tc("message_result", text="Built breakout — full game flow: menu → gameplay → pause (Esc) → game over → retry. Polished rendering: gradient paddle, glowing ball, rounded bricks with highlight, score persistence via localStorage. Increasing difficulty as score grows."),
        tr("message_result", "Delivered."),
    ]


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading tokenizer ({MODEL})...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    print("Tokenizer loaded.")

    examples = [
        ("v9_ecs_zombie",        v9_ecs_zombie),
        ("v9_save_platformer",   v9_save_platformer),
        ("v9_proc_dungeon",      v9_proc_dungeon),
        ("v9_menu_breakout",     v9_menu_breakout),
    ]

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(OUT_PATH, "w") as f:
        for source, fn in examples:
            messages = fn()
            text = tokenizer.apply_chat_template(
                messages, tools=TOOLS, tokenize=False, add_generation_prompt=False
            )
            record = {"text": text, "source": source}
            f.write(json.dumps(record) + "\n")
            total += 1
            print(f"  wrote {source} ({len(text)} chars)")

    print(f"\nWrote {total} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
