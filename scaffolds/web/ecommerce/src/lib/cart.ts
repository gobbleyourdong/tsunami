import { useCallback, useMemo, useSyncExternalStore } from "react"
import { findProduct, type Product } from "../data/catalog"

export type CartLine = { productId: string; qty: number }
export type Cart = CartLine[]

/**
 * Tiny external-store cart. Kept outside React state so any component
 * can read/mutate without prop-drilling. Persists to localStorage so
 * a reload keeps the cart — remove the storage calls if you want the
 * cart to clear between sessions.
 */
const STORAGE_KEY = "ecommerce.cart.v1"

function loadInitial(): Cart {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

let state: Cart = loadInitial()
const listeners = new Set<() => void>()

function emit() {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }
  listeners.forEach(l => l())
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}

export function getState(): Cart {
  return state
}

export function addToCart(productId: string, qty = 1): void {
  const product = findProduct(productId)
  if (!product) return
  const cap = Math.max(0, product.stock)
  const existing = state.find(l => l.productId === productId)
  if (existing) {
    state = state.map(l =>
      l.productId === productId
        ? { ...l, qty: Math.min(cap, l.qty + qty) }
        : l,
    )
  } else {
    state = [...state, { productId, qty: Math.min(cap, qty) }]
  }
  emit()
}

export function setQty(productId: string, qty: number): void {
  if (qty <= 0) {
    state = state.filter(l => l.productId !== productId)
  } else {
    const product = findProduct(productId)
    const cap = product ? Math.max(0, product.stock) : qty
    state = state.map(l =>
      l.productId === productId ? { ...l, qty: Math.min(cap, qty) } : l,
    )
  }
  emit()
}

export function removeFromCart(productId: string): void {
  state = state.filter(l => l.productId !== productId)
  emit()
}

export function clearCart(): void {
  state = []
  emit()
}

export function cartLineTotals(cart: Cart): { product: Product; line: CartLine; subtotal_cents: number }[] {
  const out: { product: Product; line: CartLine; subtotal_cents: number }[] = []
  for (const line of cart) {
    const product = findProduct(line.productId)
    if (!product) continue
    out.push({ product, line, subtotal_cents: product.price_cents * line.qty })
  }
  return out
}

export function cartTotal(cart: Cart): number {
  return cartLineTotals(cart).reduce((acc, l) => acc + l.subtotal_cents, 0)
}

export function useCart() {
  const snapshot = useSyncExternalStore(subscribe, getState, getState)
  const totals = useMemo(() => cartLineTotals(snapshot), [snapshot])
  const total = useMemo(() => cartTotal(snapshot), [snapshot])
  const add = useCallback((id: string, qty = 1) => addToCart(id, qty), [])
  const set = useCallback((id: string, qty: number) => setQty(id, qty), [])
  const remove = useCallback((id: string) => removeFromCart(id), [])
  const clear = useCallback(() => clearCart(), [])
  return { cart: snapshot, totals, total, add, set, remove, clear }
}
