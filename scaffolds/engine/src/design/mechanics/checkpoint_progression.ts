// CheckpointProgression — Phase 3 action-core mechanic.
//
// Snapshots named archetype fields at save points, restores them on
// respawn. Three modes:
//   respawn_in_place — same scene, restore fields, position unchanged
//   reset_scene      — same scene, restore fields, re-run scene init
//   reset_level      — flow-level — signal flow to replay this level

import type { Game } from '../../game/game'
import type { CheckpointProgressionParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { clearFlags } from './world_flags'

class CheckpointProgressionRuntime implements MechanicRuntime {
  private params: CheckpointProgressionParams
  private game!: Game
  private snapshot: Record<string, unknown> | null = null
  private lastCheckpoint: [number, number, number] | null = null

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as CheckpointProgressionParams
  }

  init(game: Game): void {
    this.game = game
    this.takeSnapshot()   // Initial snapshot = starting state.
  }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { this.snapshot = null }

  /** Called by a Checkpoint component trigger when the player touches a
   *  checkpoint entity. Captures current field values + position. */
  setCheckpoint(position: [number, number, number]): void {
    this.takeSnapshot()
    this.lastCheckpoint = position
  }

  /** Called by LoseOnZero / a damage action to trigger the restore. */
  respawn(): void {
    if (!this.snapshot) return
    this.restoreSnapshot()
    if (this.params.mode === 'reset_scene') {
      clearFlags(this.game)
      // Scene-level reset: the harness's scene manager should re-run the
      // scene's init callback. We set a flag on properties to signal it.
      this.setResetFlag()
    }
    // reset_level is handled by the flow layer observing a dedicated
    // world_flag (`reset_level_requested`) that this method writes.
    if (this.params.mode === 'reset_level') {
      this.setResetFlag('reset_level_requested')
    }
  }

  expose(): Record<string, unknown> {
    return {
      hasSnapshot: this.snapshot !== null,
      lastCheckpoint: this.lastCheckpoint,
      mode: this.params.mode,
    }
  }

  private takeSnapshot(): void {
    const ent = this.findPlayerEntity()
    if (!ent) return
    const props = (ent.properties ?? {}) as Record<string, unknown>
    const snap: Record<string, unknown> = {}
    for (const field of this.params.restore_fields ?? []) {
      if (field in props) snap[field] = props[field]
    }
    this.snapshot = snap
  }

  private restoreSnapshot(): void {
    const ent = this.findPlayerEntity()
    if (!ent || !this.snapshot) return
    const props = (ent.properties ?? {}) as Record<string, unknown>
    for (const [k, v] of Object.entries(this.snapshot)) props[k] = v
    ent.properties = props
    if (this.lastCheckpoint) {
      ent.position = this.lastCheckpoint
    }
  }

  private findPlayerEntity(): Record<string, unknown> | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.find(e => e.type === aid) ?? null
  }

  private setResetFlag(name: string = 'scene_reset_requested'): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return
    const props = (active.properties ?? {}) as Record<string, unknown>
    const flags = (props.world_flags ?? {}) as Record<string, unknown>
    flags[name] = true
    props.world_flags = flags
    active.properties = props
  }
}

mechanicRegistry.register('CheckpointProgression', (instance, game) => {
  const rt = new CheckpointProgressionRuntime(instance)
  rt.init(game)
  return rt
})
