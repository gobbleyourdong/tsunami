---
name: Atelier Warm
applies_to: [landing, react-build, ecommerce]
mood: handcraft, ceramics, small-brand DTC, Terra Studios, warm cream, no chrome
default_mode: neutral
corpus_share: 12
anchors: editorial-dawn, warm-retro-wedding, cozy-app-harmony, boutique-boarding-pet-care-website
---

<!-- corpus_share derivation: the warm-cream cluster (handcraft / DTC / small
     brand) — estimated ~12 templates sharing warm-paper bg + muted terracotta
     + serif-first. Overlaps partly with magazine_editorial on quiet editorial
     blogs; this doctrine owns the product / brand / DTC voice. -->


## Palette
- Background: warm cream / paper — `hsl(40 33% 96%)` or `hsl(30 100% 95%)` or
  `hsl(35 25% 94%)`. Never pure white.
- Foreground: warm near-black — `hsl(30 10% 15%)` or `hsl(15 45% 20%)`. Never
  `#000` — it looks wrong against the warm bg.
- Primary: DESATURATED brand color — muted terracotta `hsl(16 78% 53%)`, deep
  forest `hsl(142 30% 30%)`, oxblood `hsl(350 50% 32%)`, dusty-plum
  `hsl(340 20% 35%)`.
- Accent: very soft blush or sage — `hsl(10 30% 85%)`, `hsl(78 40% 42%)`,
  `hsl(36 58% 58%)`.
- NO saturated vivid colors. NO pure black. NO cool blues.

## Typography
- Display: gentle serif at 400 weight — `EB Garamond`, `Cormorant Garamond`,
  `Libre Caslon Text`, `Fraunces` (soft optical axis settings).
- Body: companion serif OR system sans — whatever feels like "handwritten
  invitation". Avoid Inter-on-cream (reads cold).
- Scale is modest: 48px display / 28px section / 16–17px body / 13px caption.
  No oversized type — the brand is quiet.
- Paragraph indent: `text-indent: 1em` on paragraphs after the first. Small
  nod to print.

## Layout bias
- **Soft asymmetry** — NOT Swiss strict-grid, NOT full-bleed bold. Columns
  overlap slightly, photos get rough edges (no hard rectangles; use very
  subtle 2–4px radius or `polygon()` clipping).
- Product / piece shots: single image per row on mobile, 2-up on desktop.
  Generous margin around each image — space is luxury here.
- Copy sits next to imagery, not under it — left/right alternating in long
  scroll sections.
- No hero section at all — first view is a single image + three lines of
  italic copy + "Shop Collection" or "Visit the Studio" in plain serif.

## Motion
- Hand-crafted feeling — NOT machine-smooth. 400ms ease-out, nothing faster.
- Fade-in on scroll for copy. Images get a slow 800ms filter reveal from
  `sepia(0.15)` to `sepia(0)`.
- Button hover: underline slides in from left, 300ms. No translate.
- No springs, no bounces, no cursor effects.

## Structural moves that read current
- **Stamp / seal motif**: a small circular badge somewhere ("Est. 2019" /
  "Handmade in Oakland") in serif, reading like a back-of-book colophon.
- **Deckle-edge images**: use SVG filter or CSS mask to give photo edges
  slight irregularity (`filter: url(#rough)` with turbulence). Optional but
  characterful.
- **Hand-lettered-feel subheads**: use a script/italic secondary font for ONE
  element per page — e.g., section label "workshop notes" in italic script
  at 24px.
- **Signed copy**: end of about/manifesto blocks ends with `— Name, Place`
  in italic, right-aligned.
- **Warm ribbon banner**: small cream-on-terracotta strip ("Free shipping on
  orders over $80") at top — more like a letterpress band than a promo bar.

## DO-NOTs
- No dark mode. Cream IS the mood.
- No bold sans display (that's cinematic_display).
- No pure-white card backgrounds — use `#fafaf7` or `bg-[hsl(40_33%_96%)]`.
- No neon / vivid accents. Keep saturation below 60%.
- No shadows — use subtle warm borders `hsl(30 15% 85%)` instead.

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <section className="min-h-screen bg-[hsl(40_33%_96%)] text-[hsl(30_10%_15%)]">
      {/* Narrow top bar — cream ribbon — letterpress feel */}
      <div className="border-b border-[hsl(30_15%_35%)]/20">
        <div className="max-w-6xl mx-auto flex justify-between items-center px-6 py-3 text-xs tracking-wider">
          <span className="italic">Est. 2019 · Oakland, CA</span>
          <span>Free shipping on orders over $80</span>
        </div>
      </div>

      {/* Nav + logo wordmark, serif, centered */}
      <nav className="max-w-6xl mx-auto flex justify-between items-baseline px-6 py-8">
        <ul className="flex gap-8 text-sm font-serif">
          <li><a href="/shop">Shop</a></li>
          <li><a href="/collections">Collections</a></li>
          <li><a href="/journal">Journal</a></li>
        </ul>
        <a href="/" className="font-serif text-3xl italic">Terra</a>
        <ul className="flex gap-8 text-sm font-serif">
          <li><a href="/about">Studio</a></li>
          <li><a href="/cart">Cart (0)</a></li>
        </ul>
      </nav>

      {/* Asymmetric intro — no hero image, copy + one small piece photo */}
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-24 grid md:grid-cols-[3fr_2fr] gap-12 items-end">
        <div className="space-y-6">
          <h1 className="font-serif text-5xl md:text-6xl leading-[1.1]">
            Hand-thrown stoneware<br/>for a slower table.
          </h1>
          <p className="font-serif text-lg italic text-[hsl(30_10%_30%)] max-w-md">
            Each piece is cut, pulled, and glazed by hand in our Oakland studio.
            We fire twice a month — this season's pieces are made to order.
          </p>
          <a href="/shop" className="inline-block text-sm uppercase tracking-[0.2em] border-b border-[hsl(30_10%_15%)] pb-1">
            Shop the collection →
          </a>
        </div>
        <img
          src="/piece.jpg"
          alt="Hand-thrown bowl, cream glaze"
          className="aspect-[4/5] object-cover w-full"
        />
      </div>

      {/* Tiny colophon stamp */}
      <div className="max-w-6xl mx-auto px-6 pb-10 text-right">
        <span className="inline-block text-xs italic border border-[hsl(30_15%_35%)]/30 rounded-full px-4 py-1">
          — Made in Oakland —
        </span>
      </div>
    </section>
  );
}
```

Notes: NO hero image overlay. Asymmetric `grid-cols-[3fr_2fr]` — corpus
favors 60/40 splits over Swiss 50/50. Serif italic for warmth. Tiny colophon
badge ("Made in Oakland") reads as a hand-stamp, not a marketing chip.

## Reference sites (scraped corpus)
- editorial-dawn (warm cream, muted red)
- warm-retro-wedding (peach base, oxblood primary)
- cozy-app-harmony ("Terra Studios" — handcrafted ceramics)
- boutique-boarding-pet-care-website

## Evidence note
Small but distinct cluster — ~8–10 templates in the scraped corpus. Doesn't
fit `magazine_editorial` (too quiet), `photo_studio` (no hero image), or
`playful_chromatic` (not playful). The DTC-craft-brand voice needs its own
doctrine because the drone otherwise collapses it to "playful" and adds
bento grids + chromatic gradients, which murders the handcraft feel.
