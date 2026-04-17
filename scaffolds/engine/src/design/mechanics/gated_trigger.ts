// GatedTrigger — Phase 4 extension mechanic.
//
// Gates a door/path archetype on one of: ConditionKey truthy, specific
// item in inventory, or tagged entity present. Fires open_effect when
// the gate first transitions to open. Idempotent — only fires once.

import type { Game } from '../../game/game'
import type { ActionRef, GatedTriggerParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

class GatedTriggerRuntime implements MechanicRuntime {
  private params: GatedTriggerParams
  private game!: Game
  private opened = false

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as GatedTriggerParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    if (this.opened) return
    if (this.gateSatisfied()) {
      this.opened = true
      this.markOpenOnEntities()
      if (this.params.open_effect) this.fire(this.params.open_effect)
    }
  }

  dispose(): void { /* state lives on entity */ }

  expose(): Record<string, unknown> {
    return { opened: this.opened }
  }

  private gateSatisfied(): boolean {
    const o = this.params.opens_when as unknown
    if (typeof o === 'string') return flagTruthy(this.game, o)
    if (o && typeof o === 'object') {
      const ow = o as Record<string, unknown>
      if (typeof ow.has_item === 'string') return this.playerHasItem(ow.has_item)
      if (typeof ow.tag_present === 'string') return this.tagPresent(ow.tag_present)
    }
    return false
  }

  private playerHasItem(item: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const player = entities.find(e => {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      return Array.isArray(tags) && tags.includes('player')
    })
    if (!player) return false
    const inv = ((player.properties as Record<string, unknown> | undefined)?.Inventory ?? []) as unknown
    return Array.isArray(inv) && (inv as string[]).includes(item)
  }

  private tagPresent(tag: string): boolean {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    return entities.some(e => {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      return Array.isArray(tags) && tags.includes(tag)
    })
  }

  private markOpenOnEntities(): void {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.gate_archetype as unknown as string
    for (const e of entities) {
      if (e.type !== aid) continue
      const p = (e.properties ?? {}) as Record<string, unknown>
      p.gate_open = true
      e.properties = p
    }
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('GatedTrigger', (instance, game) => {
  const rt = new GatedTriggerRuntime(instance)
  rt.init(game)
  return rt
})
