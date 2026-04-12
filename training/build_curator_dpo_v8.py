#!/usr/bin/env python3
"""build_curator_dpo_v8.py — DPO pairs for build-v93 patterns.

18 pairs (3 per fault, 6 faults):
  DDF01 — DnD: onDragOver must preventDefault() to allow drop
  DDF02 — DnD: setData('text/plain', id) not the whole object
  DDF03 — IntersectionObserver, not scroll events
  DDF04 — observer.disconnect() in useEffect cleanup
  DDF05 — useDebounce source before marked(), not debouncing HTML
  DDF06 — CSS vars via documentElement.style.setProperty, not inline styles per-component
"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path("workspace/training_data/curator_dpo_v8.jsonl")
TODAY = str(date.today())


def pair(source_bug, chosen, rejected, note):
    return {
        "prompt": f"[DDF probe: {source_bug}]",
        "chosen": chosen,
        "rejected": rejected,
        "source_bug": source_bug,
        "note": note,
        "images": [],
        "date": TODAY,
    }


# ── DDF01: onDragOver must preventDefault() ────────────────────────────────────
DDF01_PAIRS = [
    pair("DDF01a",
         chosen="onDragOver={(e) => { e.preventDefault(); setOver(col) }}  // preventDefault required to allow drop",
         rejected="onDragOver={() => setOver(col)}  // missing preventDefault — browser cancels drop event",
         note="onDragOver MUST call e.preventDefault(); without it the browser treats the target as non-droppable"),
    pair("DDF01b",
         chosen="<div onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>",
         rejected="<div onDrop={handleDrop}>  // onDrop fires only if onDragOver called preventDefault()",
         note="Drop target needs both onDragOver (with preventDefault) AND onDrop handler"),
    pair("DDF01c",
         chosen="function onDragOver(e: DragEvent, col: Column) {\n  e.preventDefault()  // allow drop\n  setOver(col)\n}",
         rejected="function onDragOver(e: DragEvent, col: Column) {\n  setOver(col)  // no preventDefault — onDrop won't fire\n}",
         note="The browser's default drag behavior is 'not allowed'; preventDefault overrides that to signal the zone accepts drops"),
]

# ── DDF02: setData('text/plain', id) not whole object ─────────────────────────
DDF02_PAIRS = [
    pair("DDF02a",
         chosen="e.dataTransfer.setData('text/plain', card.id)  // serialize only the ID",
         rejected="e.dataTransfer.setData('application/json', JSON.stringify(card))  // whole object is fragile across iframes",
         note="Pass only the card ID in dataTransfer; look up the full object from state in onDrop — avoids stale data"),
    pair("DDF02b",
         chosen="const cardId = e.dataTransfer.getData('text/plain')  // read ID → look up in board state",
         rejected="const card = JSON.parse(e.dataTransfer.getData('application/json'))  // stale if state changed during drag",
         note="dataTransfer carries the ID only; onDrop reads current state via the ID to get fresh data"),
    pair("DDF02c",
         chosen="onDragStart: setData('text/plain', id)  →  onDrop: getData → look up card in board state",
         rejected="onDragStart: setData('application/json', JSON.stringify(card))  →  onDrop: JSON.parse the whole card",
         note="IDs are stable; serialized objects become stale. Always pass IDs and resolve from current state in onDrop"),
]

# ── DDF03: IntersectionObserver not scroll events ─────────────────────────────
DDF03_PAIRS = [
    pair("DDF03a",
         chosen="new IntersectionObserver(entries => { if (entries[0].isIntersecting) loadMore() }, { rootMargin: '200px' })",
         rejected="window.addEventListener('scroll', () => { if (window.innerHeight + scrollY >= document.body.scrollHeight - 200) loadMore() })",
         note="IntersectionObserver is more performant and declarative than scroll events; fires asynchronously off main thread"),
    pair("DDF03b",
         chosen="const observer = new IntersectionObserver(cb, { rootMargin: '200px' })\nobserver.observe(sentinelRef.current)",
         rejected="window.addEventListener('scroll', handleScroll)  // fires on every scroll frame, needs manual debouncing",
         note="IntersectionObserver with rootMargin pre-triggers before the sentinel reaches the viewport; scroll events fire continuously"),
    pair("DDF03c",
         chosen="Infinite scroll: sentinel div at end of list + IntersectionObserver({ rootMargin: '200px' })",
         rejected="Infinite scroll: onScroll handler comparing scrollTop + clientHeight vs scrollHeight",
         note="IntersectionObserver is the modern approach; no scroll math, no debouncing needed, auto-cleanup with disconnect()"),
]

# ── DDF04: observer.disconnect() cleanup ──────────────────────────────────────
DDF04_PAIRS = [
    pair("DDF04a",
         chosen="useEffect(() => {\n  const observer = new IntersectionObserver(cb)\n  observer.observe(sentinel)\n  return () => observer.disconnect()  // cleanup\n}, [loadMore])",
         rejected="useEffect(() => {\n  const observer = new IntersectionObserver(cb)\n  observer.observe(sentinel)\n  // no cleanup — observer leaks on unmount\n}, [loadMore])",
         note="Always return observer.disconnect() from useEffect cleanup; otherwise each render creates a new observer"),
    pair("DDF04b",
         chosen="return () => observer.disconnect()  // in useEffect return value — runs on unmount or deps change",
         rejected="// No cleanup. Each loadMore change creates a new observer without removing the old one.",
         note="Without cleanup, dependency changes cause multiple observers to accumulate, firing loadMore multiple times per scroll"),
    pair("DDF04c",
         chosen="useEffect: create observer → observe sentinel → return () => observer.disconnect()",
         rejected="useEffect: create observer → observe sentinel  (no return/cleanup)",
         note="Missing disconnect() = memory leak + duplicate firings when component re-renders"),
]

# ── DDF05: useDebounce source, not HTML output ─────────────────────────────────
DDF05_PAIRS = [
    pair("DDF05a",
         chosen="const debouncedMd = useDebounce(source, 300)\nuseEffect(() => setHtml(marked(debouncedMd)), [debouncedMd])",
         rejected="const debouncedHtml = useDebounce(marked(source), 300)  // marked() runs on every keystroke, just delays setState",
         note="Debounce the SOURCE string, not the marked() call; otherwise the expensive parse still runs every keystroke"),
    pair("DDF05b",
         chosen="useDebounce(markdownSource, 300) → debouncedSource → useEffect runs marked() only when stable",
         rejected="onChange → setHtml(debounce(marked(source), 300))  // debounce in onChange doesn't prevent marked() execution",
         note="useDebounce on the input value delays the effect trigger; debouncing the output doesn't reduce computation"),
    pair("DDF05c",
         chosen="const debouncedSource = useDebounce(source, 300)\nuseEffect(() => { setHtml(marked(debouncedSource) as string) }, [debouncedSource])",
         rejected="const html = useMemo(() => marked(source), [source])  // useMemo doesn't debounce — still re-runs on every keystroke",
         note="useMemo is synchronous and fires on every change; useDebounce delays the dep update by N ms"),
]

# ── DDF06: CSS vars via setProperty, not inline styles per-component ──────────
DDF06_PAIRS = [
    pair("DDF06a",
         chosen="document.documentElement.style.setProperty('--color-primary', theme.primary)  // one call updates all components",
         rejected="// Pass theme as prop to every component and use theme.primary inline in each style={{}}",
         note="CSS custom properties cascade from :root — one setProperty call instantly updates every consumer without prop drilling"),
    pair("DDF06b",
         chosen="<button style={{ background: 'var(--color-primary)' }}>  // reads from CSS var",
         rejected="<button style={{ background: theme.primary }}>  // requires theme prop passed down to button",
         note="var(--color-primary) reads the current CSS variable without needing theme passed as a prop"),
    pair("DDF06c",
         chosen="applyTheme(t): root.style.setProperty('--color-primary', t.primary) × N props → all components auto-update",
         rejected="applyTheme(t): setThemeState(t) + every component must receive theme as prop and reference theme.primary",
         note="CSS variables eliminate prop drilling for theme; only ThemeProvider needs the JS object, consumers use var()"),
]


def main():
    all_pairs = DDF01_PAIRS + DDF02_PAIRS + DDF03_PAIRS + DDF04_PAIRS + DDF05_PAIRS + DDF06_PAIRS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")
    print(f"Wrote {len(all_pairs)} pairs to {OUT}")
    for p in all_pairs:
        print(f"  {p['source_bug']}: {p['note'][:65]}")


if __name__ == "__main__":
    main()
