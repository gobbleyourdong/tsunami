/**
 * Tsunami Engine — WebGPU Native Browser Library
 * Zero dependencies. Web-first.
 *
 * Layering (see FRAMEWORK_MANIFEST.md):
 *   Layer 0 (runtime core): math, renderer, scene, physics, audio,
 *     input, animation, vfx, ai
 *   Layer 1 (components):   ./components — attach to EntityDef.properties
 *   Layer 2 (mechanics):    ./mechanics  — catalog runtime (33/46 implemented)
 *   Layer 2 (flow / UI):    ./flow, ./ui — orchestration + UI primitives
 *   Layer 3 (app):          ./game       — Game + SceneBuilder harness
 */

// Layer 0
export * from './renderer'
export * from './scene'
export * from './animation'
export * from './physics'
export * from './vfx'
export * from './ai'
export * from './audio'
export * from './input'
export * from './math/vec'
export * from './math/quat'

// Layer 1
export * from './systems'      // HealthSystem/Inventory/Score/Checkpoint
export * from './components'   // Component type shapes + helpers

// Layer 2
export * from './mechanics'    // Catalog runtime (via design/mechanics/)
export * from './flow'
export * from './ui'

// Layer 3
export * from './game'

// CLI tooling (separate entrypoint; exposed for completeness)
export * from './cli'
