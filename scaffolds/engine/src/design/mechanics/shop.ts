// Shop — Phase 4 extension mechanic.
//
// Vendor archetype sells items from a stock list. purchase(itemName) debits
// the currency field on the player, adds the item to the player's Inventory,
// decrements stock_count (if set), and re-applies unlock_condition gating.

import type { Game } from '../../game/game'
import type { MechanicInstance, ShopParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

type StockEntry = ShopParams['stock'][number]

class ShopRuntime implements MechanicRuntime {
  private params: ShopParams
  private game!: Game
  private stockRemaining = new Map<string, number>()

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ShopParams
    for (const s of this.params.stock ?? []) {
      if (typeof s.stock_count === 'number') this.stockRemaining.set(s.item, s.stock_count)
    }
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { this.stockRemaining.clear() }

  /** External: player opens the shop UI and selects an item. */
  purchase(itemName: string): { ok: boolean; reason?: string } {
    const entry = (this.params.stock ?? []).find(s => s.item === itemName)
    if (!entry) return { ok: false, reason: 'item not in stock' }
    if (!this.availableForSale(entry)) return { ok: false, reason: 'locked' }
    if (this.stockRemaining.has(itemName) && (this.stockRemaining.get(itemName) ?? 0) <= 0) {
      return { ok: false, reason: 'out of stock' }
    }
    if (!this.debitPlayer(entry.price)) {
      return { ok: false, reason: 'insufficient currency' }
    }
    this.creditItem(itemName)
    if (this.stockRemaining.has(itemName)) {
      this.stockRemaining.set(itemName, (this.stockRemaining.get(itemName) ?? 0) - 1)
    }
    return { ok: true }
  }

  expose(): Record<string, unknown> {
    return {
      layout: this.params.ui_layout ?? 'list',
      available: (this.params.stock ?? [])
        .filter(s => this.availableForSale(s))
        .map(s => ({ item: s.item, price: s.price,
                     remaining: this.stockRemaining.get(s.item) })),
    }
  }

  private availableForSale(entry: StockEntry): boolean {
    if (entry.unlock_condition
        && !flagTruthy(this.game, entry.unlock_condition as unknown as string)) return false
    return true
  }

  private debitPlayer(amount: number): boolean {
    const player = this.findVendorCustomer()
    if (!player) return false
    const props = (player.properties ?? {}) as Record<string, unknown>
    const bal = (props[this.params.currency_field] as number | undefined) ?? 0
    if (bal < amount) return false
    props[this.params.currency_field] = bal - amount
    player.properties = props
    return true
  }

  private creditItem(item: string): void {
    const player = this.findVendorCustomer()
    if (!player) return
    const props = (player.properties ?? {}) as Record<string, unknown>
    const inv = ((props.Inventory ?? []) as string[]).slice()
    inv.push(item)
    props.Inventory = inv
    player.properties = props
  }

  private findVendorCustomer(): Record<string, unknown> | null {
    // v1: first entity tagged 'player' is the customer.
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    return entities.find(e => {
      const tags = (((e.properties as Record<string, unknown> | undefined)?.tags) ?? []) as string[]
      return Array.isArray(tags) && tags.includes('player')
    }) ?? null
  }
}

mechanicRegistry.register('Shop', (instance, game) => {
  const rt = new ShopRuntime(instance)
  rt.init(game)
  return rt
})
