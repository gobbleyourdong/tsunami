import { describe, it, expect } from 'vitest'
import { createVillageMap, createForestMap, canMoveTo, isWalkable, isBlockedByProp } from '../src/rpg/world'

describe('RPG World', () => {
  it('village map has correct dimensions', () => {
    const map = createVillageMap()
    expect(map.width).toBe(24)
    expect(map.height).toBe(18)
    expect(map.layers.ground.length).toBe(18)
    expect(map.layers.ground[0].length).toBe(24)
  })

  it('forest map has correct dimensions', () => {
    const map = createForestMap()
    expect(map.width).toBe(24)
    expect(map.height).toBe(18)
  })

  it('village has NPCs', () => {
    const map = createVillageMap()
    expect(map.npcs.length).toBe(3)
    expect(map.npcs.find(n => n.id === 'elder')).toBeDefined()
    expect(map.npcs.find(n => n.id === 'merchant')).toBeDefined()
    expect(map.npcs.find(n => n.id === 'guard')).toBeDefined()
  })

  it('forest has hostile wolves', () => {
    const map = createForestMap()
    const wolves = map.npcs.filter(n => n.hostile)
    expect(wolves.length).toBe(3)
  })

  it('water and lava are not walkable', () => {
    expect(isWalkable('water')).toBe(false)
    expect(isWalkable('lava')).toBe(false)
    expect(isWalkable('grass')).toBe(true)
    expect(isWalkable('path')).toBe(true)
  })

  it('canMoveTo respects bounds', () => {
    const map = createVillageMap()
    expect(canMoveTo(map, -1, 5)).toBe(false)
    expect(canMoveTo(map, 100, 5)).toBe(false)
    expect(canMoveTo(map, 5, -1)).toBe(false)
  })

  it('canMoveTo respects water tiles', () => {
    const map = createVillageMap()
    // Pond is at 13,5 and 14,5-7
    expect(canMoveTo(map, 5, 13)).toBe(false) // water tile
  })

  it('canMoveTo respects solid props', () => {
    const map = createVillageMap()
    // House at 7,4 is solid
    expect(isBlockedByProp(map, 7, 4)).toBe(true)
    // Empty grass tile should not be blocked
    expect(isBlockedByProp(map, 10, 10)).toBe(false)
  })

  it('village has exit to forest', () => {
    const map = createVillageMap()
    const exit = map.exits.find(e => e.target === 'forest')
    expect(exit).toBeDefined()
  })

  it('forest has exit back to village', () => {
    const map = createForestMap()
    const exit = map.exits.find(e => e.target === 'village')
    expect(exit).toBeDefined()
  })

  it('playerStart is on a walkable tile', () => {
    const map = createVillageMap()
    const [sx, sy] = map.playerStart
    expect(canMoveTo(map, sx, sy)).toBe(true)
  })

  it('NPCs have dialog', () => {
    const map = createVillageMap()
    for (const npc of map.npcs) {
      if (!npc.hostile) {
        expect(npc.dialog!.length).toBeGreaterThan(0)
      }
    }
  })

  it('guard has patrol waypoints', () => {
    const map = createVillageMap()
    const guard = map.npcs.find(n => n.id === 'guard')!
    expect(guard.patrol).toBeDefined()
    expect(guard.patrol!.length).toBeGreaterThan(0)
  })
})
