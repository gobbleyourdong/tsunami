/**
 * Match scene — cross-genre canary #3.
 *
 * Mounts EXACTLY 8 mechanics per JOB-Q Proposition 3. Architectural
 * invariants exercised here that magic_hoops + ninja_garden don't:
 *
 *   1. **RhythmTrack × AttackFrames coupling** — AttackFrames reads
 *      beat-phase from RhythmTrack via `beat_source_ref`; damage
 *      multiplier applies at hit-resolve time based on on-beat/off-beat
 *      window.
 *   2. **Beat-fraction time units** — moves.json expresses startup/
 *      active/recovery in `startup_beats` instead of frames. Tests that
 *      AttackFrames accepts alternate time-units at runtime.
 *   3. **Mechanic execution-order determinism** — RhythmTrack must tick
 *      before AttackFrames (otherwise AttackFrames reads stale beat state).
 *      Mounting order encodes this; registry doesn't enforce it but the
 *      canary test asserts the order is preserved.
 *
 * If these hold without new runtime types, the framework handles
 * time-coupled cross-mechanic choreography correctly.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import charactersData from '../../data/characters.json'
import movesData from '../../data/moves.json'
import stagesData from '../../data/stages.json'
import beatmapsData from '../../data/beatmaps.json'
import config from '../../data/config.json'

export class Match {
  readonly name = 'match'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private mountOrder: string[] = []

  constructor() {
    const fighters = Object.keys((charactersData as any).characters ?? {})
    const stages = Object.keys((stagesData as any).stages ?? {})
    this.description = `Rhythm Fighter — ${fighters.length} fighters × ${stages.length} stages (fighting + rhythm)`
  }

  setup(): void {
    const matchup = (config as any).starting_matchup ?? ['ryu_beat', 'ken_beat']
    const p1 = matchup[0]
    const p2 = matchup[1]

    // ---- Beat clock FIRST — other mechanics read beat-phase from it ----
    this.tryMount('RhythmTrack', {
      beatmap_ref: 'crossbeat_120bpm',
      bgm_ref: 'crossbeat_120bpm',
      on_beat_window_beats: (config as any).match_rules?.on_beat_window_beats ?? 0.125,
      time_signature: [4, 4],
    })

    // ---- Rhythm-coupled damage frames ----
    // One AttackFrames per fighter. `beat_source_ref` ties damage-multiplier
    // application back to the beat_clock's current_beat_phase. timing_unit=
    // 'beats' signals that moves.json startup_beats/active_beats fields
    // should be consumed as-is (not converted from frames).
    for (const pid of [p1, p2]) {
      this.tryMount('AttackFrames', {
        owner_tag: `fighter_${pid === p1 ? 'p1' : 'p2'}`,
        timing_unit: 'beats',
        on_beat_damage_multiplier: (config as any).match_rules?.on_beat_damage_multiplier ?? 1.5,
        off_beat_damage_multiplier: (config as any).match_rules?.off_beat_damage_multiplier ?? 0.5,
        beat_source_ref: 'beat_clock',
      })
    }

    // ---- Combo input → move dispatch ----
    for (const pid of [p1, p2]) {
      const char = (charactersData as any).characters[pid]
      if (!char) continue
      this.tryMount('ComboAttacks', {
        owner_id: pid,
        moveset_ref: char.move_list_ref,
        input_channel: pid === p1 ? 'player1' : 'player2',
      })
    }

    // ---- Rhythm-bonus status stack ----
    // On-beat hit adds a rhythm_bonus stack (capped at 3); decays on next beat.
    this.tryMount('StatusStack', {
      status_id: 'rhythm_bonus',
      max_stacks: 3,
      decay_on_beat: true,
      apply_on_event: 'on_beat_hit',
    })

    // ---- BGM + beat-synced SFX ----
    this.tryMount('ChipMusic', {
      base_track_ref: 'crossbeat_120bpm',
      bpm: 120,
      loop: true,
      drives_beat_clock: true,
    })

    this.tryMount('SfxLibrary', {
      presets: {
        on_beat_hit:  'sfxr_percussive_hit',
        off_beat_hit: 'sfxr_muted_hit',
        block:        'sfxr_block',
        whiff:        'sfxr_whiff',
        round_start:  'sfxr_round_start',
      },
    })

    // ---- HUD + win condition ----
    this.tryMount('HUD', {
      fields: [
        { archetype: p1, component: 'Health', label: 'P1' },
        { archetype: p2, component: 'Health', label: 'P2' },
        { mechanic: 'beat_clock', field: 'current_beat_phase', label: 'BEAT' },
        { mechanic: 'rhythm_bonus_stack', field: 'stacks', label: 'BONUS' },
      ],
      layout: 'corners',
    })

    this.tryMount('WinOnCount', {
      watch_singleton: 'rounds_won_p1',
      count_target: 2,
      count_condition: 'rounds_best_of_3',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.mountOrder.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`, type, params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) {
      this.mechanics.push(rt)
      this.mountOrder.push(type)
    }
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: Object.entries((charactersData as any).characters ?? {})
            .map(([id, c]) => ({ id, ...(c as any) })),
        }),
      },
      config: { mode: (config as any).config?.mode ?? '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }

  /** Test accessor: mount order (canary asserts RhythmTrack before AttackFrames). */
  getMountOrder(): string[] { return [...this.mountOrder] }
}
