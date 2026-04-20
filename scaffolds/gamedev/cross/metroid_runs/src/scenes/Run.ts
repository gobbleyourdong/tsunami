/**
 * Run scene — procedurally-generated metroidvania run.
 *
 * Mounts 8 mechanics per JOB-W composition target. Key architectural
 * choreography:
 *
 *   - **ProceduralRoomChain** with a NEW seed each run (per-run reset)
 *   - **GatedTrigger** + **LockAndKey** for ability-gated rooms
 *     (ability must be held to open a gate — persistent across runs)
 *   - **PhysicsModifier** toggled by ability unlocks (double_jump
 *     changes gravity_scale briefly when activated)
 *   - **CheckpointProgression** marks the current-run's checkpoint,
 *     BUT abilities/boss_defeats carried by a scaffold-level save
 *     object that survives scene disposal + re-init
 *
 * The per-run-reset vs. persistent-progression split is encoded in
 * `rules.json::persistent_state_whitelist`. Room layout + HP + held
 * items wipe on death; abilities + boss_defeats + max_hp_upgrades do not.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import roomsData from '../../data/rooms.json'
import playerData from '../../data/player.json'
import enemiesData from '../../data/enemies.json'
import abilitiesData from '../../data/abilities.json'
import bossesData from '../../data/bosses.json'
import seedsData from '../../data/seeds.json'
import config from '../../data/config.json'

interface PersistentState {
  abilities: string[]
  boss_defeats: string[]
  max_hp_upgrades: number
  runs_completed: number
}

export class Run {
  readonly name = 'run'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private physicsRuntime: any = null
  private currentSeed: number

  // Scaffold-level persistent state — NOT disposed on teardown.
  // In production this would live on the save-data layer; here we
  // hold it on the Run instance to demonstrate the carry-over pattern.
  private static persistent: PersistentState = {
    abilities: [],
    boss_defeats: [],
    max_hp_upgrades: 0,
    runs_completed: 0,
  }

  constructor() {
    const rooms = Object.keys((roomsData as any).room_templates ?? {})
    const abilities = Object.keys((abilitiesData as any).abilities ?? {})
    this.description = `Metroid Runs — ${rooms.length} room templates, ${abilities.length} abilities, seed-determined layout`
    this.currentSeed = (config as any).first_run_seed ?? 1
  }

  setup(): void {
    // ProceduralRoomChain — fresh seed per run, different layout each time.
    this.tryMount('ProceduralRoomChain', {
      seed: this.currentSeed,
      room_templates_ref: 'rooms.json',
      default_pool_ref: 'default_template_pool',
      always_first_room_ref: 'always_first_room',
      chain_length: 12,
    })

    // LockAndKey — ability-item doors.
    this.tryMount('LockAndKey', {
      lock_tag: 'ability_door',
      key_source: 'persistent_abilities',
    })

    // GatedTrigger — conditional events (boss-unlock tied to ability count).
    this.tryMount('GatedTrigger', {
      trigger_tag: 'boss_gate',
      required_state: 'abilities_count',
      threshold: 3,
    })

    // ItemUse — consumables (health potions, run-scoped).
    this.tryMount('ItemUse', {
      inventory_component: 'Inventory',
      usable_tags: ['health_potion', 'bomb', 'key_card'],
    })

    // PhysicsModifier — ability-gated gravity/friction changes
    // (double_jump halves gravity briefly; dash boosts time_scale).
    this.physicsRuntime = this.tryMount('PhysicsModifier', {
      gravity_scale: 1.0,
      friction_scale: 1.0,
      time_scale: 1.0,
    })

    // CheckpointProgression — mid-run respawn. Wipes on death
    // EXCEPT the persistent-state fields preserved by this scaffold.
    this.tryMount('CheckpointProgression', {
      respawn_at: 'last_checkpoint',
      lives_component: 'Lives',
    })

    // BossPhases — boss drops an ability on first defeat; subsequent
    // runs skip the drop but re-encounter the phased fight.
    this.tryMount('BossPhases', {
      boss_archetype_tag: 'boss',
      phase_triggers: 'hp_threshold',
      first_defeat_drops_ability: true,
    })

    this.tryMount('HUD', {
      fields: [
        { archetype: 'player', component: 'Health', label: 'HP' },
        { singleton: 'run_time',         label: 'RUN' },
        { singleton: 'abilities_count',  label: 'ABILITIES' },
        { singleton: 'current_seed',     label: 'SEED' },
      ],
      layout: 'corners',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.physicsRuntime = null
  }

  // ---- Public API (per-run vs. persistent state) ----

  /** Start a new run with a fresh seed. Per-run state wipes; persistent
   *  state (abilities / boss_defeats / max_hp_upgrades) survives. */
  newRun(seed?: number): void {
    this.currentSeed = seed ?? (Date.now() & 0x7fffffff)
    Run.persistent.runs_completed += 1
    this.teardown()
    this.setup()
  }

  /** Unlock an ability — persists across runs. */
  unlockAbility(id: string): boolean {
    if (!(id in ((abilitiesData as any).abilities ?? {}))) return false
    if (Run.persistent.abilities.includes(id)) return false
    Run.persistent.abilities.push(id)
    return true
  }

  /** Record a boss defeat — persists. */
  recordBossDefeat(id: string): void {
    if (!Run.persistent.boss_defeats.includes(id)) {
      Run.persistent.boss_defeats.push(id)
    }
  }

  // ---- Read API ----

  getCurrentSeed(): number { return this.currentSeed }
  getPersistentState(): Readonly<PersistentState> { return { ...Run.persistent } }
  hasAbility(id: string): boolean { return Run.persistent.abilities.includes(id) }

  /** Reset persistent state — for test teardown only. */
  static resetPersistent(): void {
    Run.persistent = { abilities: [], boss_defeats: [], max_hp_upgrades: 0, runs_completed: 0 }
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
          entities: [
            { id: 'player', ...((playerData as any).player ?? {}) },
            ...Object.entries((enemiesData as any).enemies ?? {})
              .map(([id, e]) => ({ id, ...(e as any) })),
            ...Object.entries((bossesData as any).bosses ?? {})
              .map(([id, b]) => ({ id, ...(b as any) })),
          ],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
