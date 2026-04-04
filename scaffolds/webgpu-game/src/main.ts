/**
 * Game entry point — uses the Tsunami Engine.
 *
 * The engine provides:
 *   - Game: top-level orchestrator (renderer, physics, audio, input, scenes)
 *   - SceneBuilder: fluent API for constructing levels
 *   - Physics: custom GJK/EPA solver, rigidbodies, raycasting
 *   - AI: FSM, behavior trees, NavMesh pathfinding
 *   - Animation: skeleton, clips, state machine, IK, GPU skinning
 *   - Audio: Web Audio API, spatial audio, sound pooling
 *   - Input: keyboard, gamepad, touch, pointer lock, combos
 *   - VFX: GPU particles, shader graph, post-processing
 *   - Flow: scene manager, menus, dialog, tutorial, difficulty
 *   - Systems: health, inventory, checkpoint/save, score
 *
 * Usage:
 *   const game = new Game({ mode: '3d' })
 *   const level = game.scene('level1')
 *   level.spawn('player', { mesh: 'capsule', position: [0, 1, 0], controller: 'fps' })
 *   level.spawn('enemy', { mesh: 'sphere', position: [5, 1, 0], ai: 'patrol' })
 *   level.ground(50, 'grid')
 *   level.light('directional', { direction: [1, -1, 0.5] })
 *   game.start()
 */

import { Game } from 'tsunami-engine'

// Create game
const game = new Game({
  mode: '3d',
  title: 'My Game',
  width: window.innerWidth,
  height: window.innerHeight,
})

// Build the main scene
const level = game.scene('main')

// Camera
level.camera([0, 5, 10], [0, 0, 0], 60)

// Lighting
level.light('directional', { direction: [1, -1, 0.5], intensity: 1.0 })

// Ground
level.ground(50, 'grid')

// Player
level.spawn('player', {
  mesh: 'capsule',
  position: [0, 1, 0],
  controller: 'fps',
  mass: 1,
})

// Some objects
for (let i = 0; i < 5; i++) {
  level.spawn(`box_${i}`, {
    mesh: 'box',
    position: [Math.random() * 10 - 5, 3 + i * 2, Math.random() * 10 - 5],
    mass: 1,
    material: 'default',
  })
}

// HUD
const hud = document.getElementById('hud')!
game.frameLoop.onFrame(() => {
  hud.textContent = `FPS: ${Math.round(game.frameLoop.fps)} | Entities: ${level.entityCount}`
})

// Start
game.start()
