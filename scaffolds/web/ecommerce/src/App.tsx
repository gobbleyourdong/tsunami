import { ProductGrid, Cart } from "./components"
import { useCart } from "./lib/cart"
import { formatPrice } from "./data/catalog"

export default function App() {
  const { cart, total, add, clear } = useCart()
  const inCart = (id: string) =>
    cart.find(l => l.productId === id)?.qty ?? 0

  function handleCheckout() {
    window.alert(
      `Checkout stub — total ${formatPrice(total)}. ` +
      "Wire me to Stripe / your payment processor in src/lib/checkout.ts.",
    )
    clear()
  }

  return (
    <div className="shell">
      <main className="main">
        <h1>Shop</h1>
        <div className="sub">
          Scaffold for a product grid → cart → checkout flow.
          Replace the seed data in `data/products.json`.
        </div>
        <ProductGrid onAdd={add} quantityInCart={inCart} />
      </main>
      <Cart onCheckout={handleCheckout} />
    </div>
  )
}
