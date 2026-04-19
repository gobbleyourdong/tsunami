---
name: Editorial Dark
applies_to: [landing, react-build, dashboard]
mood: luxury, cinematic, Apple / Tesla / Kettle / The Row
default_mode: dark
corpus_share: 2
anchors: luxe-portfolio-suite
---

<!-- corpus_share derivation: only luxe-portfolio-suite (Maya Chen —
     product design) cleanly matches dark + Playfair + minimalist luxury
     within the 155 scrape. Cap at 2 — the doctrine is aspirational for
     the Apple/Tesla voice which is rare in the actual corpus.
     Keyword-routable via `luxury dark / apple-style / noir`. -->


## Palette
- Base: near-black `#0a0a0a` with 1-2 elevation tints `#111`, `#1a1a1a`
- Text: `#f5f5f5` primary, `#f5f5f5/60` secondary, `#f5f5f5/30` tertiary
- One brand accent, used with restraint (< 5% of pixels) — gold, copper, forest, oxblood, arctic blue
- No gradients except controlled 2-stop fades on imagery (hero overlay, image bottom vignette)

## Typography
- Display: large serif — `Playfair Display`, `Cormorant Garamond`, `GT Sectra`, or `Editorial New`. Weight 400-500. Tight tracking.
- Body: neutral sans — `Inter`, `Söhne`, `Neue Haas Grotesk`. Weight 400. Comfortable 1.6 line-height.
- Scale: 72px+ display, 40px H1, 24px H2, 16px body, 13px caption, 11px micro. Skip 2 steps between each.
- Numerals: tabular for specs (`font-variant-numeric: tabular-nums`).

## Layout bias
- Asymmetric: 7fr / 5fr splits, not 6/6. Negative space dominates.
- Heroes are NOT centered — text left-aligned at bottom-left or bottom-right, large photo fills rest.
- Sections are uneven heights — 70vh, 45vh, 110vh — never uniform.
- Gutters: 8px base unit, sections spaced 120-160px apart vertically.

## Motion
- Spring easing, not linear. `transition: { type: "spring", stiffness: 80, damping: 20 }`.
- Scroll-linked: image parallax at 0.4x, text at 1.0x. Use framer-motion `useScroll` + `useTransform`.
- Hover: subtle scale 1.01-1.02 + brightness 1.05, 600-800ms. Never bouncy.
- Page transitions: crossfade with 400ms delay on incoming content. No slide.

## Structural moves that read current
- Sticky image column, scrolling text column (position: sticky; top: 10vh)
- Horizontal section break: large quote, mid-weight serif, italics, max-w-3xl, centered
- Drop cap on long-form (first letter 5x size, float left, serif)
- Number-led stat rows: "01 — 1,700 km" not "1700 / km" — number gets the weight
- Bento for collections: 2x1 hero tile + three 1x1 tiles, not uniform grid

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5]">
      {/* Top nav — thin, letter-spaced, anchored top */}
      <header className="max-w-[1440px] mx-auto flex justify-between items-center px-8 py-6">
        <a href="/" className="font-serif text-xl tracking-tight">Maya Chen</a>
        <nav className="flex gap-10 text-xs uppercase tracking-[0.25em]">
          <a href="/work">Work</a>
          <a href="/studio">Studio</a>
          <a href="/journal">Journal</a>
          <a href="/contact">Contact</a>
        </nav>
      </header>

      {/* Asymmetric 7fr/5fr split — image sticky-column on the right,
          editorial text scrolls past on the left. */}
      <section className="max-w-[1440px] mx-auto grid grid-cols-[7fr_5fr] gap-16 px-8 pt-16 pb-32">
        <div className="space-y-12">
          <p className="text-xs uppercase tracking-[0.3em] text-[#f5f5f5]/60">
            Product Design · Between Los Angeles and New York
          </p>
          <h1 className="font-serif text-6xl md:text-7xl leading-[1.05] tracking-tight">
            A quieter kind<br/>
            of product.
          </h1>
          <p className="font-serif text-lg text-[#f5f5f5]/80 max-w-md leading-relaxed">
            I lead product design at a handful of companies where restraint is
            the brief. Nine years. Three employers. Zero hurry.
          </p>
          {/* Number-led stat row — display weight on the number */}
          <dl className="grid grid-cols-3 gap-8 text-sm border-t border-[#f5f5f5]/20 pt-8">
            {[
              ["01","— 1,700 km"],["02","— 9 years"],["03","— 34 projects"]
            ].map(([k,v]) =>
              <div key={k}>
                <dt className="font-serif text-4xl tabular-nums">{k}</dt>
                <dd className="text-xs uppercase tracking-[0.2em] text-[#f5f5f5]/60 mt-2">{v}</dd>
              </div>
            )}
          </dl>
        </div>
        <div className="sticky top-[10vh] h-[80vh]">
          <img
            src="/hero.jpg"
            alt="Portrait, dim studio light"
            className="w-full h-full object-cover"
          />
          <p className="mt-3 text-xs italic text-[#f5f5f5]/50">
            Silver GT, coastal range — 2025
          </p>
        </div>
      </section>

      {/* Horizontal pull quote breaker */}
      <section className="max-w-3xl mx-auto px-8 py-24 text-center">
        <blockquote className="font-serif italic text-3xl md:text-4xl leading-[1.3]">
          "The work that lasts is the work that
          felt unhurried at the time."
        </blockquote>
      </section>
    </div>
  );
}
```

Notes: `grid-cols-[7fr_5fr]` asymmetry is the doctrine tell (NOT the
6/6 Swiss split). Right column is a `sticky top-[10vh]` image — it
holds while the left text scrolls, then releases. Numbered stat row
uses serif display numerals with small uppercase captions. ONE accent
gesture — here the italic pull quote breaker — no color chip, no
button. `f5f5f5/60` and `/20` opacity tiers instead of mid-grey hexes.

## Reference sites to emulate
- apple.com/iphone, tesla.com/model-s, thepeaq.co, kettle.co
- Editorial magazines: nytimes.com/interactive features, wallpaper.com, kinfolk.com
