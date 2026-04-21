# web/ecommerce

**Pitch:** product grid + cart + checkout stub. React + Vite + TS. The cart
is an external store (useSyncExternalStore) persisted to localStorage, so
any component can mutate without prop-drilling and a reload keeps the cart.

## Quick start

```bash
npm install
npm run dev        # localhost:5175
```

## Structure

| Path | What |
|------|------|
| `data/products.json`   | Seed product catalog — id/name/price_cents/currency/stock/category/image/description |
| `src/data/catalog.ts`  | Typed product access + category/price helpers                    |
| `src/lib/cart.ts`      | External-store cart with useCart() hook + pure total calc        |
| `src/components/`      | ProductGrid (with category filter), ProductCard, Cart            |

## Add a product

Append to `data/products.json`:

```json
{ "id": "p-007", "name": "…", "price_cents": 4900,
  "currency": "USD", "category": "…", "image": "…", "stock": 10,
  "description": "…" }
```

IDs must be unique; use `p-XXX` or your own convention.

## Wire checkout to a real payment processor

`src/App.tsx::handleCheckout` is a stub that alerts the total + clears
the cart. To ship a real flow, add `src/lib/checkout.ts` that calls
your backend's create-session endpoint:

- **Stripe Checkout**: POST cart to `/api/checkout`, server creates
  a Checkout Session, client redirects to `session.url`.
- **PaymentIntent flow**: similar, but mount the Payment Element in a
  `<Checkout>` component instead of redirecting.
- **Custom**: whatever your backend expects.

Keep the cart + product shape unchanged; just replace the `window.alert`
with your checkout call.

## Prices in cents

`price_cents` is integer cents to avoid float drift on totals. Format for
display with `formatPrice(cents, currency)`. Sums stay exact until you
render.

## Anchors

`Stripe Checkout`, `Shopify Hydrogen`, `Medusa`, `Snipcart`, `commercetools`.
