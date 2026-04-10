/**
 * TODO: Replace with your game.
 *
 * Engine API:
 *   Game         — top-level: wires renderer, physics, input, scenes, frame loop
 *   SceneManager — add scenes, transition between them (fade, cut)
 *   SceneBuilder — fluent API: .camera() .light() .ground() .spawn() .onUpdate()
 *   KeyboardInput, ActionMap — input binding (WASD, Space, etc.)
 *   ScoreSystem, HealthSystem, CheckpointSystem — gameplay primitives
 *   DifficultyManager — S-curve difficulty scaling
 *   MenuSystem, DialogSystem, TutorialSystem — game flow
 *   PhysicsWorld — GJK collision, raycasts, rigidbodies
 *   ParticleSystem — VFX presets (fire, smoke, sparks, blood, magic)
 *   BehaviorTree, FSM, Pathfinding — AI
 *
 * Pattern:
 *   1. Create Game({ mode: '2d' | '3d' })
 *   2. Define scenes with game.scene('name')
 *   3. Spawn entities, set camera, add lights
 *   4. Wire input → actions
 *   5. game.start()
 */

import { Game } from '@engine/game/game'
import { KeyboardInput } from '@engine/input/keyboard'
import { ActionMap } from '@engine/input/action_map'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'

// --- Config ---
const game = new Game({ mode: '2d', width: 800, height: 600 })

const keyboard = new KeyboardInput()
const actions = new ActionMap()
  .define('left',  { type: 'key', code: 'KeyA' }, { type: 'key', code: 'ArrowLeft' })
  .define('right', { type: 'key', code: 'KeyD' }, { type: 'key', code: 'ArrowRight' })
  .define('up',    { type: 'key', code: 'KeyW' }, { type: 'key', code: 'ArrowUp' })
  .define('fire',  { type: 'key', code: 'Space' })

keyboard.bind()

const score = new ScoreSystem()
const health = new HealthSystem(3)

// --- Game Scene ---
const level = game.scene('level')
level.camera({ position: [0, 0, 10] })

// TODO: spawn entities, wire update logic
// level.spawn('player', { position: [400, 550, 0] })
// level.onUpdate((dt) => { ... })

game.setFlow([{ scene: 'level' }])
game.start()
