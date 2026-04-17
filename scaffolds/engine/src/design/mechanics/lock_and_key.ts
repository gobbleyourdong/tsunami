// LockAndKey — Phase 3 action-core mechanic.
//
// Tag-based gate. Any entity carrying lock_tag is un-interactable (its
// trigger fires nothing) until an entity with key_tag touches it.
// consume_key flag controls whether the key entity is destroyed or
// persists (master key). v1 implementation surfaces "unlocked" state on
// the lock entity's properties so GatedTrigger / the renderer can react.

import type { Game } from '../../game/game'
import type { LockAndKeyParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class LockAndKeyRuntime implements MechanicRuntime {
  private params: LockAndKeyParams
  private game!: Game
  private unlockedLockEntities = new Set<string>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as LockAndKeyParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    // Passive proximity check: a key entity touching a lock entity
    // unlocks it. "Touching" v1 = within 1.5 world units.
    const { keys, locks } = this.collectTagged()
    for (const lock of locks) {
      const lockId = String(lock.name ?? JSON.stringify(lock.position))
      if (this.unlockedLockEntities.has(lockId)) continue
      for (const key of keys) {
        if (this.inContact(lock, key)) {
          this.unlock(lock, lockId)
          if (this.params.consume_key) this.destroyEntity(key)
          break
        }
      }
    }
  }

  dispose(): void { this.unlockedLockEntities.clear() }

  expose(): Record<string, unknown> {
    return {
      unlockedCount: this.unlockedLockEntities.size,
      keyTag: this.params.key_tag,
      lockTag: this.params.lock_tag,
    }
  }

  private collectTagged(): {
    keys: Array<Record<string, unknown>>
    locks: Array<Record<string, unknown>>
  } {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const keys: Array<Record<string, unknown>> = []
    const locks: Array<Record<string, unknown>> = []
    for (const e of entities) {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      if (Array.isArray(tags) && tags.includes(this.params.key_tag)) keys.push(e)
      if (Array.isArray(tags) && tags.includes(this.params.lock_tag)) locks.push(e)
    }
    return { keys, locks }
  }

  private inContact(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
    const pa = (a.position as [number, number, number] | undefined) ?? [0, 0, 0]
    const pb = (b.position as [number, number, number] | undefined) ?? [0, 0, 0]
    const dx = pa[0] - pb[0], dy = pa[1] - pb[1], dz = pa[2] - pb[2]
    return (dx * dx + dy * dy + dz * dz) <= 1.5 * 1.5
  }

  private unlock(lock: Record<string, unknown>, lockId: string): void {
    const props = (lock.properties ?? {}) as Record<string, unknown>
    props.unlocked = true
    lock.properties = props
    this.unlockedLockEntities.add(lockId)
  }

  private destroyEntity(key: Record<string, unknown>): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return
    const entities = (active.entities as Array<Record<string, unknown>> | undefined) ?? []
    const i = entities.indexOf(key)
    if (i >= 0) entities.splice(i, 1)
  }
}

mechanicRegistry.register('LockAndKey', (instance, game) => {
  const rt = new LockAndKeyRuntime(instance)
  rt.init(game)
  return rt
})
