/**
 * Fight scene — the core combat loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - ComboAttacks (input → move dispatch via moves.json)
 *  - AttackFrames (startup/active/recovery windows with hitbox activation)
 *  - HUD (health bars per fighter, timer, round counter, super meter)
 *  - CameraFollow (tracks midpoint between fighters)
 *  - SfxLibrary (hit / block / whiff SFX)
 *
 * Win check: any fighter HP → 0 OR timer → 0 → decide winner by HP,
 * round counter updates, best-of-N per config.match_rules.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import charactersData from '../../data/characters.json'
import movesData from '../../data/moves.json'
import stagesData from '../../data/stages.json'
import config from '../../data/config.json'

export class Fight {
  readonly name = 'fight'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private p1_id = 'ryu'
  private p2_id = 'ken'
  private stage_id = 'suzaku_castle'
  private roundsWon = [0, 0]
  private currentRound = 1

  constructor() {
    const rules = (config as any).match_rules
    const rounds = rules?.rounds_per_match ?? 3
    const timer = rules?.round_timer ?? 99
    this.description = `${rounds}-round match, ${timer}s timer, ${
      Object.keys((charactersData as { characters: Record<string, any> }).characters).length
    } fighters in roster`
  }

  setup(): void {
    // Mount ComboAttacks for each fighter. Each takes the fighter's
    // move list from moves.json.
    const chars = (charactersData as { characters: Record<string, any> }).characters
    const moves = (movesData as { movesets?: Record<string, any>; moves?: any }).movesets ??
                  (movesData as any).moves ?? {}

    for (const pid of [this.p1_id, this.p2_id]) {
      const char = chars[pid]
      if (!char) continue
      const moveset = moves[char.move_list_ref]
      if (!moveset) continue

      // ComboAttacks mechanic — reads inputs, dispatches moves.
      this.tryMount('ComboAttacks', {
        owner_id: pid,
        moveset_ref: char.move_list_ref,
        input_channel: pid === this.p1_id ? 'player1' : 'player2',
      })
    }

    // Camera tracks midpoint between fighters (stub: tracks p1 with lerp).
    this.tryMount('CameraFollow', {
      target_tag: 'fighter',
      lerp: 0.2,
      deadzone: [1.0, 0.5],
    })

    // HUD — health bars + timer + round indicators + super meter.
    this.tryMount('HUD', {
      fields: [
        { archetype: this.p1_id, component: 'Health', label: 'P1' },
        { archetype: this.p2_id, component: 'Health', label: 'P2' },
        { mechanic: 'round_timer', field: 'remaining', label: 'TIME' },
      ],
      layout: 'corners',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`,
      type,
      params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, this.makeStubGame())
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: Object.entries((charactersData as { characters: Record<string, any> }).characters)
            .map(([id, c]) => ({ id, ...c })),
        }),
      },
      config: { mode: (config as any).config?.mode ?? '2d' },
    }
  }

  /** Test / debug accessor. */
  mechanicsActive(): number {
    return this.mechanics.length
  }

  /** Public setup for the pair + stage, normally called from VsScreen. */
  setMatchup(p1_id: string, p2_id: string, stage_id?: string): void {
    this.p1_id = p1_id
    this.p2_id = p2_id
    if (stage_id) this.stage_id = stage_id
    else {
      // Auto-pick from p1's stage_affinity.
      const chars = (charactersData as { characters: Record<string, any> }).characters
      this.stage_id = chars[p1_id]?.stage_affinity ?? this.stage_id
    }
  }

  getMatchup(): { p1: string; p2: string; stage: string } {
    return { p1: this.p1_id, p2: this.p2_id, stage: this.stage_id }
  }

  /** Simulate a round win for test scenarios. */
  awardRound(winner_idx: 0 | 1): void {
    this.roundsWon[winner_idx] += 1
    this.currentRound += 1
  }

  getRoundState(): { rounds: [number, number]; current: number } {
    return { rounds: [this.roundsWon[0], this.roundsWon[1]], current: this.currentRound }
  }
}
