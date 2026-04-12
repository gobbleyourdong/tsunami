#!/usr/bin/env python3
"""build_curator_dpo_v7.py — DPO v7 for builder adapter.

18 pairs covering rr01-04 patterns from SFT v92:
  RRF01 (3) — React Router for multi-page, not page state variable
  RRF02 (3) — Free public API → direct fetch; don't proxy everything
  RRF03 (3) — Context + useReducer for shared state, not prop drilling
  RRF04 (3) — Debounce search, not immediate fetch on each keystroke
  RRF05 (3) — BrowserRouter in main.tsx wrapping App (not in App.tsx)
  RRF06 (3) — Error recovery: file_edit directly, not file_read first
"""
import json
from datetime import date
from pathlib import Path

COMBINED_IN = Path("workspace/training_data/curator_dpo_combined_v6.jsonl")
OUT_NEW = Path("workspace/training_data/curator_dpo_v7.jsonl")
OUT_COMBINED = Path("workspace/training_data/curator_dpo_combined_v7.jsonl")
TODAY = str(date.today())


def pair(source_bug, chosen, rejected, note):
    return {
        "prompt": f"[RRF probe: {source_bug}]",
        "chosen": chosen,
        "rejected": rejected,
        "source_bug": source_bug,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── RRF01: React Router for multi-page ────────────────────────────────────────
RRF01_PAIRS = [
    pair("RRF01a",
         chosen="Multi-page app → react-router-dom: BrowserRouter + Routes + Route. Each page is a component at a URL path.",
         rejected="Multi-page app → useState('page') state variable: if (page==='home') return <Home/>; if (page==='detail') ...",
         note="Multi-page apps need React Router, not page state variables (no real URLs, no back button)"),
    pair("RRF01b",
         chosen="project_init with dependencies=['react-router-dom'] → BrowserRouter in main.tsx → Routes/Route in App.tsx → Link in Navbar",
         rejected="project_init with no deps → add a 'currentPage' state in App.tsx → switch(currentPage) { case 'home': ...",
         note="Pass react-router-dom in dependencies array so it's installed; use Routes/Route not switch-page"),
    pair("RRF01c",
         chosen="useParams() to read :id from URL, useNavigate() to go back, Link to navigate between pages",
         rejected="Pass the recipe ID as a prop down through multiple components; use onClick handlers to set parent state",
         note="URL-based navigation (useParams/Link) creates bookmarkable deep links; prop drilling breaks URLs"),
]

# ── RRF02: Free public API → direct fetch ─────────────────────────────────────
RRF02_PAIRS = [
    pair("RRF02a",
         chosen="Open-Meteo is free with no key → fetch directly from React: fetch('https://api.open-meteo.com/v1/forecast?...')",
         rejected="Open-Meteo (free, no key) → still proxy through Express server to 'hide the endpoint'",
         note="No-key free APIs don't need a proxy — adding Express just adds latency and complexity"),
    pair("RRF02b",
         chosen="TMDB Bearer token → VITE_TMDB_KEY in .env (acceptable: rate-limited, not a financial liability). Direct fetch from React.",
         rejected="TMDB Bearer token → must go through Express proxy server because 'API keys should be server-side'",
         note="VITE_ is fine for public rate-limited APIs; proxy is only mandatory for LLM keys (financial risk)"),
    pair("RRF02c",
         chosen="OpenAI API key → Express proxy (financial liability, $$$). Open-Meteo / TMDB / public APIs → direct fetch from React.",
         rejected="All API keys → Express proxy, always. Even for free APIs with no financial risk.",
         note="Proxy overhead is worth it for LLM APIs; overkill for free public APIs"),
]

# ── RRF03: Context + useReducer for shared state ──────────────────────────────
RRF03_PAIRS = [
    pair("RRF03a",
         chosen="Shopping cart state shared across ProductGrid and CartPanel → createContext + useReducer in CartProvider, useCart() hook in both components",
         rejected="Shopping cart state → pass items/dispatch as props from App → ProductGrid → ProductCard (4 levels deep)",
         note="Context eliminates prop drilling when state is needed in many unrelated components"),
    pair("RRF03b",
         chosen="CartProvider wrapping entire App in the JSX tree → any nested component can call useCart() without props",
         rejected="Pass cart items as props all the way down: App → Layout → Main → ProductSection → ProductCard",
         note="Context Provider at the root means zero prop forwarding for any component in the tree"),
    pair("RRF03c",
         chosen="useReducer for cart: ADD/REMOVE/SET_QTY/CLEAR actions → predictable state transitions, easy to test",
         rejected="useState([]) for cart with in-place mutations: setItems(items.filter(...)). Scatter cart logic across components.",
         note="useReducer centralizes all cart logic; useReducer+Context is the idiomatic React pattern for shared state"),
]

# ── RRF04: Debounced search ────────────────────────────────────────────────────
RRF04_PAIRS = [
    pair("RRF04a",
         chosen="Search input → useDebounce(query, 400) → useEffect fires when debounced value changes → single API call",
         rejected="Search input → onChange fires useEffect immediately → API call on every single keystroke",
         note="Immediate fetch on every keystroke = dozens of API calls per second; debounce waits for pause in typing"),
    pair("RRF04b",
         chosen="const debouncedQuery = useDebounce(query, 400); useEffect(() => fetchMovies(debouncedQuery), [debouncedQuery])",
         rejected="const [query, setQuery] = useState(''); useEffect(() => fetchMovies(query), [query])",
         note="useEffect on raw query = fetch on every character; debounced = fetch only when user stops typing"),
    pair("RRF04c",
         chosen="useDebounce custom hook: setTimeout in useEffect with cleanup — fires after N ms of no updates",
         rejected="No debounce: add a 'Search' button instead — user must click to trigger",
         note="Search-as-you-type (debounced) is better UX than requiring a button press"),
]

# ── RRF05: BrowserRouter placement ────────────────────────────────────────────
RRF05_PAIRS = [
    pair("RRF05a",
         chosen="BrowserRouter in main.tsx wrapping App: <BrowserRouter><App /></BrowserRouter> — router available everywhere",
         rejected="BrowserRouter inside App.tsx return: <BrowserRouter><Routes>...</Routes></BrowserRouter> — valid but router context limited",
         note="BrowserRouter in main.tsx is the canonical pattern — keeps App.tsx clean and router context maximally available"),
    pair("RRF05b",
         chosen="main.tsx: import { BrowserRouter } from 'react-router-dom'; <BrowserRouter><App /></BrowserRouter>",
         rejected="App.tsx: import { HashRouter } from 'react-router-dom'; return <HashRouter>... — HashRouter adds # to URLs",
         note="BrowserRouter for clean URLs (needs server config for prod); HashRouter is a workaround with ugly # URLs"),
    pair("RRF05c",
         chosen="File written: src/main.tsx (adds BrowserRouter wrapper) — then App.tsx uses Routes/Route/Link freely",
         rejected="Forget to update main.tsx; put BrowserRouter only around the Routes section in App.tsx",
         note="Updating main.tsx first establishes the router context for all of App.tsx"),
]

# ── RRF06: Error recovery → file_edit ─────────────────────────────────────────
RRF06_PAIRS = [
    pair("RRF06a",
         chosen="Cannot resolve 'react-router-dom' → file_edit package.json to add dependency → npm install → rebuild",
         rejected="Cannot resolve 'react-router-dom' → file_read src/App.tsx to check imports → file_read main.tsx → ...",
         note="Missing module error is self-explanatory — edit package.json directly, no need to read source files"),
    pair("RRF06b",
         chosen="TypeError: Cannot read properties of undefined (reading 'id') at RecipePage.tsx:12 → file_edit RecipePage.tsx line 12",
         rejected="TypeError at RecipePage.tsx:12 → file_read RecipePage.tsx to understand the code before editing",
         note="Runtime error with exact line → file_edit that line; file_read is wasted work when you have the location"),
    pair("RRF06c",
         chosen="useContext must be used inside a Provider error → file_edit main.tsx to add BrowserRouter/CartProvider wrapper",
         rejected="useContext Provider error → file_read App.tsx, file_read main.tsx, file_read Context file to investigate",
         note="'Used outside Provider' error always means: wrap in main.tsx — edit immediately, don't investigate first"),
]


def main():
    all_new = RRF01_PAIRS + RRF02_PAIRS + RRF03_PAIRS + RRF04_PAIRS + RRF05_PAIRS + RRF06_PAIRS

    # Write new pairs
    OUT_NEW.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_NEW, "w") as f:
        for p in all_new:
            f.write(json.dumps(p) + "\n")
    print(f"Wrote {len(all_new)} new pairs to {OUT_NEW}")

    # Build combined v7 = v6 + v7
    combined = []
    if COMBINED_IN.exists():
        with open(COMBINED_IN) as f:
            combined = [json.loads(l) for l in f if l.strip()]
        print(f"Loaded {len(combined)} from combined_v6")
    combined.extend(all_new)

    with open(OUT_COMBINED, "w") as f:
        for p in combined:
            f.write(json.dumps(p) + "\n")
    print(f"Combined v7: {len(combined)} pairs → {OUT_COMBINED}")

    for p in all_new:
        print(f"  {p['source_bug']}: {p['note'][:65]}")


if __name__ == "__main__":
    main()
