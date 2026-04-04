import { describe, it, expect } from 'vitest'
import { Game } from '../src/game/game'
import { SceneBuilder } from '../src/game/scene_builder'
import { parseArgs, generateHTML, createManifest, addToManifest, validateManifest } from '../src/cli/runner'

describe('Game', () => {
  it('creates with default config', () => {
    const game = new Game()
    expect(game.config.mode).toBe('3d')
    expect(game.config.width).toBe(1280)
    expect(game.config.height).toBe(720)
    expect(game.camera.mode).toBe('perspective')
  })

  it('creates 2D game with orthographic camera', () => {
    const game = new Game({ mode: '2d', width: 800, height: 600 })
    expect(game.config.mode).toBe('2d')
    expect(game.camera.mode).toBe('orthographic')
  })

  it('creates 3D game with custom config', () => {
    const game = new Game({
      mode: '3d',
      width: 1920,
      height: 1080,
      title: 'My Game',
      camera: 'orthographic',
    })
    expect(game.config.title).toBe('My Game')
    expect(game.camera.mode).toBe('orthographic')
  })

  it('scene() creates and caches scene builders', () => {
    const game = new Game()
    const level1 = game.scene('level1')
    const level1Again = game.scene('level1')
    expect(level1).toBe(level1Again)

    const level2 = game.scene('level2')
    expect(level2).not.toBe(level1)
  })

  it('serializes to JSON definition', () => {
    const game = new Game({ title: 'Test Game' })
    const level = game.scene('level1')
    level.camera({ position: [0, 10, 20], fov: 60 })
    level.spawn('player', { mesh: 'capsule', position: [0, 1, 0] })
    level.spawn('enemy', { mesh: 'box', position: [5, 1, 0], ai: 'patrol' })

    const def = game.serialize()
    expect(def.config.title).toBe('Test Game')
    expect(def.scenes.level1).toBeDefined()
    expect(def.scenes.level1.entities.length).toBe(2)
    expect(def.scenes.level1.entities[0].name).toBe('player')
    expect(def.scenes.level1.camera?.position).toEqual([0, 10, 20])
  })

  it('round-trips through serialize/deserialize', () => {
    const game = new Game({ mode: '3d' })
    const level = game.scene('arena')
    level.spawn('hero', { mesh: 'capsule', position: [0, 1, 0], mass: 1 })
    level.spawn('pickup', { mesh: 'sphere', scale: 0.3, trigger: 'coin' })
    level.camera({ position: [0, 8, 12], target: [0, 0, 0] })

    const def = game.serialize()
    const json = JSON.stringify(def)
    const restored = Game.fromDefinition(JSON.parse(json))

    expect(restored.config.mode).toBe('3d')
    const restoredLevel = restored.scene('arena')
    expect(restoredLevel.entityCount).toBe(2)
    expect(restoredLevel.getEntity('hero')).toBeDefined()
    expect(restoredLevel.getEntity('pickup')).toBeDefined()
  })

  it('physics gravity is configurable', () => {
    const game = new Game({ gravity: [0, -20, 0] })
    expect(game.physics.gravity).toEqual([0, -20, 0])
  })
})

describe('SceneBuilder', () => {
  it('spawns entities with defaults', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.spawn('box1')
    expect(scene.entityCount).toBe(1)

    const entity = scene.getEntity('box1')
    expect(entity).toBeDefined()
    expect(entity!.position).toEqual([0, 0, 0])
    expect(entity!.scale).toEqual([1, 1, 1])
    expect(entity!.type).toBe('box')
  })

  it('spawns with full options', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.spawn('player', {
      mesh: 'capsule',
      position: [1, 2, 3],
      rotation: [0, Math.PI, 0],
      scale: 2,
      controller: 'fps',
      mass: 70,
    })

    const entity = scene.getEntity('player')
    expect(entity!.type).toBe('capsule')
    expect(entity!.position).toEqual([1, 2, 3])
    expect(entity!.scale).toEqual([2, 2, 2])
    expect(entity!.controller).toBe('fps')
    expect(entity!.mass).toBe(70)
  })

  it('configures camera', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.camera({ position: [0, 50, 100], target: [0, 0, 0], fov: 45 })

    const def = scene.serialize()
    expect(def.camera?.position).toEqual([0, 50, 100])
    expect(def.camera?.fov).toBe(45)
  })

  it('adds lights', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.light('directional', { direction: [1, -2, 1], intensity: 1.5 })
    scene.light('point', { position: [0, 5, 0], range: 10 })
    // Lights are tracked internally — serialization would include them
    expect(scene.entityCount).toBe(0) // lights are separate
  })

  it('adds ground plane', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.ground({ size: 100, material: 'grass' })
    // Ground config is tracked internally
  })

  it('chaining API works', () => {
    const game = new Game()
    const scene = game.scene('level')
      .camera({ position: [0, 10, 20] })
      .light('directional', { intensity: 1.5 })
      .ground({ size: 50 })
      .spawn('player', { mesh: 'capsule', position: [0, 1, 0] })
      .spawn('enemy', { mesh: 'box', position: [5, 1, 0] })

    expect(scene.entityCount).toBe(2)
  })

  it('converts to GameScene with lifecycle', () => {
    const game = new Game()
    const scene = game.scene('test')
    let inited = false
    let updated = false
    scene.onInit(() => { inited = true })
    scene.onUpdate(() => { updated = true })

    const gs = scene.toGameScene()
    gs.init?.()
    gs.update?.(0.016)

    expect(inited).toBe(true)
    expect(updated).toBe(true)
  })

  it('serializes and deserializes entities', () => {
    const game = new Game()
    const scene = game.scene('test')
    scene.spawn('a', { mesh: 'sphere', position: [1, 2, 3], ai: 'chase' })

    const def = scene.serialize()
    expect(def.entities.length).toBe(1)
    expect(def.entities[0].name).toBe('a')
    expect(def.entities[0].properties.ai).toBe('chase')

    const game2 = new Game()
    const scene2 = game2.scene('test')
    scene2.deserialize(def)
    expect(scene2.entityCount).toBe(1)
    const entity = scene2.getEntity('a')
    expect(entity?.position).toEqual([1, 2, 3])
  })
})

describe('CLI Runner', () => {
  it('parses args with defaults', () => {
    const config = parseArgs(['game.ts'])
    expect(config.gamePath).toBe('game.ts')
    expect(config.headless).toBe(false)
    expect(config.width).toBe(1280)
  })

  it('parses --headless flag', () => {
    const config = parseArgs(['game.ts', '--headless'])
    expect(config.headless).toBe(true)
  })

  it('parses --screenshot-at', () => {
    const config = parseArgs(['game.ts', '--screenshot-at=60', '--output=frame.png'])
    expect(config.screenshotAt).toBe(60)
    expect(config.screenshotOutput).toBe('frame.png')
  })

  it('parses --width and --height', () => {
    const config = parseArgs(['game.ts', '--width=1920', '--height=1080'])
    expect(config.width).toBe(1920)
    expect(config.height).toBe(1080)
  })

  it('generates valid HTML', () => {
    const html = generateHTML('./game.ts')
    expect(html).toContain('<canvas')
    expect(html).toContain('game.ts')
    expect(html).toContain('type="module"')
  })
})

describe('Asset Manifest', () => {
  it('creates empty manifest', () => {
    const m = createManifest()
    expect(m.meshes).toEqual([])
    expect(m.textures).toEqual([])
    expect(m.sounds).toEqual([])
  })

  it('adds assets without duplicates', () => {
    const m = createManifest()
    addToManifest(m, 'meshes', 'player.glb')
    addToManifest(m, 'meshes', 'player.glb')
    addToManifest(m, 'textures', 'grass.png')
    expect(m.meshes).toEqual(['player.glb'])
    expect(m.textures).toEqual(['grass.png'])
  })

  it('validates empty manifest', () => {
    const m = createManifest()
    const result = validateManifest(m)
    expect(result.valid).toBe(true)
    expect(result.missing).toEqual([])
  })
})

describe('Full Game Build Example', () => {
  it('builds a complete platformer definition from code', () => {
    const game = new Game({ mode: '3d', width: 1280, height: 720, title: 'Platformer' })

    const title = game.scene('title')
    title.camera({ position: [0, 5, 15] })
    title.spawn('logo', { mesh: 'plane', position: [0, 3, 0], scale: 5 })

    const level1 = game.scene('level1')
    level1.camera({ position: [0, 8, 12], fov: 50 })
    level1.light('directional', { direction: [1, -2, 1], intensity: 1.5 })
    level1.ground({ size: 50 })
    level1.spawn('player', { mesh: 'capsule', position: [0, 1, 0], controller: 'platformer' })
    level1.spawn('enemy1', { mesh: 'box', position: [5, 1, 0], ai: 'patrol', patrol: [[5,1,0],[10,1,0]] })
    level1.spawn('enemy2', { mesh: 'box', position: [-3, 1, 5], ai: 'patrol' })
    level1.spawn('coin1', { mesh: 'sphere', scale: 0.3, position: [3, 2, 0], trigger: 'coin' })
    level1.spawn('coin2', { mesh: 'sphere', scale: 0.3, position: [7, 2, 0], trigger: 'coin' })

    const gameover = game.scene('gameover')
    gameover.camera({ position: [0, 5, 10] })

    // Verify
    expect(level1.entityCount).toBe(5)
    expect(game.scene('level1').getEntity('player')?.controller).toBe('platformer')

    // Serialize round-trip
    const def = game.serialize()
    const json = JSON.stringify(def)
    expect(json.length).toBeGreaterThan(500)

    const restored = Game.fromDefinition(JSON.parse(json))
    expect(restored.scene('level1').entityCount).toBe(5)
    expect(restored.scene('level1').getEntity('enemy1')?.ai).toBe('patrol')
    expect(restored.config.title).toBe('Platformer')
  })
})
