import { products, categories, type Product } from "../data/catalog"
import { useState } from "react"
import ProductCard from "./ProductCard"

type Props = { onAdd: (id: string) => void; quantityInCart: (id: string) => number }

export default function ProductGrid({ onAdd, quantityInCart }: Props) {
  const [filter, setFilter] = useState<string>("all")
  const cats = ["all", ...categories()]
  const visible = filter === "all"
    ? products
    : products.filter((p: Product) => p.category === filter)

  return (
    <>
      <div className="filters">
        {cats.map(c => (
          <button
            key={c}
            className={filter === c ? "active" : ""}
            onClick={() => setFilter(c)}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="grid">
        {visible.map(p => (
          <ProductCard key={p.id} product={p} onAdd={onAdd}
                       inCart={quantityInCart(p.id)} />
        ))}
      </div>
    </>
  )
}
