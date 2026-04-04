/**
 * Menu system — navigable with keyboard + controller.
 * Stack-based: push/pop sub-menus, escape goes back.
 */

export interface MenuItem {
  id: string
  label: string
  type: 'button' | 'toggle' | 'slider' | 'separator'
  value?: number | boolean
  min?: number
  max?: number
  step?: number
  onSelect?: () => void
  onChange?: (value: number | boolean) => void
}

export interface MenuPage {
  title: string
  items: MenuItem[]
}

export class MenuSystem {
  private stack: MenuPage[] = []
  private selectedIndex = 0

  onNavigate?: (index: number, item: MenuItem) => void
  onSelect?: (item: MenuItem) => void
  onBack?: () => void

  /** Push a menu page onto the stack. */
  push(page: MenuPage): void {
    this.stack.push(page)
    this.selectedIndex = 0
  }

  /** Pop the current menu page. Returns false if at root. */
  pop(): boolean {
    if (this.stack.length <= 1) {
      this.onBack?.()
      return false
    }
    this.stack.pop()
    this.selectedIndex = 0
    return true
  }

  /** Get current page. */
  get currentPage(): MenuPage | null {
    return this.stack[this.stack.length - 1] ?? null
  }

  /** Get selectable items (skip separators). */
  get selectableItems(): MenuItem[] {
    return this.currentPage?.items.filter(i => i.type !== 'separator') ?? []
  }

  /** Currently highlighted item. */
  get selectedItem(): MenuItem | null {
    return this.selectableItems[this.selectedIndex] ?? null
  }

  get selectedIdx(): number {
    return this.selectedIndex
  }

  get depth(): number {
    return this.stack.length
  }

  /** Navigate up. */
  up(): void {
    const items = this.selectableItems
    if (items.length === 0) return
    this.selectedIndex = (this.selectedIndex - 1 + items.length) % items.length
    this.onNavigate?.(this.selectedIndex, items[this.selectedIndex])
  }

  /** Navigate down. */
  down(): void {
    const items = this.selectableItems
    if (items.length === 0) return
    this.selectedIndex = (this.selectedIndex + 1) % items.length
    this.onNavigate?.(this.selectedIndex, items[this.selectedIndex])
  }

  /** Confirm/select current item. */
  confirm(): void {
    const item = this.selectedItem
    if (!item) return

    if (item.type === 'button') {
      item.onSelect?.()
      this.onSelect?.(item)
    } else if (item.type === 'toggle') {
      item.value = !item.value
      item.onChange?.(item.value)
      this.onSelect?.(item)
    }
  }

  /** Adjust slider left. */
  left(): void {
    const item = this.selectedItem
    if (!item || item.type !== 'slider') return
    const step = item.step ?? 1
    const min = item.min ?? 0
    item.value = Math.max(min, (item.value as number ?? 0) - step)
    item.onChange?.(item.value)
  }

  /** Adjust slider right. */
  right(): void {
    const item = this.selectedItem
    if (!item || item.type !== 'slider') return
    const step = item.step ?? 1
    const max = item.max ?? 100
    item.value = Math.min(max, (item.value as number ?? 0) + step)
    item.onChange?.(item.value)
  }

  /** Go back (escape). */
  back(): void {
    this.pop()
  }

  clear(): void {
    this.stack.length = 0
    this.selectedIndex = 0
  }
}
