/**
 * Game entry point — supports both engine-native and React modes.
 *
 * ENGINE MODE (gamedev model writes this file directly):
 *   import { Game } from '@engine/game/game'
 *   const game = new Game({ mode: '2d' })
 *   // ... scene setup, input binding, game.start()
 *
 * REACT MODE (current model writes App.tsx):
 *   This file auto-detects App.tsx and mounts it via React.
 *   The model doesn't touch main.ts — it writes App.tsx like any scaffold.
 *
 * Engine API:
 *   Game, SceneBuilder, KeyboardInput, ActionMap,
 *   ScoreSystem, HealthSystem, CheckpointSystem,
 *   DifficultyManager, MenuSystem, DialogSystem, TutorialSystem,
 *   PhysicsWorld, ParticleSystem, BehaviorTree, FSM, Pathfinding
 */

// Auto-detect: if App.tsx exists and has content, mount React
// @ts-ignore — dynamic import for optional React mode
import('./App').then(({ default: App }) => {
  if (App && typeof App === 'function') {
    import('react-dom/client').then(({ createRoot }) => {
      const root = document.getElementById('root')
      if (root) {
        // Hide canvas (React mode doesn't use it)
        const canvas = document.getElementById('game')
        if (canvas) canvas.style.display = 'none'
        createRoot(root).render(App())
      }
    })
  }
}).catch(() => {
  // No App.tsx or import failed — engine mode.
  // When the gamedev model replaces this file, this catch never runs.
})
