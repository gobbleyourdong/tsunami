/**
 * Scene builder — fluent API for constructing game scenes from code.
 * Builds entities, cameras, lights, and ground planes.
 */

import { Vec3 } from '../math/vec'
import { GameScene } from '../flow/scene_manager'
import type { Game, SceneDefinition, EntityDefinition } from './game'

export interface SpawnOptions {
  mesh?: string
  position?: Vec3
  rotation?: Vec3
  scale?: Vec3 | number
  material?: string
  controller?: string
  ai?: string
  patrol?: Vec3[]
  trigger?: string
  mass?: number
  isStatic?: boolean
  properties?: Record<string, unknown>
}

export interface LightOptions {
  direction?: Vec3
  intensity?: number
  color?: [number, number, number]
  position?: Vec3
  range?: number
}

export class SceneBuilder {
  readonly name: string
  private game: Game
  private entities: EntityDef[] = []
  private cameraConfig: { position: Vec3; target: Vec3; fov: number } = {
    position: [0, 5, 10], target: [0, 0, 0], fov: 50,
  }
  private lights: { type: string; options: LightOptions }[] = []
  private groundConfig: { size: number; material: string } | null = null
  private initCallbacks: (() => void)[] = []
  private updateCallbacks: ((dt: number) => void)[] = []

  constructor(name: string, game: Game) {
    this.name = name
    this.game = game
  }

  /** Set scene camera. */
  camera(config: { position?: Vec3; target?: Vec3; fov?: number }): this {
    if (config.position) this.cameraConfig.position = config.position
    if (config.target) this.cameraConfig.target = config.target
    if (config.fov) this.cameraConfig.fov = config.fov
    return this
  }

  /** Add a light. */
  light(type: 'directional' | 'point' | 'spot', options?: LightOptions): this {
    this.lights.push({ type, options: options ?? {} })
    return this
  }

  /** Add a ground plane. */
  ground(config: { size?: number; material?: string }): this {
    this.groundConfig = {
      size: config.size ?? 50,
      material: config.material ?? 'default',
    }
    return this
  }

  /** Spawn an entity. */
  spawn(name: string, options?: SpawnOptions): this {
    const scaleVec: Vec3 = typeof options?.scale === 'number'
      ? [options.scale, options.scale, options.scale]
      : (options?.scale ?? [1, 1, 1])

    this.entities.push({
      name,
      type: options?.mesh ?? 'box',
      position: options?.position ?? [0, 0, 0],
      rotation: options?.rotation ?? [0, 0, 0],
      scale: scaleVec,
      material: options?.material,
      controller: options?.controller,
      ai: options?.ai,
      patrol: options?.patrol,
      trigger: options?.trigger,
      mass: options?.mass,
      isStatic: options?.isStatic ?? false,
      properties: options?.properties ?? {},
    })
    return this
  }

  /** Register a callback to run on scene init. */
  onInit(callback: () => void): this {
    this.initCallbacks.push(callback)
    return this
  }

  /** Register a callback to run every frame. */
  onUpdate(callback: (dt: number) => void): this {
    this.updateCallbacks.push(callback)
    return this
  }

  /** Get all spawned entity definitions. */
  getEntities(): EntityDef[] {
    return [...this.entities]
  }

  /** Get entity by name. */
  getEntity(name: string): EntityDef | undefined {
    return this.entities.find(e => e.name === name)
  }

  /** Number of entities in scene. */
  get entityCount(): number {
    return this.entities.length
  }

  /** Convert to a GameScene for the SceneManager. */
  toGameScene(): GameScene {
    const self = this
    return {
      name: this.name,
      init() {
        for (const cb of self.initCallbacks) cb()
      },
      enter() {
        // Setup camera from config
        self.game.camera.position = [...self.cameraConfig.position]
        self.game.camera.target = [...self.cameraConfig.target]
        self.game.camera.fov = self.cameraConfig.fov
      },
      update(dt: number) {
        for (const cb of self.updateCallbacks) cb(dt)
      },
    }
  }

  /** Serialize to a JSON-safe definition. */
  serialize(): SceneDefinition {
    return {
      name: this.name,
      entities: this.entities.map(e => ({
        name: e.name,
        type: e.type,
        position: e.position,
        rotation: e.rotation,
        scale: e.scale,
        properties: {
          ...e.properties,
          material: e.material,
          controller: e.controller,
          ai: e.ai,
          trigger: e.trigger,
          mass: e.mass,
          isStatic: e.isStatic,
          ...(e.patrol ? { patrol: e.patrol } : {}),
        },
      })),
      camera: {
        position: this.cameraConfig.position,
        target: this.cameraConfig.target,
        fov: this.cameraConfig.fov,
      },
    }
  }

  /** Load from a serialized definition. */
  deserialize(def: SceneDefinition): void {
    this.entities.length = 0
    for (const e of def.entities) {
      this.entities.push({
        name: e.name,
        type: e.type,
        position: e.position,
        rotation: e.rotation,
        scale: e.scale,
        material: e.properties.material as string | undefined,
        controller: e.properties.controller as string | undefined,
        ai: e.properties.ai as string | undefined,
        trigger: e.properties.trigger as string | undefined,
        mass: e.properties.mass as number | undefined,
        isStatic: e.properties.isStatic as boolean ?? false,
        patrol: e.properties.patrol as Vec3[] | undefined,
        properties: e.properties,
      })
    }
    if (def.camera) {
      this.cameraConfig = {
        position: def.camera.position,
        target: def.camera.target,
        fov: def.camera.fov ?? 50,
      }
    }
  }
}

interface EntityDef {
  name: string
  type: string
  position: Vec3
  rotation: Vec3
  scale: Vec3
  material?: string
  controller?: string
  ai?: string
  patrol?: Vec3[]
  trigger?: string
  mass?: number
  isStatic: boolean
  properties: Record<string, unknown>
}
