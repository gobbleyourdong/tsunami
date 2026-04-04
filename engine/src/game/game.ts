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
    }
    return game
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
}
