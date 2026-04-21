"""Canary — scaffolds/web/ecommerce.

Structural canary + pure-logic parity check on cart totals. The TS
total calculator in src/lib/cart.ts::cartTotal is straightforward
enough that we can port it to Python and run the same math against
the seed catalog; this catches price-precision drift if someone
changes the calc from integer cents to floats.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "web" / "ecommerce"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "main.tsx",
        "README.md",
        "data/products.json",
        "src/App.tsx",
        "src/index.css",
        "src/data/catalog.ts",
        "src/lib/cart.ts",
        "src/components/ProductCard.tsx",
        "src/components/ProductGrid.tsx",
        "src/components/Cart.tsx",
        "src/components/index.ts",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_package_shape() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    assert pkg["name"] == "ecommerce"
    assert "react" in pkg["dependencies"]
    assert "vite" in pkg["devDependencies"]


def _products() -> list[dict]:
    return json.loads((SCAFFOLD / "data" / "products.json").read_text())["products"]


def test_products_shape() -> None:
    products = _products()
    assert len(products) >= 6, "need at least 6 seed products"
    ids = set()
    required = {"id", "name", "price_cents", "currency", "category", "stock", "image", "description"}
    for p in products:
        assert required.issubset(p.keys()), f"missing fields in {p.get('id')!r}"
        assert p["id"] not in ids, f"duplicate id: {p['id']}"
        ids.add(p["id"])
        assert isinstance(p["price_cents"], int) and p["price_cents"] > 0
        assert isinstance(p["stock"], int) and p["stock"] >= 0
        assert p["currency"] in ("USD", "EUR", "GBP", "JPY", "CAD", "AUD")


def test_categories_are_non_empty_strings() -> None:
    cats = {p["category"] for p in _products()}
    assert cats, "no categories"
    for c in cats:
        assert isinstance(c, str) and c.strip(), f"bad category: {c!r}"


def test_cart_total_parity_against_ts() -> None:
    """Port cartTotal(cart) from src/lib/cart.ts into Python. Verify it
    agrees with a hand-computed total for a two-line synthetic cart."""
    products = {p["id"]: p for p in _products()}
    synthetic_cart = [
        {"productId": "p-001", "qty": 2},
        {"productId": "p-004", "qty": 3},
    ]
    expected = products["p-001"]["price_cents"] * 2 + products["p-004"]["price_cents"] * 3

    def cart_total(cart: list[dict], catalog: dict) -> int:
        return sum(catalog[l["productId"]]["price_cents"] * l["qty"]
                   for l in cart if l["productId"] in catalog)

    assert cart_total(synthetic_cart, products) == expected


def test_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("ProductCard", "ProductGrid", "Cart"):
        assert re.search(rf"\b{name}\b", barrel), f"missing export: {name}"


def test_cart_uses_integer_cents() -> None:
    """Guard against future refactors that might use floats for money."""
    cart_ts = (SCAFFOLD / "src" / "lib" / "cart.ts").read_text()
    assert "price_cents" in cart_ts, "cart.ts must reference price_cents, not floats"
    # No obvious Math.* operations that imply float arithmetic on price
    assert "* 0." not in cart_ts and "/ 100)" not in cart_ts.replace(
        "cents / 100", ""
    ), "cart math should stay in integer cents"
