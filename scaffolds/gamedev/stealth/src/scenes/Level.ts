/**
 * Level scene — the stealth gameplay loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - VisionCone (guard detection — fov_deg, range, alert_threshold)
 *  - HotspotMechanic (hiding spots + vent-crawl + body-drag drop zones)
 *  - LockAndKey (keycards / lockpick gates)
 *  - ItemUse (silenced pistol, smoke grenade, throw rock, stun baton)
 *  - PickupLoop (ammo + keycards + collectibles)
 *  - HUD (health + stealth meter + alert level + inventory)
 *  - LoseOnZero (player Health → 0 OR alarm_tolerance exceeded)
 *  - ChipMusic + SfxLibrary (ambient theme + detection-sting + footstep)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import levelsData from '../../data/levels.json'
import guardsData from '../../data/guards.json'
import toolsData from '../../data/tools.json'
import playerData from '../../data/player.json'
import config from '../../data/config.json'

export class Level {
  readonly name = 'level'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private currentLevel: string
  private alertLevel: 'unaware' | 'suspicious' | 'alerted' = 'unaware'

  constructor() {
    const levels = Object.keys((levelsData as any).levels ?? {})
    const guards = Object.keys((guardsData as any).guards ?? {})
    this.description = `Stealth level — ${levels.length} maps, ${guards.length} guard archetypes`
    this.currentLevel = (config as any).starting_level ?? levels[0] ?? 'mission_1'
  }

  setup(): void {
    // VisionCone — one instance per guard archetype. Drives detection.
    this.tryMount('VisionCone', {
      fov_deg: 90,
      range: 6,
      alert_threshold: 0.6,
      degrade_on_break_los: true,
    })

    // HotspotMechanic — hiding spots + vent entries + ladder climbs.
    this.tryMount('HotspotMechanic', {
      trigger_tag: 'hotspot',
      effect: 'enter_hiding',
    })

    this.tryMount('LockAndKey', {
      lock_tag: 'locked_door',
      key_tag: 'keycard',
    })

    this.tryMount('ItemUse', {
      inventory_component: 'Inventory',
      usable_tags: ['silenced_pistol', 'smoke_grenade', 'throw_rock',
                    'stun_baton', 'lockpick', 'body_drag'],
    })

    this.tryMount('PickupLoop', {
      trigger_tag: 'pickup',
      effect_on_collect: 'apply_pickup',
    })

    this.tryMount('HUD', {
      fields: [
        { archetype: 'player', component: 'Health', label: 'HEALTH' },
        { singleton: 'stealth_meter', label: 'STEALTH' },
        { singleton: 'alert_level',   label: 'ALERT' },
        { singleton: 'inventory',     label: 'ITEMS' },
      ],
      layout: 'bottom',
    })

    this.tryMount('LoseOnZero', {
      watch_archetype: 'player',
      watch_component: 'Health',
      aggregate: 'any_zero',
    })

    this.tryMount('ChipMusic', {
      base_track: 'ambient_tension',
      bpm: 90,
      loop: true,
    })

    this.tryMount('SfxLibrary', {
      presets: {
        footstep_soft:    'sfxr_footstep_soft',
        footstep_loud:    'sfxr_footstep_loud',
        detection_sting:  'sfxr_detection_sting',
        takedown:         'sfxr_takedown',
        body_drag:        'sfxr_drag',
        silenced_shot:    'sfxr_shot_silenced',
      },
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  // ---- Public API ----

  loadLevel(levelId: string): boolean {
    const levels = (levelsData as any).levels ?? {}
    if (!levels[levelId]) return false
    this.currentLevel = levelId
    this.alertLevel = 'unaware'
    return true
  }

  getCurrentLevel(): string { return this.currentLevel }
  getAlertLevel(): string { return this.alertLevel }

  /** Called by VisionCone when a guard spots the player. */
  onPlayerSpotted(): void {
    if (this.alertLevel === 'unaware') this.alertLevel = 'suspicious'
    else if (this.alertLevel === 'suspicious') this.alertLevel = 'alerted'
  }

  private tryMount(type: string, params: Record<string, unknown>): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`, type, params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: [
            { id: 'player', ...((playerData as any).player ?? {}) },
            ...Object.entries((guardsData as any).guards ?? {})
              .map(([id, g]) => ({ id, ...(g as any) })),
          ],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
