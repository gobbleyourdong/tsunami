/**
 * World scene — overworld traversal.
 *
 * Composes mechanics from @engine/mechanics:
 *  - WorldMapTravel (scene-graph traversal, encounter rolls, vehicle gates)
 *  - PartyComposition (active party tracking, needed for battle handoff)
 *  - CameraFollow (tracks party sprite across the overworld)
 *  - HUD (region name, party HP bars, gold counter)
 *
 * Hands off to Battle scene when WorldMapTravel rolls an encounter.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import worldData from '../../data/world_map.json'
import partyData from '../../data/party.json'
import config from '../../data/config.json'

export class World {
  readonly name = 'world'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private wmtRuntime: any = null
  private partyRuntime: any = null

  constructor() {
    const regions = Object.keys((worldData as { regions: Record<string, any> }).regions)
    this.description = `Overworld (${regions.length} regions) — ATB combat on encounter`
  }

  setup(): void {
    // WorldMapTravel — loadGraph seeds the 8-region map from JOB-F.
    this.wmtRuntime = this.tryMount('WorldMapTravel', {
      map_mode: 'walk',
      scenes: Object.keys((worldData as any).regions),
      encounter_rate: 0.08,
      vehicles: ['airship', 'hovercraft'],
    })
    if (this.wmtRuntime && typeof this.wmtRuntime.loadGraph === 'function') {
      this.wmtRuntime.loadGraph(worldData, (config as any).starting_region ?? 'baron_town')
    }

    // PartyComposition — active party + roster from party.json.
    this.partyRuntime = this.tryMount('PartyComposition', {
      max_active: 4,
      max_roster: 8,
      can_swap_mid_battle: false,
      default_formation: 'row_standard',
    })
    if (this.partyRuntime) {
      const members = (partyData as { characters?: Record<string, any>; party?: Record<string, any> }).characters ??
                      (partyData as { party?: Record<string, any> }).party ?? {}
      for (const [id, m] of Object.entries(members)) {
        this.partyRuntime.addToRoster?.(id, (m as any).role ?? 'adventurer')
      }
      const starting = (config as any).starting_party ??
        Object.keys(members).slice(0, 4)
      this.partyRuntime.setActiveParty?.(starting)
    }

    this.tryMount('CameraFollow', {
      target_tag: 'party',
      lerp: 0.25,
      deadzone: [0.5, 0.5],
    })

    this.tryMount('HUD', {
      fields: [
        { mechanic: 'world_map_travel', field: 'current_region', label: 'REGION' },
        { archetype: 'party', component: 'Health', label: 'HP' },
        { singleton: 'gold', label: 'GP' },
      ],
      layout: 'corners',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.wmtRuntime = null
    this.partyRuntime = null
  }

  /** Public API — scene-manager glue calls this to drive travel. */
  travelTo(region: string): boolean {
    return this.wmtRuntime?.travelTo?.(region) ?? false
  }

  getCurrentRegion(): string {
    return this.wmtRuntime?.getCurrentRegion?.() ?? ''
  }

  getActiveParty(): string[] {
    return this.partyRuntime?.getActive?.() ?? []
  }

  private tryMount(type: string, params: Record<string, unknown>): any {
    const instance = {
      id: `${type}_${this.mechanics.length}`, type, params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) {
      this.mechanics.push(rt)
      return rt
    }
    return null
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: Object.entries(
            ((partyData as any).characters ?? (partyData as any).party ?? {}) as Record<string, any>,
          ).map(([id, c]) => ({ id, ...c })),
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
