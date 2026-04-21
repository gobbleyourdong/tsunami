/**
 * Stage scene — the brawler gameplay loop.
 *
 * Composes mechanics from @engine/mechanics per data/mechanics.json:
 *  - ComboAttacks (3-brawler combo chains from moves.json)
 *  - AttackFrames (startup/active/recovery per move)
 *  - WaveSpawner (position-gated enemy spawns from stages.json)
 *  - CameraFollow (locked-forward scroll + ring-arena-lock on boss gate)
 *  - PickupLoop (ground items: knife/pipe/chicken/jewels)
 *  - HUD (health per player, stage-progress, score, lives)
 *  - LoseOnZero (party KO = GameOver unless continues available)
 *  - WinOnCount (stage-clear counter)
 *  - SfxLibrary (hit/grab/throw/pickup/boss-stings)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import charactersData from '../../data/characters.json'
import enemiesData from '../../data/enemies.json'
import stagesData from '../../data/stages.json'
import movesData from '../../data/moves.json'
import pickupsData from '../../data/pickups.json'
import config from '../../data/config.json'

export class Stage {
  readonly name = 'stage'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private currentStage: string
  private currentCharacter: string

  constructor() {
    const stages = Object.keys((stagesData as any).stages ?? {})
    const chars = Object.keys((charactersData as any).characters ?? {})
    this.description = `Stage ${stages.length}× · ${chars.length} playable brawlers · Final Fight lineage`
    this.currentStage = (config as any).starting_stage ?? stages[0] ?? 'stage_1'
    this.currentCharacter = (config as any).starting_character ?? chars[0] ?? 'haymaker'
  }

  setup(): void {
    // ComboAttacks — read per-character moveset from moves.json.
    this.tryMount('ComboAttacks', {
      owner_tag: 'brawler',
      moveset_ref: `${this.currentCharacter}_moveset`,
      input_channel: 'player1',
    })

    // AttackFrames — startup/active/recovery per swing.
    this.tryMount('AttackFrames', {
      owner_tag: 'brawler',
      startup_frames: 3,
      active_frames: 4,
      recovery_frames: 8,
    })

    // WaveSpawner — position-gated enemy spawns (beat-em-up canonical).
    this.tryMount('WaveSpawner', {
      spawn_triggers: (stagesData as any).stages?.[this.currentStage]?.waves ?? [],
      enemy_pool: Object.keys((enemiesData as any).enemies ?? {}),
      mode: 'position_gated',
    })

    // CameraFollow — locked-forward scroll (no backtracking in beat-em-ups).
    // Also ring-arena-lock on boss: stage camera freezes until mid-boss dies.
    this.tryMount('CameraFollow', {
      target_tag: 'brawler',
      lerp: 0.15,
      deadzone: [1.5, 0.1],
      forward_only: true,
      lock_on_boss_gate: true,
    })

    this.tryMount('PickupLoop', {
      trigger_tag: 'ground_item',
      effect_on_collect: 'apply_pickup',
    })

    this.tryMount('HUD', {
      fields: [
        { archetype: 'brawler', component: 'Health', label: 'P1' },
        { singleton: 'lives',       label: 'LIVES' },
        { singleton: 'score',       label: 'SCORE' },
        { singleton: 'stage_name',  label: 'STAGE' },
      ],
      layout: 'top',
    })

    this.tryMount('LoseOnZero', {
      watch_archetype: 'brawler',
      watch_component: 'Health',
      aggregate: 'all_zero_no_continues',
    })

    this.tryMount('WinOnCount', {
      watch_singleton: 'stages_cleared',
      count_target: Object.keys((stagesData as any).stages ?? {}).length,
      count_condition: 'all_stages_cleared',
    })

    this.tryMount('SfxLibrary', {
      presets: {
        punch:         'sfxr_punch',
        kick:          'sfxr_kick',
        grab:          'sfxr_grab',
        throw:         'sfxr_throw',
        pickup_chicken: 'sfxr_chicken',
        pickup_weapon: 'sfxr_weapon_get',
        boss_sting:    'sfxr_boss_sting',
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

  loadStage(stageId: string): boolean {
    const stages = (stagesData as any).stages ?? {}
    if (!stages[stageId]) return false
    this.currentStage = stageId
    return true
  }

  selectCharacter(charId: string): boolean {
    const chars = (charactersData as any).characters ?? {}
    if (!chars[charId]) return false
    this.currentCharacter = charId
    return true
  }

  getCurrentStage(): string { return this.currentStage }
  getCurrentCharacter(): string { return this.currentCharacter }

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
            { id: this.currentCharacter, ...((charactersData as any).characters?.[this.currentCharacter] ?? {}) },
            ...Object.entries((enemiesData as any).enemies ?? {})
              .map(([id, e]) => ({ id, ...(e as any) })),
          ],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
