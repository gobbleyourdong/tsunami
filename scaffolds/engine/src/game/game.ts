/**
 * Game class — top-level API for building games from code.
 * Wires renderer, physics, audio, input, scene manager, and frame loop.
 *
 * const game = new Game({ mode: '3d', width: 1280, height: 720 })
 * const level = game.scene('level1')
 * level.spawn('player', { mesh: 'capsule', position: [0,1,0] })
 * game.start()
 */

import { Camera, CameraMode } from '../renderer/camera'
import { FrameLoop } from '../renderer/frame'
import { SceneManager, GameScene } from '../flow/scene_manager'
import { GameFlow, FlowStep } from '../flow/game_flow'
import { PhysicsWorld } from '../physics/world'
import { ActionMap } from '../input/action_map'
import { KeyboardInput } from '../input/keyboard'
import { SceneBuilder } from './scene_builder'
import { mechanicRegistry } from '../design/mechanics/_registry'
import type { MechanicRuntime } from '../design/mechanics/_registry'
import type { MechanicInstance } from '../design/schema'

export type GameMode = '2d' | '3d'

export interface GameConfig {
  mode?: GameMode
  width?: number
  height?: number
  title?: string
  pixelPerfect?: boolean
  camera?: 'perspective' | 'orthographic'
  gravity?: [number, number, number]
  physicsRate?: number  // Hz
  antialias?: boolean
}

const DEFAULT_CONFIG: Required<GameConfig> = {
  mode: '3d',
  width: 1280,
  height: 720,
  title: 'Tsunami Game',
  pixelPerfect: false,
  camera: 'perspective',
  gravity: [0, -9.81, 0],
  physicsRate: 60,
  antialias: true,
}

export class Game {
  readonly config: Required<GameConfig>
  readonly camera: Camera
  readonly physics: PhysicsWorld
  readonly sceneManager: SceneManager
  readonly flow: GameFlow
  readonly input: KeyboardInput
  readonly actionMap: ActionMap
  readonly frameLoop: FrameLoop

  private scenes = new Map<string, SceneBuilder>()
  private _running = false

  // v1.1 runtime wiring (engine_handoff_001 §A).
  //   mechanicInstanceById — every MechanicInstance declared in the
  //     GameDefinition, keyed by its `.id`. Populated by fromDefinition.
  //   mechanicIdsByScene — per-scene list of mechanic ids (as stashed by
  //     the compiler on scene.properties.mechanics).
  //   mechanicsByScene — live MechanicRuntime[] per scene; populated on
  //     scene activation, torn down on deactivation.
  //   activeSceneName — the scene whose runtimes tick each frame.
  private mechanicInstanceById = new Map<string, MechanicInstance>()
  private mechanicIdsByScene = new Map<string, string[]>()
  private mechanicsByScene = new Map<string, MechanicRuntime[]>()
  private activeSceneName = ''

  constructor(config?: GameConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config }

    const cameraMode: CameraMode = this.config.camera === 'orthographic' || this.config.mode === '2d'
      ? 'orthographic' : 'perspective'

    this.camera = new Camera({
      mode: cameraMode,
      fov: 60,
      orthoSize: this.config.mode === '2d' ? this.config.height / 2 : 10,
    })

    this.physics = new PhysicsWorld()
    this.physics.gravity = this.config.gravity

    this.sceneManager = new SceneManager()
    this.flow = new GameFlow(this.sceneManager)
    this.input = new KeyboardInput()
    this.actionMap = new ActionMap()
    this.frameLoop = new FrameLoop()
  }

  /** Create or get a scene builder. */
  scene(name: string): SceneBuilder {
    if (this.scenes.has(name)) return this.scenes.get(name)!
    const builder = new SceneBuilder(name, this)
    this.scenes.set(name, builder)
    return builder
  }

  /** Define the game flow. */
  setFlow(steps: FlowStep[]): this {
    // Register all scene builders as GameScenes
    for (const [name, builder] of this.scenes) {
      this.sceneManager.add(builder.toGameScene())
    }
    this.flow.setFlow(steps)
    return this
  }

  /** Start the game loop. */
  async start(): Promise<void> {
    if (this._running) return
    this._running = true

    this.input.bind()

    this.frameLoop.onFixedUpdate = (dt) => {
      this.physics.step(dt)
    }

    this.frameLoop.onUpdate = (stats) => {
      this.flow.update(stats.dt)
      this.input.update()
      this.tickMechanics(stats.dt)
    }

    this.frameLoop.onRender = (stats) => {
      this.flow.render(stats.dt)
    }

    // Start flow if configured
    if (this.flow.currentScene) {
      await this.flow.start()
    }

    this.frameLoop.start()
  }

  /** Stop the game loop. */
  stop(): void {
    this._running = false
    this.frameLoop.stop()
    this.input.unbind()
  }

  get running(): boolean { return this._running }

  get width(): number { return this.config.width }
  get height(): number { return this.config.height }

  /** Serialize entire game definition to JSON. */
  serialize(): GameDefinition {
    const scenes: Record<string, SceneDefinition> = {}
    for (const [name, builder] of this.scenes) {
      scenes[name] = builder.serialize()
    }
    return {
      config: this.config,
      scenes,
      flow: [],  // flow steps would be serialized here
    }
  }

  /** Create a Game from a serialized definition. */
  static fromDefinition(def: GameDefinition): Game {
    const game = new Game(def.config)
    for (const [name, sceneDef] of Object.entries(def.scenes)) {
      const builder = game.scene(name)
      builder.deserialize(sceneDef)
      // Compiler stashes mechanic ids on scene.properties.mechanics (see
      // scaffolds/engine/src/design/compiler.ts:makeScene). SceneDefinition
      // doesn't type `properties`, so peek loosely.
      const props =
        (sceneDef as unknown as { properties?: Record<string, unknown> }).properties
      const rawIds = (props?.mechanics ?? []) as unknown
      if (Array.isArray(rawIds)) {
        game.mechanicIdsByScene.set(
          name,
          rawIds.filter((x): x is string => typeof x === 'string'),
        )
      }
    }
    for (const mi of def.mechanics ?? []) {
      game.mechanicInstanceById.set(mi.id as unknown as string, mi)
    }
    // Hook scene transitions so runtimes init/dispose cleanly. Each
    // SceneManager.switch* path fires onSceneChange after the new scene's
    // enter(), which is the right edge for per-scene mechanic activation.
    game.sceneManager.onSceneChange = (from: string, to: string) => {
      game.handleSceneChange(from, to)
    }
    return game
  }

  // ───────── mechanic-runtime wiring (engine_handoff_001 §A) ─────────

  /**
   * Explicitly activate a scene's mechanic runtimes. Idempotent: when
   * the scene is already active, does nothing. Useful for callers who
   * bypass the flow/sceneManager path (e.g. unit tests that drive
   * mechanics directly). Normal play activates via `onSceneChange`.
   */
  activateScene(sceneName: string): void {
    if (this.activeSceneName === sceneName) return
    if (this.activeSceneName) this.tearDownScene(this.activeSceneName)
    this.activateSceneInternal(sceneName)
  }

  /** Return the live runtimes for a scene (or empty array). */
  mechanicsForScene(sceneName: string): MechanicRuntime[] {
    return this.mechanicsByScene.get(sceneName) ?? []
  }

  /** Name of the scene whose runtimes currently tick. Empty until first scene activates. */
  get activeScene(): string {
    return this.activeSceneName
  }

  private handleSceneChange(from: string, to: string): void {
    if (from && from !== to) this.tearDownScene(from)
    if (to !== this.activeSceneName) this.activateSceneInternal(to)
  }

  private activateSceneInternal(sceneName: string): void {
    this.activeSceneName = sceneName
    // Factories may have been registered before fromDefinition ran; that's
    // fine. If scene has no recorded ids (DSL-path games), stay empty.
    const ids = this.mechanicIdsByScene.get(sceneName) ?? []
    const runtimes: MechanicRuntime[] = []
    for (const id of ids) {
      const mi = this.mechanicInstanceById.get(id)
      if (!mi) {
        console.warn(`[game] scene '${sceneName}' references mechanic '${id}' but no MechanicInstance is registered — skipping`)
        continue
      }
      const rt = mechanicRegistry.create(mi, this)
      // Per the convention in mechanics/*.ts, factories call rt.init(game)
      // before returning. We do NOT call init again here — that would
      // double-init. `create` returns null if the mechanic has no runtime
      // yet (e.g. the rendering-only types during the UI wiring phase).
      if (rt) runtimes.push(rt)
    }
    this.mechanicsByScene.set(sceneName, runtimes)
  }

  private tearDownScene(sceneName: string): void {
    const rts = this.mechanicsByScene.get(sceneName)
    if (!rts) return
    for (const rt of rts) {
      try { rt.dispose() }
      catch (e) { console.error(`[game] mechanic dispose() threw:`, e) }
    }
    this.mechanicsByScene.delete(sceneName)
    if (this.activeSceneName === sceneName) this.activeSceneName = ''
  }

  private tickMechanics(dt: number): void {
    if (!this.activeSceneName) return
    const rts = this.mechanicsByScene.get(this.activeSceneName)
    if (!rts || rts.length === 0) return
    for (const rt of rts) {
      try { rt.update(dt) }
      catch (e) { console.error(`[game] mechanic update() threw:`, e) }
    }
  }
}

// --- Serialization types ---

export interface EntityDefinition {
  name: string
  type: string
  position: [number, number, number]
  rotation: [number, number, number]
  scale: [number, number, number]
  properties: Record<string, unknown>
}

export interface SceneDefinition {
  name: string
  entities: EntityDefinition[]
  camera?: {
    position: [number, number, number]
    target: [number, number, number]
    fov?: number
  }
  lighting?: {
    ambient: [number, number, number]
    directional?: {
      direction: [number, number, number]
      intensity: number
      color: [number, number, number]
    }
  }
}

export interface GameDefinition {
  config: Required<GameConfig>
  scenes: Record<string, SceneDefinition>
  flow: FlowStep[]
  /**
   * v1.1 runtime wiring (engine_handoff_001 §A). MechanicInstance bag
   * for the whole game, keyed by `mi.id`. Each scene's
   * `properties.mechanics: string[]` is a selector into this list. Left
   * optional so legacy callers that build a Game manually still
   * deserialize without type warnings.
   */
  mechanics?: MechanicInstance[]
}
