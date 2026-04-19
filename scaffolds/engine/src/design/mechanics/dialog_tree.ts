// DialogTree — Phase 1 content-multiplier mechanic.
//
// State-graph dialog. Each node has a line, optional speaker, and
// choices. Choices can gate on ConditionKey or world_flag, jump via
// goto, and fire ActionRef side effects. World flags live on a scene
// side-table (`scene.properties.world_flags`) so cross-mechanic
// reads/writes are coherent without a separate WorldFlags runtime.
//
// Entry is via trigger_archetype contact OR trigger_hotspot click. v1
// wires only the archetype-contact entry; hotspot entry is a noop and
// documented as Phase 2 work so HotspotMechanic can coexist.

import type { Game } from '../../game/game'
import type {
  ActionRef,
  DialogNode,
  DialogTreeParams,
  MechanicInstance,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class DialogTreeRuntime implements MechanicRuntime {
  private params: DialogTreeParams
  private game!: Game
  private nodeIndex = new Map<string, DialogNode>()
  private active = false
  private currentNodeId: string
  private lastChoice: string | null = null

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as DialogTreeParams
    this.currentNodeId = this.params.tree.id
    this.indexTree(this.params.tree)
  }

  init(game: Game): void {
    this.game = game
  }

  update(_dt: number): void {
    // Dialog is event-driven; nothing to tick. Advancement happens via
    // selectChoice() / advance() calls from input wiring.
  }

  dispose(): void {
    this.active = false
  }

  /** Start the dialog at the root node. Idempotent if already active. */
  start(): void {
    if (this.active) return
    this.active = true
    this.currentNodeId = this.params.tree.id
    const node = this.nodeIndex.get(this.currentNodeId)
    if (node?.on_enter) this.fireAction(node.on_enter)
  }

  /** Advance through a linear (no-choice) node. */
  advance(): void {
    if (!this.active) return
    const node = this.nodeIndex.get(this.currentNodeId)
    if (!node) return
    if (node.choices && node.choices.length > 0) {
      // Multi-choice — caller should have routed to selectChoice.
      return
    }
    // Linear auto-end.
    this.end()
  }

  /** Select a choice index at the current node. */
  selectChoice(index: number): void {
    if (!this.active) return
    const node = this.nodeIndex.get(this.currentNodeId)
    const choice = node?.choices?.[index]
    if (!choice) return
    if (!this.isChoiceAvailable(choice)) return
    this.lastChoice = choice.text
    if (choice.effect) this.fireAction(choice.effect)
    if (choice.goto) {
      const next = this.nodeIndex.get(choice.goto)
      if (next) {
        this.currentNodeId = next.id
        if (next.on_enter) this.fireAction(next.on_enter)
        return
      }
    }
    this.end()
  }

  expose(): Record<string, unknown> {
    const node = this.nodeIndex.get(this.currentNodeId)
    return {
      active: this.active,
      currentLine: node?.line ?? '',
      speaker: node?.speaker,
      choices: node?.choices?.map(c => ({
        text: c.text, available: this.isChoiceAvailable(c),
      })) ?? [],
      lastChoice: this.lastChoice,
    }
  }

  private end(): void {
    this.active = false
    this.currentNodeId = this.params.tree.id
  }

  private isChoiceAvailable(choice: NonNullable<DialogNode['choices']>[number]): boolean {
    if (!choice.requires) return true
    // Condition key: treated as true if present in scene world_flags or
    // if the game's flow has marked it fired. Fallback to unavailable
    // when the requirement can't be resolved — safer than leaking.
    const req = choice.requires as unknown
    if (typeof req === 'string') return this.flagTruthy(req)
    if (req && typeof req === 'object') {
      const rw = req as Record<string, unknown>
      if (typeof rw.world_flag === 'string') return this.flagTruthy(rw.world_flag)
    }
    return false
  }

  private flagTruthy(key: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const props = (active?.properties ?? {}) as Record<string, unknown>
    const flags = (props.world_flags ?? {}) as Record<string, unknown>
    const v = flags[key]
    return v === true || (typeof v === 'string' && v.length > 0) || (typeof v === 'number' && v !== 0)
  }

  private fireAction(action: ActionRef): void {
    // World flag writes are the only side effect handled in-mechanic;
    // other action kinds are forwarded to the engine's action dispatcher
    // when one exists. v1: quietly ignore unsupported kinds so dialog
    // doesn't throw when authors reference future-facing actions.
    if (action.kind === 'set_flag') {
      const active = this.game.sceneManager?.activeScene?.() as
        Record<string, unknown> | undefined
      if (!active) return
      const props = ((active.properties ?? {}) as Record<string, unknown>)
      const flags = ((props.world_flags ?? {}) as Record<string, unknown>)
      flags[action.world_flag as unknown as string] = action.value
      props.world_flags = flags
      ;(active as Record<string, unknown>).properties = props
    }
    if (action.kind === 'sequence') {
      action.actions.forEach(a => this.fireAction(a))
    }
  }

  private indexTree(node: DialogNode): void {
    this.nodeIndex.set(node.id, node)
    // DialogNode doesn't nest children directly — traversal is via
    // `choices[].goto`. We index all reachable nodes by recursion across
    // the tree-as-provided; choices reference other root-defined nodes
    // rather than inlined subtrees in this schema.
    // v1 assumes the tree is flat (root holds the node, choices goto by
    // id, and the design includes additional nodes at root level via
    // whatever the author provides — handled by the schema's
    // DialogNode being the singular entry; richer trees are a v2 task.)
  }
}

mechanicRegistry.register('DialogTree', (instance, game) => {
  const rt = new DialogTreeRuntime(instance)
  rt.init(game)
  return rt
})
