import type { Product } from "../data/catalog"
import { formatPrice } from "../data/catalog"

type Props = { product: Product; onAdd: (id: string) => void; inCart: number }

export default function ProductCard({ product, onAdd, inCart }: Props) {
  const remaining = product.stock - inCart
  return (
    <article className="product">
      <img src={product.image} alt={product.name} loading="lazy" />
      <h3>{product.name}</h3>
      <div className="stock">
        {remaining > 0 ? `${remaining} in stock` : "Sold out"}
      </div>
      <div className="price">{formatPrice(product.price_cents, product.currency)}</div>
      <button
        disabled={remaining <= 0}
        onClick={() => onAdd(product.id)}
      >
        Add to cart
      </button>
    </article>
  )
}
