import { useCart } from "../lib/cart"
import { formatPrice } from "../data/catalog"

type Props = { onCheckout: () => void }

export default function Cart({ onCheckout }: Props) {
  const { totals, total, set, remove } = useCart()
  return (
    <aside className="cart">
      <h2>Cart</h2>
      {totals.length === 0 && <div className="cart-empty">No items yet.</div>}
      {totals.map(({ product, line, subtotal_cents }) => (
        <div className="cart-line" key={line.productId}>
          <div>
            <div className="name">{product.name}</div>
            <div className="meta">{formatPrice(subtotal_cents, product.currency)}</div>
          </div>
          <div className="qty">
            <button onClick={() => set(line.productId, line.qty - 1)}>−</button>
            <span>{line.qty}</span>
            <button onClick={() => set(line.productId, line.qty + 1)}>+</button>
            <button onClick={() => remove(line.productId)} title="Remove">×</button>
          </div>
        </div>
      ))}
      {totals.length > 0 && (
        <>
          <div className="cart-total">
            <span>Total</span>
            <span>{formatPrice(total)}</span>
          </div>
          <button className="cart-checkout" onClick={onCheckout}>Checkout</button>
        </>
      )}
    </aside>
  )
}
