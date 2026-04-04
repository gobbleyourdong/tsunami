/**
 * SIGMA ARENA — Top-down wave-based arena shooter.
 * Demonstrates every Tsunami Engine module.
 */

import { Game } from '@engine/game/game'
import { KeyboardInput } from '@engine/input/keyboard'
import { ActionMap } from '@engine/input/action_map'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { CheckpointSystem, MemorySaveBackend } from '@engine/systems/checkpoint'
import { DifficultyManager } from '@engine/flow/difficulty'
import { SceneManager } from '@engine/flow/scene_manager'
import { GameFlow } from '@engine/flow/game_flow'
import { MenuSystem } from '@engine/flow/menu'
import { DialogSystem } from '@engine/flow/dialog'
import { TutorialSystem } from '@engine/flow/tutorial'
import { WaveManager } from './game/waves'
import { PlayerController } from './game/player'
import { EnemyManager } from './game/enemies'
import { ProjectileManager } from './game/projectiles'
import { PickupManager } from './game/pickups'
import { ArenaRenderer } from './game/renderer'
import { HUD } from './game/hud'
import { ProceduralAudio } from './game/audio'
import type { GameState } from './game/state'

// --- Game State ---
const state: GameState = {
  score: new ScoreSystem(2),
  playerHealth: new HealthSystem(100),
  difficulty: new DifficultyManager(),
  checkpoint: new CheckpointSystem(new MemorySaveBackend()),
  wave: 0,
  maxWave: 10,
  paused: false,
  gameOver: false,
  phase: 'title',
}

// --- Input ---
const keyboard = new KeyboardInput()
const actions = new ActionMap()
  .define('moveUp', { type: 'key', code: 'KeyW' }, { type: 'key', code: 'ArrowUp' })
  .define('moveDown', { type: 'key', code: 'KeyS' }, { type: 'key', code: 'ArrowDown' })
  .define('moveLeft', { type: 'key', code: 'KeyA' }, { type: 'key', code: 'ArrowLeft' })
  .define('moveRight', { type: 'key', code: 'KeyD' }, { type: 'key', code: 'ArrowRight' })
  .define('shoot', { type: 'key', code: 'Space' })
  .define('pause', { type: 'key', code: 'Escape' })
  .define('confirm', { type: 'key', code: 'Enter' })

keyboard.bind()

// --- Scene Manager + Flow ---
const sceneManager = new SceneManager()
const flow = new GameFlow(sceneManager)

// --- Subsystems (will be initialized per-scene) ---
let player: PlayerController | null = null
let enemies: EnemyManager | null = null
let projectiles: ProjectileManager | null = null
let pickups: PickupManager | null = null
let waves: WaveManager | null = null
let renderer: ArenaRenderer | null = null
let hud: HUD | null = null
let audio: ProceduralAudio | null = null
let tutorial: TutorialSystem | null = null

// --- Scenes ---

sceneManager.add({
  name: 'title',
  enter() {
    state.phase = 'title'
    hud?.showTitle(state.score.highScore)
  },
  update(dt) {
    if (keyboard.justPressed('Enter') || keyboard.justPressed('Space')) {
      sceneManager.goto('tutorial', { type: 'fade', duration: 400 })
    }
  },
})

sceneManager.add({
  name: 'tutorial',
  enter() {
    state.phase = 'tutorial'
    tutorial = new TutorialSystem()
    tutorial.onComplete = () => {
      sceneManager.goto('arena', { type: 'fade', duration: 400 })
    }
    tutorial.start([
      { id: 'move', message: 'WASD to move', waitForAction: 'move' },
      { id: 'shoot', message: 'SPACE to shoot', waitForAction: 'shoot' },
      { id: 'ready', message: 'Survive the arena!', duration: 2 },
    ])
    hud?.showTutorial(tutorial)
  },
  update(dt) {
    if (!tutorial) return
    // Detect actions for tutorial gates
    const moved = keyboard.isDown('KeyW') || keyboard.isDown('KeyA') ||
                  keyboard.isDown('KeyS') || keyboard.isDown('KeyD')
    if (moved) tutorial.notifyAction('move')
    if (keyboard.justPressed('Space')) tutorial.notifyAction('shoot')
    tutorial.update(dt)
  },
})

sceneManager.add({
  name: 'arena',
  enter() {
    state.phase = 'arena'
    state.gameOver = false
    state.wave = 0
    state.score.reset()
    state.playerHealth = new HealthSystem(100)
    state.difficulty.setLevel(0)

    player = new PlayerController(state, keyboard, actions)
    enemies = new EnemyManager(state)
    projectiles = new ProjectileManager()
    pickups = new PickupManager(state)
    waves = new WaveManager(state, enemies)

    state.playerHealth.onDeath = () => {
      state.gameOver = true
      setTimeout(() => {
        sceneManager.goto('gameover', { type: 'fade', duration: 600 })
      }, 1000)
    }

    // Start wave 1
    waves.startNextWave()

    // Checkpoint
    state.checkpoint.register('score', {
      serialize: () => state.score.serialize(),
      deserialize: (d) => state.score.deserialize(d as any),
    })
    state.checkpoint.register('health', {
      serialize: () => state.playerHealth.serialize(),
      deserialize: (d) => state.playerHealth.deserialize(d as any),
    })

    hud?.showArena()
    audio?.playMusic()
  },
  update(dt) {
    if (state.paused || state.gameOver) return

    player?.update(dt, projectiles!)
    enemies?.update(dt, player!, projectiles!)
    projectiles?.update(dt, enemies!, player!, pickups!)
    pickups?.update(dt, player!)
    waves?.update(dt)
    state.score.update(dt)

    // Renderer would draw here
    renderer?.render(dt, player!, enemies!, projectiles!, pickups!)
  },
  exit() {
    audio?.stopMusic()
  },
})

sceneManager.add({
  name: 'gameover',
  enter() {
    state.phase = 'gameover'
    hud?.showGameOver(state.score.score, state.wave, state.score.maxCombo)
  },
  update(dt) {
    if (keyboard.justPressed('Enter') || keyboard.justPressed('Space')) {
      sceneManager.goto('title', { type: 'fade', duration: 400 })
    }
  },
})

// --- Flow ---
flow.setFlow([
  { scene: 'title' },
  { scene: 'tutorial' },
  { scene: 'arena' },
  { scene: 'gameover' },
])

// --- Boot ---
async function boot() {
  const canvas = document.getElementById('game') as HTMLCanvasElement
  renderer = new ArenaRenderer(canvas)
  hud = new HUD(document.getElementById('hud')!)
  audio = new ProceduralAudio()

  await sceneManager.goto('title')

  // Main loop
  let lastTime = performance.now()
  function tick(now: number) {
    const dt = Math.min((now - lastTime) / 1000, 0.1)
    lastTime = now

    // Pause toggle
    if (keyboard.justPressed('Escape') && state.phase === 'arena') {
      state.paused = !state.paused
      hud?.showPause(state.paused)
    }

    sceneManager.update(dt)
    hud?.update(dt, state)
    keyboard.update()

    requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

boot()
