import raw from "../../data/products.json"

export type Product = {
  id: string
  name: string
  price_cents: number
  currency: string
  category: string
  image: string
  stock: number
  description: string
}

export const products: Product[] = (raw as { products: Product[] }).products

export function findProduct(id: string): Product | undefined {
  return products.find(p => p.id === id)
}

export function categories(): string[] {
  return Array.from(new Set(products.map(p => p.category))).sort()
}

export function formatPrice(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency })
    .format(cents / 100)
}
