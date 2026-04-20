/**
 * Match scene — cross-genre canary #2.
 *
 * Mounts EXACTLY 12 mechanics from `@engine/mechanics`, drawing from
 * three genre heritages simultaneously to exercise architectural
 * composition invariants that magic_hoops doesn't cover:
 *
 *   - **Sandbox** (Terraria):       ProceduralRoomChain, InventoryCombine
 *   - **Action**  (Ninja Gaiden):   ComboAttacks, AttackFrames, PhysicsModifier
 *   - **Stealth** (Shinobi/MGS):    VisionCone, ItemUse, LockAndKey
 *   - **Universal scene glue**:     BossPhases, CheckpointProgression, CameraFollow, HUD
 *
 * Architectural-invariant assertions (enforced by ninja_garden_canary.test.ts):
 *   1. Every tryMount() name is registered in the mechanic registry.
 *   2. Scene imports ONLY from @engine/mechanics (no relative paths to
 *      engine internals, no new mechanic TYPES invented).
 *   3. Composition exercises ≥3 genre heritages (sandbox + action +
 *      stealth — verified by the canary test's heritage-coverage check).
 *
 * If this fails to compose cleanly, the Layer 1/2 abstractions are
 * leaking and need fixing — not this scene.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import playerData from '../../data/player.json'
import enemiesData from '../../data/enemies.json'
import biomesData from '../../data/biomes.json'
import toolsData from '../../data/tools.json'
import bossesData from '../../data/bosses.json'
import arenaData from '../../data/arena.json'
import rulesData from '../../data/rules.json'
import config from '../../data/config.json'

export class Match {
  readonly name = 'match'
  description = ''
  private mechanics: MechanicRuntime[] = []

  constructor() {
    const enemies = Object.keys((enemiesData as any).enemies ?? {})
    const biomes = Object.keys((biomesData as any).biomes ?? {})
    const bosses = Object.keys((bossesData as any).bosses ?? {})
    this.description = `Ninja Garden — ${biomes.length} biomes × ${enemies.length} enemies × ${bosses.length} bosses (sandbox+action+stealth)`
  }

  setup(): void {
    // ---- Sandbox heritage ---------------------------------------------------
    // Terraria's procedural chunk generation + persistent modifications.
    this.tryMount('ProceduralRoomChain', {
      seed_field: 'world_seed',
      biomes_ref: 'biomes.json',
      biome_progression_field: 'biome_progression_default',
      world_size_tiles_field: 'world_size_tiles',
      persist_modifications: (arenaData as any).arena?.procedural_terrain_persistence ?? true,
    })

    // InventoryCombine — crafting bench recipes (Terraria-style).
    this.tryMount('InventoryCombine', {
      recipe_source: 'data/tools.json',
      target_inventory: 'player',
      recipe_unlock_event: 'craft_recipes_known',
    })

    // ---- Action heritage ----------------------------------------------------
    // PhysicsModifier — gravity tuned for wall-grab / double-jump feel.
    this.tryMount('PhysicsModifier', {
      gravity_scale: 0.95,
      friction_scale: 1.0,
      time_scale: 1.0,
    })

    // ComboAttacks — shuriken / kunai / kusarigama chain combos.
    this.tryMount('ComboAttacks', {
      owner_id: 'shinobi_player',
      moveset_ref: 'shinobi_ground_combos',
      input_channel: 'player1',
    })

    // AttackFrames — startup/active/recovery on katana + ranged tools.
    this.tryMount('AttackFrames', {
      owner_tag: 'shinobi',
      startup_frames: 4,
      active_frames: 3,
      recovery_frames: 8,
    })

    // ---- Stealth heritage ---------------------------------------------------
    // VisionCone — enemy patrol FOV + alert_threshold (MGS-style).
    this.tryMount('VisionCone', {
      fov_deg: 80,
      range: 7,
      alert_threshold: 0.55,
      degrade_on_break_los: true,
    })

    // ItemUse — smoke bomb, grappling hook, silenced shuriken dispatch.
    this.tryMount('ItemUse', {
      inventory_component: 'Inventory',
      usable_tags: ['shuriken', 'kunai', 'smoke_bomb', 'grappling_hook', 'kusarigama'],
    })

    // LockAndKey — shrine gates that open only after collecting key-item
    // OR after all guards in zone are silently eliminated.
    this.tryMount('LockAndKey', {
      lock_tag: 'shrine_gate',
      key_tag: 'shrine_key',
    })

    // ---- Universal scene glue -----------------------------------------------
    // BossPhases — three bosses with multi-phase patterns (ogre_king /
    // shadow_shogun / sky_dragon per bosses.json).
    this.tryMount('BossPhases', {
      boss_archetype_tag: 'boss',
      phase_triggers: 'hp_threshold',
    })

    // CheckpointProgression — respawn at last-crafted-bed / shrine altar.
    this.tryMount('CheckpointProgression', {
      respawn_at: 'last_checkpoint',
      lives_component: 'Lives',
    })

    // CameraFollow — sidescroller rig on the player with horizontal lead.
    this.tryMount('CameraFollow', {
      target_tag: 'player',
      lerp: 0.2,
      deadzone: [1.2, 0.4],
    })

    // HUD — chakra bar + stealth meter + day/night indicator + inventory.
    this.tryMount('HUD', {
      fields: [
        { archetype: 'shinobi_player', component: 'Health',         label: 'HP' },
        { archetype: 'shinobi_player', component: "Resource.chakra", label: 'CHAKRA' },
        { archetype: 'shinobi_player', component: "Resource.stealth_meter", label: 'STEALTH' },
        { singleton: 'day_phase',      label: 'PHASE' },
        { singleton: 'biome',          label: 'ZONE' },
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
            { id: 'shinobi_player', ...((playerData as any).player ?? {}) },
            ...Object.entries((enemiesData as any).enemies ?? {})
              .map(([id, e]) => ({ id, ...(e as any) })),
            ...Object.entries((bossesData as any).bosses ?? {})
              .map(([id, b]) => ({ id, ...(b as any) })),
          ],
        }),
      },
      config: { mode: (config as any).config?.mode ?? '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }

  /** Test accessor: rules-driven win condition kind (used by canary test). */
  getWinConditionKind(): string {
    return ((rulesData as any).rules?.win_condition?.kind as string) ?? ''
  }
}
