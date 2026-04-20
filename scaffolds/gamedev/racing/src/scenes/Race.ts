/**
 * Race scene — the racing gameplay loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - CheckpointProgression (lap counting + mid-track respawn if off-track)
 *  - CameraFollow (vehicle-anchored camera with look-ahead lerp)
 *  - PickupLoop (kart-style boost + shell + banana OR sim tuning parts)
 *  - WinOnCount (finishing N laps = race complete)
 *  - LoseOnZero (dnf_timer → 0 = race failed)
 *  - HUD (lap counter + position + time + speed)
 *  - ChipMusic + SfxLibrary (race theme + engine sfx + impact)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import tracksData from '../../data/tracks.json'
import vehiclesData from '../../data/vehicles.json'
import racersData from '../../data/racers.json'
import config from '../../data/config.json'

export class Race {
  readonly name = 'race'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private currentTrack: string
  private currentVehicle: string
  private currentLap = 0
  private position = 1

  constructor() {
    const tracks = Object.keys((tracksData as any).tracks ?? {})
    const vehicles = Object.keys((vehiclesData as any).vehicles ?? {})
    this.description = `Racing — ${tracks.length} tracks, ${vehicles.length} vehicles`
    this.currentTrack = (config as any).starting_track ?? tracks[0] ?? 'circuit_1'
    this.currentVehicle = (config as any).starting_vehicle ??
                          (racersData as any).racers?.player?.vehicle ??
                          vehicles[0] ?? 'hatchback'
  }

  setup(): void {
    // CheckpointProgression — lap counter drives WinOnCount.
    this.tryMount('CheckpointProgression', {
      respawn_at: 'last_checkpoint',
      lap_count_component: 'Lap',
    })

    this.tryMount('CameraFollow', {
      target_tag: 'player_vehicle',
      lerp: 0.15,
      deadzone: [0.3, 0.3],
      look_ahead: 3,
    })

    this.tryMount('PickupLoop', {
      trigger_tag: 'powerup_box',
      effect_on_collect: 'grant_random_powerup',
    })

    this.tryMount('WinOnCount', {
      watch_singleton: 'laps_complete',
      count_target: (config as any).laps_per_race ?? 3,
      count_condition: 'crossed_finish',
    })

    this.tryMount('LoseOnZero', {
      watch_singleton: 'dnf_timer',
      aggregate: 'zero',
    })

    this.tryMount('HUD', {
      fields: [
        { singleton: 'laps_complete', label: 'LAP' },
        { singleton: 'position',      label: 'POS' },
        { singleton: 'race_time',     label: 'TIME' },
        { singleton: 'current_speed', label: 'SPEED' },
      ],
      layout: 'corners',
    })

    this.tryMount('ChipMusic', {
      base_track: 'race_theme',
      bpm: 160,
      loop: true,
    })

    this.tryMount('SfxLibrary', {
      presets: {
        engine_idle:   'sfxr_engine_idle',
        engine_rev:    'sfxr_engine_rev',
        collision:     'sfxr_collision',
        boost:         'sfxr_boost',
        checkpoint:    'sfxr_checkpoint',
        lap_complete:  'sfxr_lap_complete',
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

  loadTrack(trackId: string): boolean {
    const tracks = (tracksData as any).tracks ?? {}
    if (!tracks[trackId]) return false
    this.currentTrack = trackId
    this.currentLap = 0
    return true
  }

  selectVehicle(vehicleId: string): boolean {
    const vehicles = (vehiclesData as any).vehicles ?? {}
    if (!vehicles[vehicleId]) return false
    this.currentVehicle = vehicleId
    return true
  }

  getCurrentTrack(): string { return this.currentTrack }
  getCurrentVehicle(): string { return this.currentVehicle }
  getCurrentLap(): number { return this.currentLap }
  getPosition(): number { return this.position }

  /** Called by CheckpointProgression on lap-close. */
  onLapComplete(): void { this.currentLap += 1 }

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
          entities: Object.entries((racersData as any).racers ?? {})
            .map(([id, r]) => ({ id, ...(r as any) })),
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
