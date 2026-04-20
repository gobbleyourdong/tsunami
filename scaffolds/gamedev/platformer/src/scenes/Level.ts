/**
 * Level scene — the main gameplay loop.
 *
 * Composes mechanics from @engine/mechanics:
 *  - PhysicsModifier (global gravity / friction / time-scale — tunable per level)
 *  - CheckpointProgression (per-level checkpoint + respawn)
 *  - PickupLoop (coins / powerups feed score + Mario-like effects)
 *  - LockAndKey (keys unlock doors to hidden areas)
 *  - CameraFollow (tracks the player with horizontal lead)
 *  - LoseOnZero (lives → 0 → game over)
 *  - WinOnCount (end-flag reached → next level)
 *  - HUD (coins, lives, level-name, time)
 *  - SfxLibrary (jump / coin / hit SFX)
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import levelsData from '../../data/levels.json'
import enemiesData from '../../data/enemies.json'
import playerData from '../../data/player.json'
import config from '../../data/config.json'

export class Level {
  readonly name = 'level'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private physicsRuntime: any = null
  private currentLevel: string

  constructor() {
    const levels = Object.keys((levelsData as any).levels ?? {})
    this.description = `Platformer level — ${levels.length} levels, precision jumping`
    this.currentLevel = (config as any).starting_level ?? levels[0] ?? '1-1'
  }

  setup(): void {
    // PhysicsModifier — tune gravity for jump feel. Platformer default:
    // gravity_scale 1.0; SMB-like fall is ~1.5; Celeste is ~0.85 (floatier).
    this.physicsRuntime = this.tryMount('PhysicsModifier', {
      gravity_scale: 1.0,
      friction_scale: 1.0,
      time_scale: 1.0,
    })

    // CheckpointProgression — mid-level checkpoints + respawn.
    this.tryMount('CheckpointProgression', {
      respawn_at: 'last_checkpoint',
      lives_component: 'Lives',
    })

    // PickupLoop — coins / mushroom / fire-flower / star.
    this.tryMount('PickupLoop', {
      trigger_tag: 'pickup',
      effect_on_collect: 'apply_powerup',
    })

    // LockAndKey — keys open doors to bonus areas.
    this.tryMount('LockAndKey', {
      lock_tag: 'door',
      key_tag: 'key',
    })

    this.tryMount('CameraFollow', {
      target_tag: 'player',
      lerp: 0.2,
      deadzone: [1.5, 0.3],
    })

    this.tryMount('LoseOnZero', {
      watch_singleton: 'lives',
      aggregate: 'zero',
    })

    this.tryMount('WinOnCount', {
      watch_tag: 'level_exit',
      count_target: 1,
      count_condition: 'player_reached',
    })

    this.tryMount('HUD', {
      fields: [
        { singleton: 'coins',     label: 'COIN' },
        { singleton: 'lives',     label: '× ' },
        { singleton: 'score',     label: 'SCORE' },
        { singleton: 'time_left', label: 'TIME' },
      ],
      layout: 'top',
    })

    this.tryMount('SfxLibrary', {
      presets: {
        jump:     'sfxr_jump',
        coin:     'sfxr_coin',
        hit:      'sfxr_hit',
        powerup:  'sfxr_powerup',
        death:    'sfxr_death',
      },
    })
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
    this.physicsRuntime = null
  }

  // ---- Public API ----

  /** Switch to a new level. Re-tunes PhysicsModifier if the level declares
   *  non-default gravity (e.g. underwater levels use 0.3). */
  loadLevel(levelId: string): boolean {
    const levels = (levelsData as any).levels ?? {}
    const lvl = levels[levelId]
    if (!lvl) return false
    this.currentLevel = levelId
    if (this.physicsRuntime && typeof lvl.gravity_scale === 'number') {
      this.physicsRuntime.setGravityScale?.(lvl.gravity_scale)
    }
    return true
  }

  getCurrentLevel(): string { return this.currentLevel }

  getPhysicsScales(): { gravity: number; friction: number; time: number } {
    return {
      gravity: this.physicsRuntime?.getGravityScale?.() ?? 1,
      friction: this.physicsRuntime?.getFrictionScale?.() ?? 1,
      time: this.physicsRuntime?.getTimeScale?.() ?? 1,
    }
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
          ],
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }
}
