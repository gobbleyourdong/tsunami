/**
 * ParallaxScroll mechanic — unit tests for scroll-position calculation.
 *
 * Creates a minimal stub Game + scene-with-player and steps the mechanic
 * through position deltas, checking that per-layer offsets accumulate at
 * the configured scroll_speed_ratio.
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/design/mechanics/index'
import type { MechanicInstance } from '../src/design/schema'
// Side-effect import to ensure ParallaxScroll is registered
import '../src/design/mechanics/parallax_scroll'

interface StubScene {
  entities: Array<{ archetype: string; position: { x: number; y: number } }>
}

interface StubGame {
  sceneManager: { activeScene: () => StubScene | null }
  scene: StubScene
}

function makeGame(playerX: number, playerY: number): StubGame {
  const scene: StubScene = {
    entities: [{ archetype: 'player', position: { x: playerX, y: playerY } }],
  }
  return {
    scene,
    sceneManager: { activeScene: () => scene },
  }
}

function makeInstance(layers: Array<{ sprite_id: string; scroll_speed_ratio: number; layer_z?: number; lock_y?: boolean }>): MechanicInstance {
  return {
    id: 'px_0' as any,
    type: 'ParallaxScroll',
    params: {
      follow_archetype: 'player' as any,
      axes: 'horizontal',
      layers,
    } as any,
  }
}

describe('ParallaxScroll', () => {
  it('registers in the mechanic registry', () => {
    expect(mechanicRegistry.has('ParallaxScroll')).toBe(true)
  })

  it('3-layer parallax: offsets accumulate at per-layer ratios', () => {
    const game = makeGame(0, 0)
    const instance = makeInstance([
      { sprite_id: 'far',  scroll_speed_ratio: 0.25 },
      { sprite_id: 'mid',  scroll_speed_ratio: 0.5 },
      { sprite_id: 'near', scroll_speed_ratio: 1.0 },
    ])
    const rt = mechanicRegistry.create(instance, game as any)!
    expect(rt).toBeTruthy()

    // Move player 100 world-units right, tick the mechanic.
    game.scene.entities[0].position.x = 100
    rt.update(1 / 60)

    const exposed = rt.expose!() as any
    const offs = exposed.layer_offsets
    expect(offs).toHaveLength(3)
    expect(offs[0].offset_x).toBeCloseTo(25)   // far: 100 * 0.25
    expect(offs[1].offset_x).toBeCloseTo(50)   // mid: 100 * 0.5
    expect(offs[2].offset_x).toBeCloseTo(100)  // near: 100 * 1.0
    expect(offs[0].offset_y).toBe(0)           // horizontal-only axes
    rt.dispose()
  })

  it('offsets accumulate across multiple updates', () => {
    const game = makeGame(0, 0)
    const instance = makeInstance([{ sprite_id: 'far', scroll_speed_ratio: 0.5 }])
    const rt = mechanicRegistry.create(instance, game as any)!

    game.scene.entities[0].position.x = 40
    rt.update(1 / 60)
    let off = (rt.expose!() as any).layer_offsets[0].offset_x
    expect(off).toBeCloseTo(20)

    game.scene.entities[0].position.x = 100  // another 60 units
    rt.update(1 / 60)
    off = (rt.expose!() as any).layer_offsets[0].offset_x
    expect(off).toBeCloseTo(20 + 30)  // accumulated: 20 + (60 * 0.5)
    rt.dispose()
  })

  it('default z-ordering: far=-10, near=0 for 3-layer', () => {
    const game = makeGame(0, 0)
    const instance = makeInstance([
      { sprite_id: 'far',  scroll_speed_ratio: 0.25 },
      { sprite_id: 'mid',  scroll_speed_ratio: 0.5 },
      { sprite_id: 'near', scroll_speed_ratio: 0.75 },
    ])
    const rt = mechanicRegistry.create(instance, game as any)!
    rt.update(1 / 60)
    const offs = (rt.expose!() as any).layer_offsets
    expect(offs[0].layer_z).toBe(-10)
    expect(offs[1].layer_z).toBe(-5)
    expect(offs[2].layer_z).toBe(0)
    rt.dispose()
  })

  it('explicit layer_z overrides default', () => {
    const game = makeGame(0, 0)
    const instance = makeInstance([
      { sprite_id: 'sky', scroll_speed_ratio: 0, layer_z: -100 },
      { sprite_id: 'foreground_skin', scroll_speed_ratio: 1, layer_z: 5 },
    ])
    const rt = mechanicRegistry.create(instance, game as any)!
    rt.update(1 / 60)
    const offs = (rt.expose!() as any).layer_offsets
    expect(offs[0].layer_z).toBe(-100)
    expect(offs[1].layer_z).toBe(5)
    rt.dispose()
  })

  it('static skybox (ratio=0) does not move when player moves', () => {
    const game = makeGame(0, 0)
    const instance = makeInstance([{ sprite_id: 'skybox', scroll_speed_ratio: 0 }])
    const rt = mechanicRegistry.create(instance, game as any)!

    game.scene.entities[0].position.x = 500
    rt.update(1 / 60)
    game.scene.entities[0].position.x = 1000
    rt.update(1 / 60)
    const off = (rt.expose!() as any).layer_offsets[0].offset_x
    expect(off).toBe(0)  // static
    rt.dispose()
  })

  it('handles missing follow-archetype gracefully', () => {
    const game = makeGame(0, 0)
    game.scene.entities = []  // no player
    const instance = makeInstance([{ sprite_id: 'far', scroll_speed_ratio: 0.5 }])
    const rt = mechanicRegistry.create(instance, game as any)!
    // Should not throw on update
    expect(() => rt.update(1 / 60)).not.toThrow()
    const offs = (rt.expose!() as any).layer_offsets
    expect(offs[0].offset_x).toBe(0)
    rt.dispose()
  })
})
