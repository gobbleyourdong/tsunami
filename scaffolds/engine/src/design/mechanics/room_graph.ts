// RoomGraph — Phase 3 action-core mechanic.
//
// Discrete-room connectivity with edge gates. Each room maps to a
// compiler-lowered scene. Edges can require a ConditionKey or an item
// in the player's inventory. Transitions fire on an explicit
// requestTransition(to) call — typically triggered by a door entity's
// trigger or a HotspotMechanic.

import type { Game } from '../../game/game'
import type { MechanicInstance, RoomGraphParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy, writeWorldFlag } from './world_flags'

class RoomGraphRuntime implements MechanicRuntime {
  private params: RoomGraphParams
  private game!: Game
  private currentRoom: string
  private visitedRooms = new Set<string>()
  private edgesFromCurrent: RoomGraphParams['edges'] = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as RoomGraphParams
    this.currentRoom = this.params.start_room
    this.visitedRooms.add(this.currentRoom)
    this.refreshEdges()
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { /* no timers */ }

  /** External: try to move to `to`. Returns true if the edge was valid
   *  and the transition fired; false if the edge was gated. */
  requestTransition(to: string): boolean {
    const edge = this.edgesFromCurrent.find(e => e.to === to)
    if (!edge) return false
    if (!this.gateSatisfied(edge)) return false
    // Fire on_enter of the destination room if defined.
    const destRoom = this.params.rooms?.find(r => r.id === to)
    if (destRoom?.on_enter) {
      const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
        ((a: unknown) => void) | undefined
      if (typeof dispatch === 'function') {
        try { dispatch(destRoom.on_enter) } catch { /* fire-and-forget */ }
      }
    }
    this.currentRoom = to
    this.visitedRooms.add(to)
    this.refreshEdges()
    writeWorldFlag(this.game, 'room_transition_requested', to)
    return true
  }

  expose(): Record<string, unknown> {
    return {
      currentRoom: this.currentRoom,
      visited: [...this.visitedRooms],
      availableEdges: this.edgesFromCurrent
        .filter(e => this.gateSatisfied(e))
        .map(e => e.to),
      totalRooms: this.params.rooms?.length ?? 0,
    }
  }

  private refreshEdges(): void {
    this.edgesFromCurrent = (this.params.edges ?? [])
      .filter(e => e.from === this.currentRoom)
  }

  private gateSatisfied(edge: RoomGraphParams['edges'][number]): boolean {
    if (edge.requires_condition
        && !flagTruthy(this.game, edge.requires_condition as unknown as string)) {
      return false
    }
    if (edge.requires_item && !this.playerHasItem(edge.requires_item)) {
      return false
    }
    return true
  }

  private playerHasItem(item: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const player = entities.find(e => {
      const p = e.properties as Record<string, unknown> | undefined
      const tags = (p?.tags ?? []) as string[]
      return Array.isArray(tags) && tags.includes('player')
    })
    if (!player) return false
    const inv = ((player.properties as Record<string, unknown> | undefined)?.Inventory ?? []) as unknown
    if (!Array.isArray(inv)) return false
    return inv.includes(item)
  }
}

mechanicRegistry.register('RoomGraph', (instance, game) => {
  const rt = new RoomGraphRuntime(instance)
  rt.init(game)
  return rt
})
