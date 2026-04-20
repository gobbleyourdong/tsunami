/**
 * Level scene — the FPS gameplay loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - BulletPattern (player weapon projectiles)
 *  - WaveSpawner (enemy spawn waves on trigger zones)
 *  - AttackFrames (hitscan/projectile windup + active frames)
 *  - PickupLoop (ammo + medkit + armor shards)
 *  - ItemUse (use pickup effects like medkit-heal, berserk)
 *  - LockAndKey (red/blue/yellow keycards gate doors)
 *  - CameraFollow (first-person camera — lerp 0, target the player)
 *  - HUD (health + armor + ammo per weapon + crosshair + keys held)
 *  - LoseOnZero (health → 0 = game over)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import weaponsData from '../../data/weapons.json'
import enemiesData from '../../data/enemies.json'
import levelsData from '../../data/levels.json'
import playerData from '../../data/player.json'
import config from '../../data/config.json'

export class Level {
  readonly name = 'level'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private currentLevel: string
  private equippedWeapon: string

  constructor() {
    const weapons = Object.keys((weaponsData as any).weapons ?? {})
    const levels = Object.keys((levelsData as any).levels ?? {})
    this.description = `FPS level — ${levels.length} maps, ${weapons.length} weapons`
    this.currentLevel = (config as any).starting_level ?? levels[0] ?? 'e1m1'
    this.equippedWeapon = (config as any).starting_weapon_equipped ?? weapons[0] ?? 'pistol'
  }

  setup(): void {
    // BulletPattern — one instance per active weapon. Doom-like: weapon
    // determines pattern shape via projectile_kind (hitscan | projectile).
    this.tryMount('BulletPattern', {
      owner_tag: 'player',
      weapon_ref: this.equippedWeapon,
      fire_rate: (weaponsData as any).weapons?.[this.equippedWeapon]?.rate_of_fire ?? 8,
      spread: (weaponsData as any).weapons?.[this.equippedWeapon]?.spread ?? 0.02,
      projectile_kind: (weaponsData as any).weapons?.[this.equippedWeapon]?.projectile_kind ?? 'hitscan',
    })

    // WaveSpawner — enemies spawn when player enters trigger zones.
    this.tryMount('WaveSpawner', {
      spawn_triggers: (levelsData as any).levels?.[this.currentLevel]?.enemy_spawns ?? [],
      enemy_pool: Object.keys((enemiesData as any).enemies ?? {}),
      difficulty_scale: (config as any).difficulty ?? 'normal',
    })

    // AttackFrames — hitscan / projectile windup + active frames per weapon.
    this.tryMount('AttackFrames', {
      owner_tag: 'player',
      startup_frames: 2,
      active_frames: 3,
      recovery_frames: 4,
    })

    this.tryMount('PickupLoop', {
      trigger_tag: 'pickup',
      effect_on_collect: 'apply_pickup',
    })

    this.tryMount('ItemUse', {
      inventory_component: 'Inventory',
      usable_tags: ['medkit', 'armor_shard', 'berserk'],
    })

    this.tryMount('LockAndKey', {
      lock_tag: 'keycard_door',
      key_tag: 'keycard',
    })

    // First-person camera: target is the player with no lerp.
    this.tryMount('CameraFollow', {
      target_tag: 'player',
      lerp: 0.0,
      deadzone: [0, 0],
      first_person: true,
    })

    this.tryMount('HUD', {
      fields: [
        { archetype: 'player', component: 'Health', label: 'HEALTH' },
        { archetype: 'player', component: 'Armor',  label: 'ARMOR' },
        { singleton: 'ammo_equipped', label: 'AMMO' },
        { singleton: 'keys',          label: 'KEYS' },
      ],
      layout: 'bottom',
    })

    this.tryMount('LoseOnZero', {
      watch_archetype: 'player',
      watch_component: 'Health',
      aggregate: 'any_zero',
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  // ---- Public API ----

  /** Switch to a different level. */
  loadLevel(levelId: string): boolean {
    const levels = (levelsData as any).levels ?? {}
    if (!levels[levelId]) return false
    this.currentLevel = levelId
    return true
  }

  /** Equip a different weapon — swaps the BulletPattern params. */
  equipWeapon(weaponId: string): boolean {
    const weapons = (weaponsData as any).weapons ?? {}
    if (!weapons[weaponId]) return false
    this.equippedWeapon = weaponId
    return true
  }

  getCurrentLevel(): string { return this.currentLevel }
  getEquippedWeapon(): string { return this.equippedWeapon }

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
            ...Object.entries((enemiesData as any).enemies ?? {})
              .map(([id, e]) => ({ id, ...(e as any) })),
          ],
        }),
      },
      config: { mode: (config as any).config?.mode ?? '3d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
