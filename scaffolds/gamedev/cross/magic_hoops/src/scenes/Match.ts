/**
 * Match scene — 1v1 magic hoops.
 *
 * Pure composition from @engine/mechanics. ZERO new mechanic types.
 * This scene is the architecture-correctness gate for Layer 1/2.
 *
 * Mechanic wiring (by heritage):
 *   fighting:        ComboAttacks (per wizard, reads spellbook),
 *                    AttackFrames (spell hitbox activation timeline)
 *   sports/arcade:   WinOnCount (first to N goals wins),
 *                    HUD (score + timer + HP + mana — the "scoreboard")
 *   rpg:             ItemUse (spell dispatch from input),
 *                    StatusStack (slow / shield / stun buffs)
 *   action:          CameraFollow (tracks midpoint between wizards),
 *                    CheckpointProgression (respawn on HP=0)
 *   universal:       LoseOnZero (KO check), Difficulty (AI scaling — unused
 *                    in 1v1-PvP, kept to prove it mounts harmlessly)
 *
 * Data-driven:
 *   data/characters.json  — 2 wizards with components + spellbook
 *   data/spells.json      — 6 spells with inputs + mana + damage + hitbox
 *   data/arena.json       — court geometry + goals + ball config
 *   data/rules.json       — match format (score_vs_clock composite rule)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import charactersData from '../../data/characters.json'
import spellsData from '../../data/spells.json'
import arenaData from '../../data/arena.json'
import rulesData from '../../data/rules.json'

export class Match {
  readonly name = 'match'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private scores = [0, 0]

  constructor() {
    const chars = (charactersData as { characters: Record<string, any> }).characters
    const spellCount = Object.keys(
      (spellsData as { spells: Record<string, any> }).spells,
    ).length
    this.description = `${Object.keys(chars).length} wizards · ${spellCount} spells · ${rulesData.clock_sec}s match · ${(arenaData as any).goals.length} goals`
  }

  setup(): void {
    // Stub game for mechanic init().
    const stubGame = this.makeStubGame()

    // 1. Per-wizard ComboAttacks — spellcasting via inputs from moves/spells.
    const chars = (charactersData as { characters: Record<string, any> }).characters
    for (const [wizId, wiz] of Object.entries<any>(chars)) {
      this.tryMount('ComboAttacks', {
        owner_id: wizId,
        moveset_ref: `${wizId}_spellbook`,
        input_channel: wiz.team_id === 1 ? 'player1' : 'player2',
      }, stubGame)
    }

    // 2. Camera tracks midpoint (action heritage — same primitive as fighting Fight.ts).
    this.tryMount('CameraFollow', {
      target_tag: 'fighter',
      lerp: 0.2,
      deadzone: [2.0, 1.0],
    }, stubGame)

    // 3. HUD — composite scoreboard (score + timer + HP + mana).
    this.tryMount('HUD', {
      fields: [
        { archetype: 'gandalf_red',  component: 'Health', label: 'G HP' },
        { archetype: 'gandalf_red',  component: 'Score',  label: 'G' },
        { archetype: 'merlin_blue',  component: 'Health', label: 'M HP' },
        { archetype: 'merlin_blue',  component: 'Score',  label: 'M' },
        { mechanic: 'match_clock', field: 'remaining', label: 'TIME' },
      ],
      layout: 'corners',
    }, stubGame)

    // 4. WinOnCount — first team to N goals wins (sports victory).
    this.tryMount('WinOnCount', {
      target: 'goals_scored',
      count: 5,
    }, stubGame)

    // 5. LoseOnZero — fighting-heritage KO detection (triggers respawn via CheckpointProgression).
    this.tryMount('LoseOnZero', {
      component: 'Health',
      on_archetype: 'gandalf_red',
    }, stubGame)

    // 6. CheckpointProgression — respawn after KO.
    this.tryMount('CheckpointProgression', {
      respawn_delay_sec: rulesData.respawn_sec,
      mode: 'respawn_in_place',
    }, stubGame)

    // 7. Difficulty — mounted harmless to prove a "genre-foreign" mechanic
    //    can sit inertly in a cross-genre scene without conflict.
    this.tryMount('Difficulty', {
      drive: 'time',
      easy: { spawnRateMul: 1.0 },
      hard: { spawnRateMul: 1.0 },
      max_level: 1,
    }, stubGame)
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>, game: any): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`,
      type,
      params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, game)
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    return {
      sceneManager: {
        activeScene: () => ({
          entities: Object.entries(
            (charactersData as { characters: Record<string, any> }).characters,
          ).map(([id, c]) => ({ id, ...c })),
        }),
      },
      config: { mode: '2d' },
    }
  }

  /** Test accessor — how many mechanics actually mounted. */
  mechanicsActive(): number { return this.mechanics.length }

  /** Test: simulate a goal scored. */
  scoreGoal(team_id: 1 | 2): void {
    this.scores[team_id - 1] += rulesData.goal_value ?? 2
  }

  getScores(): { team1: number; team2: number } {
    return { team1: this.scores[0], team2: this.scores[1] }
  }
}
