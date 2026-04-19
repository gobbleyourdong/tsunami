---
name: Swiss Modern
applies_to: [dashboard, data-viz, landing, react-build]
mood: functional, rigorous, Müller-Brockmann / Base Design / Bureau Mirko Borsche
default_mode: light
corpus_share: 4
anchors: event-template-12345, signa-craft-magic, finance-buddy-43, vital-trade-news
---

<!-- corpus_share derivation: 4 templates at off-white bg + Inter/Host
     Grotesk/Archivo + grid-strict feel. Small share because the
     users lean expressive (photo_studio, atelier_warm) over Swiss
     rigor. Aspirational escape-hatch for `swiss/grid-strict/Helvetica`
     keyword routes. -->


## Palette
- Off-white base `#fafaf7` or warm-grey `#f0eee8`
- Near-black text `#111`
- ONE saturated primary: Helvetica-red `#e30613`, cobalt `#0047ab`, or chrome-yellow `#ffcc00`
- Grey ramp for hierarchy: `#888`, `#bbb`, `#ddd`. No other colours.

## Typography
- Single family, three weights only: `Inter` or `Neue Haas Grotesk` at 400 / 500 / 700
- No italics. No serifs. No display faces.
- Scale by ratio: 12 → 14 → 18 → 24 → 48 → 72. Nothing between.
- Tight letter-spacing on all-caps labels (tracking-widest for uppercase small text)

## Layout bias
- Strict 12-column grid, visible if possible (subtle 1px vertical rules at breakpoints)
- Everything left-aligned to column. No centering except deliberate set-pieces.
- Sections separated by single hairline rules, not padding-only
- Numbered sections (01 / 02 / 03) in a left margin or top corner

## Motion
- Minimal. Instant state change > animated state change.
- The only permitted animation: `opacity` fade-in on first mount, 200ms ease-out.
- No hover scales, no parallax, no scroll-linked effects. Grid is the show.

## Structural moves
- Full-bleed horizontal rule between sections
- Label + value pairs laid out in strict columns, aligned on colon or unit
- Running footer with section number / total ("03 / 08") at bottom of every view
- Captions under images: one-line, numbered ("Fig. 4 — Silver GT, coastal range")
- Navigation as a text list (not buttons), underline on active

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <div className="min-h-screen bg-[#fafaf7] text-[#111]">
      {/* Top rule + section nav — numbered, underlined active */}
      <header className="border-b border-[#111]">
        <div className="max-w-[1440px] mx-auto grid grid-cols-12 gap-4 px-6 py-4 items-center">
          <a href="/" className="col-span-3 font-bold tracking-tight text-lg">
            Studio/Nine
          </a>
          <nav className="col-span-7 flex gap-6 text-sm">
            {[
              ["01","Work"],["02","About"],["03","Process"],
              ["04","Writing"],["05","Contact"]
            ].map(([n,l]) =>
              <a key={n} href={`/${l.toLowerCase()}`} className="flex gap-2 hover:underline underline-offset-4">
                <span className="text-[#888] tabular-nums">{n}</span>
                <span>{l}</span>
              </a>
            )}
          </nav>
          <div className="col-span-2 text-right text-xs tabular-nums text-[#888]">
            03 / 08 · 2026
          </div>
        </div>
      </header>

      {/* Hero — strict 12-col, left-aligned, no centering */}
      <section className="max-w-[1440px] mx-auto grid grid-cols-12 gap-4 px-6 py-24">
        <div className="col-span-1 text-xs tabular-nums text-[#888]">01</div>
        <div className="col-span-7">
          <h1 className="text-[72px] leading-[1.05] tracking-tight font-bold">
            We design with<br/>grids, with reason,<br/>with restraint.
          </h1>
        </div>
        <div className="col-span-4 flex flex-col justify-end text-sm space-y-4">
          <p>
            Studio/Nine is a brand and editorial design practice based in
            Zürich and Brooklyn. We ship identities, books, and websites
            for clients in culture and industry.
          </p>
          <a href="/work" className="text-[#e30613] font-medium underline underline-offset-4">
            See the work →
          </a>
        </div>
      </section>

      {/* Hairline rule → label-value pairs aligned on colon */}
      <section className="max-w-[1440px] mx-auto grid grid-cols-12 gap-4 px-6 py-16 border-t border-[#111]">
        <div className="col-span-1 text-xs tabular-nums text-[#888]">02</div>
        <div className="col-span-3 text-xs uppercase tracking-wider">Currently</div>
        <dl className="col-span-8 grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          {[
            ["Clients", "MoMA · ETH Zürich · Phaidon · Berghain"],
            ["Focus",   "Editorial, wayfinding, digital product"],
            ["Team",    "Nine designers, two engineers, zero salespeople"],
            ["Next",    "Accepting three engagements for fall 2026"],
          ].map(([k,v]) =>
            <React.Fragment key={k}>
              <dt className="text-[#888] uppercase tracking-wider text-xs">{k}</dt>
              <dd>{v}</dd>
            </React.Fragment>
          )}
        </dl>
      </section>

      {/* Running footer — section-of-total */}
      <footer className="max-w-[1440px] mx-auto px-6 py-4 border-t border-[#111] flex justify-between items-center text-xs tabular-nums text-[#888]">
        <span>Studio/Nine · Zürich · Brooklyn</span>
        <span>03 / 08</span>
      </footer>
    </div>
  );
}
```

Notes: Strict `grid-cols-12 gap-4` enforcement at every section.
Numbered section markers in a narrow left gutter. ONE accent color
(`#e30613` Helvetica-red) reserved for the single CTA. Label-value
dl-grid uses `[120px_1fr]` for column alignment. Everything sits on
hairline `border-t border-[#111]` rules — no padding-only dividers.

## Reference sites to emulate
- kunsthaus.ch, moma.org old archive, hatchetgordon.com, experimentaljetset.nl
- Monograph: any Muller-Brockmann grid book
