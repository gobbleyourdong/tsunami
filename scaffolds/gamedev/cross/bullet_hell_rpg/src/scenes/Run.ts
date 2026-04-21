/**
 * Run scene — bullet-hell RPG session.
 *
 * Cross-genre composition from @engine/mechanics. ZERO new primitives.
 *
 * Heritage mix (each tryMount tagged with origin genre):
 *   bullet-hell (arcade): BulletPattern, WaveSpawner, BossPhases, ScoreCombos, Difficulty
 *   fighting:             AttackFrames (player shot hitbox activation)
 *   rpg:                  LevelUpProgression, EquipmentLoadout, StatusStack
 *   action/universal:     CameraFollow, HUD, LoseOnZero, CheckpointProgression
 *
 * Data-driven:
 *   data/player.json       — pilot archetype + starting loadout
 *   data/enemies.json      — 5 enemy archetypes with BulletPattern params
 *   data/waves.json        — spawn schedule (WaveSpawner)
 *   data/bosses.json       — boss with BossPhases
 *   data/equipment.json    — 5 equippable items (EquipmentLoadout)
 *   data/progression.json  — xp curve + level rewards + StatusStack effects
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import playerData from '../../data/player.json'
import enemiesData from '../../data/enemies.json'
import wavesData from '../../data/waves.json'
import bossesData from '../../data/bosses.json'
import equipmentData from '../../data/equipment.json'
import progressionData from '../../data/progression.json'

export class Run {
  readonly name = 'run'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private score = 0
  private xp = 0
  private level = 1

  constructor() {
    const enemies = (enemiesData as { enemies: Record<string, unknown> }).enemies
    const bosses = (bossesData as { bosses: Record<string, unknown> }).bosses
    const equip = (equipmentData as { equipment: Record<string, unknown> }).equipment
    this.description =
      `${Object.keys(enemies).length} enemy types · ${Object.keys(bosses).length} boss · ` +
      `${Object.keys(equip).length} equipment · ${(wavesData as any).waves.length} waves`
  }

  setup(): void {
    const stubGame = this.makeStubGame()

    // 1. BulletPattern — one pattern mount per enemy archetype (bullet-hell heritage).
    const enemies = (enemiesData as { enemies: Record<string, any> }).enemies
    for (const [id, e] of Object.entries(enemies)) {
      this.tryMount('BulletPattern', {
        emitter_id: id,
        pattern: e.pattern.kind,
        bullets_per_burst: e.pattern.bullets_per_burst,
        bullet_speed: e.pattern.bullet_speed,
        interval_ms: e.pattern.interval_ms,
      }, stubGame)
    }

    // 2. WaveSpawner — drive encounter cadence (bullet-hell / arcade heritage).
    this.tryMount('WaveSpawner', {
      waves: (wavesData as any).waves,
      end_condition: (wavesData as any).end_condition,
    }, stubGame)

    // 3. BossPhases — boss battle with phase escalation (bullet-hell heritage).
    const boss = (bossesData as any).bosses.the_archon
    this.tryMount('BossPhases', {
      boss_archetype: 'archon',
      phases: boss.phases,
      telegraph_sec: boss.telegraph_sec,
    }, stubGame)

    // 4. AttackFrames — player's own shots have hitbox activation timelines
    //    (fighting heritage: same primitive used in Fight.ts for jab/punch).
    this.tryMount('AttackFrames', {
      owner_id: 'player_1',
      attack: 'spread_shot',
      startup_frames: 2,
      active_frames: 4,
      recovery_frames: 6,
    }, stubGame)

    // 5. ScoreCombos — chain-scoring (arcade heritage).
    this.tryMount('ScoreCombos', {
      base_multiplier: 1.0,
      chain_window_ms: 2000,
      max_multiplier: 8.0,
    }, stubGame)

    // 6. LevelUpProgression — xp → level, unlock new equipment (rpg heritage).
    this.tryMount('LevelUpProgression', {
      xp_curve: (progressionData as any).progression.xp_curve,
      rewards: (progressionData as any).progression.level_rewards,
    }, stubGame)

    // 7. EquipmentLoadout — slot-based weapon/armor swap (rpg heritage).
    this.tryMount('EquipmentLoadout', {
      owner_id: 'player_1',
      slots: ['primary_weapon', 'secondary_weapon', 'armor'],
      initial: (playerData as any).player.starting_loadout,
      catalog_ref: 'equipment.equipment',
    }, stubGame)

    // 8. StatusStack — focus / shield / overdrive buffs (rpg heritage).
    this.tryMount('StatusStack', {
      owner_id: 'player_1',
      effects: (progressionData as any).progression.status_effects,
    }, stubGame)

    // 9. CameraFollow — tracks the player (action/universal heritage).
    this.tryMount('CameraFollow', {
      target_tag: 'player',
      lerp: 0.15,
      deadzone: [0.5, 2.0],
    }, stubGame)

    // 10. HUD — score + level + HP + mana (universal).
    this.tryMount('HUD', {
      fields: [
        { archetype: 'pilot', component: 'Health', label: 'HP' },
        { archetype: 'pilot', component: 'Score',  label: 'SCORE' },
        { mechanic: 'level_up_progression', field: 'level', label: 'LV' },
        { mechanic: 'score_combos', field: 'multiplier', label: 'x' },
      ],
      layout: 'top',
    }, stubGame)

    // 11. Difficulty — ramp over run time (bullet-hell heritage: rank system).
    this.tryMount('Difficulty', {
      drive: 'time',
      easy: { spawnRateMul: 0.8, bulletSpeedMul: 0.9 },
      hard: { spawnRateMul: 1.5, bulletSpeedMul: 1.2 },
      max_level: 3,
    }, stubGame)

    // 12. LoseOnZero — KO on 0 HP (universal).
    this.tryMount('LoseOnZero', {
      component: 'Health',
      on_archetype: 'pilot',
    }, stubGame)

    // 13. CheckpointProgression — respawn at last checkpoint (action heritage).
    this.tryMount('CheckpointProgression', {
      respawn_delay_sec: 2,
      mode: 'respawn_at_checkpoint',
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
          entities: [{ id: 'player_1', ...(playerData as any).player }],
        }),
      },
      config: { mode: '2d' },
    }
  }

  /** Test accessor — how many mechanics actually mounted. */
  mechanicsActive(): number { return this.mechanics.length }

  /** Test: simulate destroying an enemy. */
  registerKill(score_value: number, xp_value: number): void {
    this.score += score_value
    this.xp += xp_value
  }

  getStats(): { score: number; xp: number; level: number } {
    return { score: this.score, xp: this.xp, level: this.level }
  }
}
