// TimeReverseMechanic — v1.3 time extension (Cycle 22).
//
// Records per-entity transform / HP / resource snapshots into a ring
// buffer at `snapshot_rate_hz`. On rewind, plays the buffer backwards
// at real-time, restoring each entity to its historical state.
// Optional resource gate — drains a named resource component during
// rewind (Prince of Persia's SandsOfTime dial).
//
// Not the same as PhysicsModifier.time_scale: that mechanic scales
// time forward (slow-mo / fast-mo). This mechanic plays state back.

import type { Game } from '../../game/game'
import type { TimeReverseMechanicParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface Snapshot {
  t: number  // timestamp in seconds since init
  x?: number
  y?: number
  z?: number
  hp?: number
  /** Extra fields — whatever the scaffold decides to record. */
  [k: string]: unknown
}

class TimeReverseMechanicRuntime implements MechanicRuntime {
  private params: TimeReverseMechanicParams
  private game!: Game
  private rings = new Map<string, Snapshot[]>()
  private elapsed = 0
  private lastSnapshotAt = 0
  private rewinding = false
  private rewindCursor = 0  // index into ring buffer during rewind
  private resourceLeft = Infinity

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as TimeReverseMechanicParams
  }

  init(game: Game): void {
    this.game = game
    this.resourceLeft = Infinity  // disabled unless a scaffold seeds it
  }

  update(dt: number): void {
    if (this.rewinding) {
      this.stepRewind(dt)
      return
    }
    this.elapsed += dt
    const period = 1 / Math.max(1, this.params.snapshot_rate_hz)
    if (this.elapsed - this.lastSnapshotAt < period) return
    this.lastSnapshotAt = this.elapsed
    this.recordFrame()
  }

  dispose(): void {
    this.rings.clear()
    this.elapsed = 0
    this.lastSnapshotAt = 0
    this.rewinding = false
    this.rewindCursor = 0
  }

  expose(): Record<string, unknown> {
    return {
      is_rewinding: this.rewinding,
      buffer_depth: this.bufferDepth(),
      rewind_resource_left: this.resourceLeft,
      elapsed: this.elapsed,
      affects_tag: this.params.affects_tag ?? null,
    }
  }

  // ---- Public API ----

  /** Record a snapshot for an entity. Scaffold calls this from its
   *  state-change hooks (movement, damage, pickup) to populate the
   *  ring buffer with meaningful frames. Automatic per-frame recording
   *  also happens on update() at snapshot_rate_hz. */
  recordSnapshot(entityId: string, state: Omit<Snapshot, 't'>): void {
    if (this.rewinding) return
    const ring = this.rings.get(entityId) ?? []
    ring.push({ t: this.elapsed, ...state })
    // Trim to rewind_duration window.
    const cutoff = this.elapsed - this.params.rewind_duration_sec
    while (ring.length > 0 && ring[0].t < cutoff) ring.shift()
    this.rings.set(entityId, ring)
  }

  /** Begin rewinding. Drains resource_component (if configured).
   *  Returns false if no history to rewind or resource exhausted. */
  startRewind(): boolean {
    if (this.bufferDepth() === 0) return false
    if (this.params.resource_component && this.resourceLeft <= 0) return false
    this.rewinding = true
    this.rewindCursor = this.newestFrameIndex()
    try { writeWorldFlag(this.game, 'time.rewinding', true) } catch { /* ignore */ }
    return true
  }

  /** Stop rewinding. Snapshots recorded after this point start fresh. */
  stopRewind(): void {
    this.rewinding = false
    // Prune ring to the cursor position so future recording continues
    // from where rewind left off.
    for (const [id, ring] of this.rings) {
      this.rings.set(id, ring.slice(0, this.rewindCursor + 1))
    }
    this.lastSnapshotAt = this.elapsed
    try { writeWorldFlag(this.game, 'time.rewinding', false) } catch { /* ignore */ }
  }

  /** Seed the resource pool (scaffold calls on scene init if
   *  resource_component is configured). */
  setResource(amount: number): void {
    this.resourceLeft = amount
  }

  getResource(): number { return this.resourceLeft }
  isRewinding(): boolean { return this.rewinding }
  getSnapshots(entityId: string): Snapshot[] {
    const ring = this.rings.get(entityId)
    return ring ? [...ring] : []
  }
  bufferDepth(): number {
    let max = 0
    for (const ring of this.rings.values()) max = Math.max(max, ring.length)
    return max
  }

  // ---- Internals ----

  private recordFrame(): void {
    // Pull whatever entities the scene advertises and record coarse state.
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>>) ?? []
    for (const e of entities) {
      const id = (e as { id?: string }).id
      if (!id) continue
      const tag = this.params.affects_tag
      if (tag) {
        const tags = (e.tags as string[] | undefined) ?? []
        if (!tags.includes(tag)) continue
      }
      const pos = (e.position ?? {}) as Record<string, number>
      const snapshot: Omit<Snapshot, 't'> = {
        x: pos.x, y: pos.y, z: pos.z,
        hp: (e as Record<string, number | undefined>).hp,
      }
      this.recordSnapshot(id, snapshot)
    }
  }

  private stepRewind(dt: number): void {
    // Drain resource first — stop if exhausted.
    if (this.params.resource_component && this.params.resource_drain_rate) {
      this.resourceLeft -= this.params.resource_drain_rate * dt
      if (this.resourceLeft <= 0) {
        this.resourceLeft = 0
        this.stopRewind()
        return
      }
    }
    // Step the cursor backwards at real-time rate.
    const stepsPerSec = this.params.snapshot_rate_hz
    const advance = Math.max(1, Math.round(stepsPerSec * dt))
    this.rewindCursor -= advance
    if (this.rewindCursor <= 0) {
      this.rewindCursor = 0
      this.stopRewind()
      return
    }
    this.elapsed = Math.max(0, this.elapsed - dt)
  }

  private newestFrameIndex(): number {
    let max = 0
    for (const ring of this.rings.values()) {
      if (ring.length > max) max = ring.length - 1
    }
    return max
  }
}

mechanicRegistry.register('TimeReverseMechanic', (instance, game) => {
  const rt = new TimeReverseMechanicRuntime(instance)
  rt.init(game)
  return rt
})
