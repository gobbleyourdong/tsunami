/**
 * Phase 3 — WorldMapTravel runtime smoke test.
 *
 * Verifies:
 * - Registers with the mechanic registry
 * - loadGraph sets current region + exposes reachable neighbors
 * - travelTo rejects non-adjacent moves in walk/vehicle modes
 * - teleport_menu mode bypasses adjacency (but honors vehicle gates)
 * - requires_vehicle regions unreachable until vehicle unlocked
 * - Random encounter rolls honor encounter_rate + encounter_table
 * - Active vehicle suppresses encounter rolls
 * - Seed-data integration: load scaffolds/.claude/seed_data/jrpg/world_map.json
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicInstance, WorldMapTravelParams } from '../src/design/schema'

function makeStubGame(): any {
  return { sceneManager: { activeScene: () => ({ entities: [] }) } }
}

function makeInstance(params: Partial<WorldMapTravelParams> = {}): MechanicInstance {
  return {
    id: 'wmt_test',
    type: 'WorldMapTravel',
    params: {
      map_mode: 'walk',
      scenes: [],
      encounter_rate: 0.0,
      vehicles: ['airship'],
      ...params,
    } as WorldMapTravelParams,
  }
}

function simpleGraph() {
  return {
    regions: {
      town: { id: 'town', connections: ['field'], encounter_rate: 0 },
      field: {
        id: 'field', connections: ['town', 'dungeon', 'ocean_cove'],
        encounter_rate: 0.8, encounter_table: ['slime', 'goblin'],
      },
      dungeon: {
        id: 'dungeon', connections: ['field'],
        encounter_rate: 0.5, encounter_table: ['skeleton'],
      },
      ocean_cove: {
        id: 'ocean_cove', connections: ['field', 'secret_isle'],
        encounter_rate: 0.1, encounter_table: ['crab'],
      },
      secret_isle: {
        id: 'secret_isle', connections: ['ocean_cove'],
        encounter_rate: 0, requires_vehicle: 'airship',
      },
    },
  }
}

describe('Phase 3 — WorldMapTravel runtime', () => {
  it('is registered in the mechanic registry', () => {
    expect(mechanicRegistry.has('WorldMapTravel')).toBe(true)
  })

  it('loadGraph seeds regions and starting region', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.getCurrentRegion()).toBe('town')
    expect(rt.listRegions()).toHaveLength(5)
  })

  it('reachableFromCurrent returns connections in walk mode', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.reachableFromCurrent()).toEqual(['field'])
  })

  it('travelTo to a connected region succeeds', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setRNG(() => 0.99)  // suppress encounter
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.travelTo('field')).toBe(true)
    expect(rt.getCurrentRegion()).toBe('field')
  })

  it('travelTo to a non-adjacent region is blocked in walk mode', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.travelTo('dungeon')).toBe(false)
    expect(rt.getCurrentRegion()).toBe('town')
  })

  it('travelTo bypasses adjacency in teleport_menu mode', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ map_mode: 'teleport_menu' }), makeStubGame(),
    )! as any
    rt.setRNG(() => 0.99)
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.travelTo('dungeon')).toBe(true)
    expect(rt.getCurrentRegion()).toBe('dungeon')
  })

  it('travelTo blocked when destination requires unowned vehicle', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ map_mode: 'teleport_menu' }), makeStubGame(),
    )! as any
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.travelTo('secret_isle')).toBe(false)
  })

  it('unlockVehicle + travelTo opens the gated region', () => {
    const rt = mechanicRegistry.create(
      makeInstance({ map_mode: 'teleport_menu' }), makeStubGame(),
    )! as any
    rt.setRNG(() => 0.99)
    rt.loadGraph(simpleGraph(), 'town')
    expect(rt.unlockVehicle('airship')).toBe(true)
    expect(rt.travelTo('secret_isle')).toBe(true)
  })

  it('unlockVehicle rejects vehicles not declared in params.vehicles', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    expect(rt.unlockVehicle('unicorn')).toBe(false)
  })

  it('random encounter fires when rate + rng align', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    // rng=0.0 → always under threshold, table pick index = floor(0.0 * len) = 0
    rt.setRNG(() => 0.0)
    rt.loadGraph(simpleGraph(), 'town')
    rt.travelTo('field')
    const events = rt.getEvents()
    expect(events.some((e: any) => e.kind === 'encounter' && e.enemy === 'slime')).toBe(true)
  })

  it('boarded vehicle suppresses encounter rolls', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.setRNG(() => 0.0)
    rt.loadGraph(simpleGraph(), 'town')
    rt.unlockVehicle('airship')
    rt.boardVehicle('airship')
    rt.travelTo('field')
    const events = rt.getEvents()
    expect(events.some((e: any) => e.kind === 'encounter')).toBe(false)
  })

  it('expose() surfaces current_region + reachable + vehicles', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadGraph(simpleGraph(), 'town')
    rt.unlockVehicle('airship')
    const snap = rt.expose() as any
    expect(snap.current_region).toBe('town')
    expect(snap.region_count).toBe(5)
    expect(snap.unlocked_vehicles).toEqual(['airship'])
  })

  it('integrates with JOB-F seed world_map.json (8 regions, baron_town start)', () => {
    const seedPath = join(
      __dirname, '..', '..', '..', '.claude', 'seed_data', 'jrpg', 'world_map.json',
    )
    if (!existsSync(seedPath)) {
      // Seed may not ship in every checkout — skip without failing.
      return
    }
    const data = JSON.parse(readFileSync(seedPath, 'utf8'))
    const rt = mechanicRegistry.create(
      makeInstance({
        map_mode: 'walk',
        scenes: Object.keys(data.regions),
        encounter_rate: 0.08,
      }),
      makeStubGame(),
    )! as any
    rt.setRNG(() => 0.99)
    rt.loadGraph(data, 'baron_town')
    expect(rt.getCurrentRegion()).toBe('baron_town')
    expect(rt.listRegions().length).toBeGreaterThanOrEqual(8)
    // baron_town connects to baron_field per the seed
    expect(rt.reachableFromCurrent()).toContain('baron_field')
    expect(rt.travelTo('baron_field')).toBe(true)
  })

  it('dispose clears state', () => {
    const rt = mechanicRegistry.create(makeInstance(), makeStubGame())! as any
    rt.loadGraph(simpleGraph(), 'town')
    rt.dispose()
    expect(rt.listRegions()).toEqual([])
    expect(rt.getCurrentRegion()).toBe('')
  })
})
