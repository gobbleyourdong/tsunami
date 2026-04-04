/**
 * Inventory/pickup system.
 * Slot-based with stacking, add/remove/query.
 */

export interface ItemDef {
  id: string
  name: string
  maxStack: number
  category: string
  data?: Record<string, unknown>
}

export interface InventorySlot {
  item: ItemDef
  quantity: number
}

export class Inventory {
  private slots: (InventorySlot | null)[]
  readonly maxSlots: number

  onChange?: () => void

  constructor(maxSlots = 20) {
    this.maxSlots = maxSlots
    this.slots = new Array(maxSlots).fill(null)
  }

  /** Add item. Returns leftover quantity that didn't fit. */
  add(item: ItemDef, quantity = 1): number {
    let remaining = quantity

    // Stack onto existing slots first
    for (let i = 0; i < this.maxSlots && remaining > 0; i++) {
      const slot = this.slots[i]
      if (slot && slot.item.id === item.id && slot.quantity < item.maxStack) {
        const space = item.maxStack - slot.quantity
        const toAdd = Math.min(space, remaining)
        slot.quantity += toAdd
        remaining -= toAdd
      }
    }

    // Fill empty slots
    for (let i = 0; i < this.maxSlots && remaining > 0; i++) {
      if (!this.slots[i]) {
        const toAdd = Math.min(item.maxStack, remaining)
        this.slots[i] = { item, quantity: toAdd }
        remaining -= toAdd
      }
    }

    if (remaining < quantity) this.onChange?.()
    return remaining
  }

  /** Remove quantity of item. Returns amount actually removed. */
  remove(itemId: string, quantity = 1): number {
    let remaining = quantity

    for (let i = this.maxSlots - 1; i >= 0 && remaining > 0; i--) {
      const slot = this.slots[i]
      if (slot && slot.item.id === itemId) {
        const toRemove = Math.min(slot.quantity, remaining)
        slot.quantity -= toRemove
        remaining -= toRemove
        if (slot.quantity <= 0) this.slots[i] = null
      }
    }

    if (remaining < quantity) this.onChange?.()
    return quantity - remaining
  }

  /** Check if inventory contains at least N of an item. */
  has(itemId: string, quantity = 1): boolean {
    return this.count(itemId) >= quantity
  }

  /** Count total quantity of an item across all slots. */
  count(itemId: string): number {
    let total = 0
    for (const slot of this.slots) {
      if (slot && slot.item.id === itemId) total += slot.quantity
    }
    return total
  }

  /** Get slot at index. */
  getSlot(index: number): InventorySlot | null {
    return this.slots[index] ?? null
  }

  /** Get all non-empty slots. */
  getAll(): InventorySlot[] {
    return this.slots.filter((s): s is InventorySlot => s !== null)
  }

  /** Number of occupied slots. */
  get usedSlots(): number {
    return this.slots.filter(s => s !== null).length
  }

  get isFull(): boolean {
    return this.usedSlots >= this.maxSlots
  }

  clear(): void {
    this.slots.fill(null)
    this.onChange?.()
  }

  serialize(): (InventorySlot | null)[] {
    return this.slots.map(s => s ? { item: s.item, quantity: s.quantity } : null)
  }

  deserialize(data: (InventorySlot | null)[]): void {
    for (let i = 0; i < this.maxSlots; i++) {
      this.slots[i] = data[i] ?? null
    }
  }
}
