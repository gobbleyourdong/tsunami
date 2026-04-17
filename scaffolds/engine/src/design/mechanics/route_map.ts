// RouteMap — Phase 4 extension mechanic.
//
// Slay-the-Spire-style path-node graph. Each node has a kind (battle /
// elite / event / shop / rest / boss / treasure) + depth + associated scene.
// Edges define valid next-node transitions. Start nodes are the entry points
// for the run; boss_node is the unique terminal. selectNext(nodeId) records
// the choice; expose() publishes the currentNode + availableNext list.

import type { MechanicInstance, RouteMapParams } from '../schema'
import type { Game } from '../../game/game'
import { mechanicRegistry, type MechanicRuntime } from './index'

type Node = RouteMapParams['nodes'][number]

class RouteMapRuntime implements MechanicRuntime {
  private params: RouteMapParams
  private game!: Game
  private currentNodeId: string | null = null
  private visited: string[] = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as RouteMapParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { /* state lives in runtime */ }

  /** External: called at run start (or after selecting a start node). */
  beginAt(nodeId: string): boolean {
    if (!this.params.start_nodes.includes(nodeId)) return false
    this.currentNodeId = nodeId
    this.visited.push(nodeId)
    return true
  }

  /** External: advance to nodeId. Returns true iff it's a valid next. */
  selectNext(nodeId: string): boolean {
    if (!this.currentNodeId) return false
    const edges = (this.params.edges ?? []).filter(e => e.from === this.currentNodeId)
    if (!edges.some(e => e.to === nodeId)) return false
    this.currentNodeId = nodeId
    this.visited.push(nodeId)
    return true
  }

  expose(): Record<string, unknown> {
    const current = this.findNode(this.currentNodeId)
    const available = this.currentNodeId
      ? (this.params.edges ?? [])
        .filter(e => e.from === this.currentNodeId)
        .map(e => {
          const n = this.findNode(e.to)
          return n ? { id: n.id, kind: n.kind, depth: n.depth } : null
        })
        .filter((x): x is NonNullable<typeof x> => x !== null)
      : []
    return {
      layout: this.params.layout,
      currentNode: current
        ? { id: current.id, kind: current.kind, depth: current.depth }
        : null,
      visited: [...this.visited],
      available,
      reachedBoss: this.currentNodeId === this.params.boss_node,
    }
  }

  private findNode(id: string | null): Node | null {
    if (!id) return null
    return (this.params.nodes ?? []).find(n => n.id === id) ?? null
  }
}

mechanicRegistry.register('RouteMap', (instance, game) => {
  const rt = new RouteMapRuntime(instance)
  rt.init(game)
  return rt
})
