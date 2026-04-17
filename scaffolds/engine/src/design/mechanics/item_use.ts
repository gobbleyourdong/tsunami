// ItemUse — Phase 4 extension mechanic.
//
// Binds named items to action effects. useItem(name) fires the bound
// ActionRef subject to requires_target_tag (if set, a tagged entity must
// be within range) and consume_on_use. active_slot is cosmetic — UI
// consumes it to bind to a physical button.

import type { Game } from '../../game/game'
import type { ActionRef, ItemUseParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type Item = ItemUseParams['items'][number]

class ItemUseRuntime implements MechanicRuntime {
  private params: ItemUseParams
  private game!: Game
  private itemByName = new Map<string, Item>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ItemUseParams
    for (const it of this.params.items ?? []) this.itemByName.set(it.name, it)
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { this.itemByName.clear() }

  /** External: player presses the bound button. Returns true if item fired. */
  useItem(name: string): boolean {
    const item = this.itemByName.get(name)
    if (!item) return false
    if (!this.playerHasItem(name)) return false
    if (item.requires_target_tag && !this.targetInRange(item.requires_target_tag)) return false
    this.fire(item.action)
    if (item.consume_on_use) this.consumeItem(name)
    return true
  }

  expose(): Record<string, unknown> {
    return {
      activeSlot: this.params.active_slot,
      items: [...this.itemByName.keys()],
    }
  }

  private playerHasItem(name: string): boolean {
    const player = this.findOwner()
    if (!player) return false
    const inv = (((player.properties as Record<string, unknown>)?.Inventory) ?? []) as unknown
    return Array.isArray(inv) && (inv as string[]).includes(name)
  }

  private consumeItem(name: string): void {
    const player = this.findOwner()
    if (!player) return
    const props = (player.properties ?? {}) as Record<string, unknown>
    const inv = ((props.Inventory ?? []) as string[]).slice()
    const i = inv.indexOf(name)
    if (i >= 0) inv.splice(i, 1)
    props.Inventory = inv
    player.properties = props
  }

  private targetInRange(tag: string, rangeUnits = 2.0): boolean {
    const player = this.findOwner()
    if (!player) return false
    const pp = (player.position as [number, number, number] | undefined) ?? [0, 0, 0]
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    for (const e of entities) {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      if (!Array.isArray(tags) || !tags.includes(tag)) continue
      const ep = (e.position as [number, number, number] | undefined) ?? [0, 0, 0]
      const dx = pp[0] - ep[0], dy = pp[1] - ep[1], dz = pp[2] - ep[2]
      if ((dx * dx + dy * dy + dz * dz) <= rangeUnits * rangeUnits) return true
    }
    return false
  }

  private findOwner(): Record<string, unknown> | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.find(e => e.type === aid) ?? null
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('ItemUse', (instance, game) => {
  const rt = new ItemUseRuntime(instance)
  rt.init(game)
  return rt
})
