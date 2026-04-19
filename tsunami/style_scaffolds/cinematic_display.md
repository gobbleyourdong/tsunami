---
name: Cinematic Display
applies_to: [landing, react-build]
mood: band site, film studio, nightclub, full-bleed hero, oversized type, music/merch
default_mode: dark
corpus_share: 8
anchors: band-haven-hub, velvet-echo-studio, project-fetcher-pal, cine-charm-log, ruin-rhythm-site
---

<!-- corpus_share derivation: dark-mode total = 22/155; ~8 use condensed
     display sans (Bebas Neue / Anton / Archivo Black) for a cinematic / band /
     film voice. The others are editorial_dark (serif luxury). -->


## Palette
- Base: pure black `#000000` or near-black `hsl(0 0% 4%)`. Not a tinted-dark.
- Foreground: pure white `#ffffff` or `hsl(0 0% 98%)`. No grey body text.
- Accent: ONE high-chroma color used sparingly — electric yellow `#ffeb00`, hot
  red `#dc2626`, or retained neutral grey `hsl(0 0% 10%)` (quiet variant).
- No gradients on surfaces. Gradients only as image overlay darkening (hero
  bottom → transparent, to lift title off photograph).
- Zero mid-grey for "muted" text — use opacity: `text-white/60` instead.

## Typography
- Display: condensed bold sans — `Bebas Neue`, `Anton`, `Archivo Black`, or
  `Oswald`. Uppercase ONLY. Tracking wide on headers (`tracking-wider`).
- Body: same family at lighter weight, or system sans.
- Scale is extreme: hero headline 160–220px (clamp), H2 64–96px, body 14–15px.
  The gap between display and body is the point — body is tiny, display is huge.
- Numerals: tabular, often used as structural element (track numbers, tour dates,
  edition numbers). `font-variant-numeric: tabular-nums`.

## Layout bias
- Full-bleed everything. No max-width container on hero. Zero body padding.
- Hero: 100vh video loop or single oversized photograph, band/film name as
  display-serif-cap centered bottom, all-caps, wide tracking.
- Navigation: fixed-top, tiny type (12–14px uppercase), horizontal list flush-right
  or centered. Active = underlined.
- Tour dates / track listing: monospace-numeric left column + all-caps venue
  right column, hairline rule between rows. Like a liner-note credit sheet.
- Sections separated by 1px white rules, NOT padding-only.

## Motion
- Controlled. No bouncy springs, no hover bounce. Text slides up from bottom
  on scroll-in (24px translate, 500ms ease-out). Images fade.
- Video loops are the primary motion — autoplay muted hero video beats any
  transition animation.
- Marquee: slowly-ticking horizontal marquee of album names / tour cities /
  film titles at the top of sections, infinite loop.
- Button hover: invert (white-on-black → black-on-white) instantly, no animation.

## Structural moves that read current
- **Oversized type as a graphic element** — BAND NAME in 200px font spanning full
  width is the hero, not a wordmark-plus-tagline.
- **Track / show listing**: monospace numeric prefix, all-caps title, right-aligned
  date, rule between rows. Looks like a vinyl back cover.
- **Marquee band**: horizontal-scrolling text strip — upcoming dates or album
  names — on loop.
- **Black square video thumbnails** in a strict 3-column grid with white caption
  underneath each (song title, duration, year).
- **Subscribe bar**: fixed bottom, full-width, black with one email input + JOIN
  button. No newsletter copy beyond "MAILING LIST".

## DO-NOTs
- No Playfair / Cormorant / Editorial serif (that's photo_studio or magazine).
- No muted mid-grey "hint" text. Use white-opacity.
- No bento grid, no rounded cards, no drop shadows.
- No light-mode toggle. Committed dark.
- No magnetic cursor or spring-bounce — this is not Stripe.

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <section className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Fixed-top micro-nav, uppercase tracked-wide, no wordmark image */}
      <nav className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-6 md:px-12 py-6 backdrop-blur-md bg-background/30">
        <span className="text-xs uppercase tracking-[0.3em]">Shrine</span>
        <ul className="flex gap-8 text-xs uppercase tracking-[0.25em]">
          <li><a href="/music">Music</a></li>
          <li><a href="/tour">Tour</a></li>
          <li><a href="/merch">Merch</a></li>
          <li><a href="/press">Press</a></li>
        </ul>
      </nav>

      {/* Full-bleed hero video or photograph. 100vh. */}
      <div className="absolute inset-0 z-0">
        <video
          src="/hero.mp4"
          autoPlay
          muted
          loop
          playsInline
          className="w-full h-full object-cover opacity-70"
        />
        {/* Dark scrim toward bottom so the display-type reads */}
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
      </div>

      {/* Oversized display headline, centered bottom, Bebas Neue uppercase */}
      <div className="absolute bottom-16 left-0 right-0 z-10 text-center px-4">
        <h1
          className="font-['Bebas_Neue'] uppercase leading-[0.85] tracking-widest"
          style={{ fontSize: "clamp(80px, 18vw, 220px)" }}
        >
          Shrine
        </h1>
        <p className="mt-4 text-xs uppercase tracking-[0.3em] text-white/70">
          Post-punk · Brooklyn · Est. 2019
        </p>
      </div>

      {/* Ticking marquee of upcoming dates */}
      <div className="absolute bottom-0 left-0 right-0 z-10 overflow-hidden border-t border-white/20 py-3">
        <div className="whitespace-nowrap text-xs uppercase tracking-[0.25em] animate-[marquee_30s_linear_infinite]">
          MAR 12 BERLIN · MAR 15 PARIS · MAR 19 LONDON · MAR 22 DUBLIN · APR 02 NYC · APR 05 LA · APR 08 TOKYO · &nbsp;
        </div>
      </div>
    </section>
  );
}
```

Add to index.css (or tailwind config):
```css
@keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
```

Notes: hero IS 100vh video/image with dark-scrim gradient. Band name at 220px
is the graphic element, not a wordmark. Nav is translucent `bg-background/30`
+ `backdrop-blur-md` — the corpus signal. Ticking marquee at bottom = liner-
note credit-sheet energy.

## Reference sites (scraped corpus)
- band-haven-hub (Cassidy Lane — country-pop with Anton display)
- velvet-echo-studio (Shrine — post-punk, Bebas Neue)
- project-fetcher-pal (photographer dark — Bebas Neue)
- cine-charm-log
- ruin-rhythm-site

## Evidence note
Dark-mode = 22/155 templates; of those, 8 use display condensed sans (Bebas Neue /
Anton / Archivo). Previous `editorial_dark` doctrine collapsed "luxury serif dark"
and "cinematic display dark" into one — they're distinct. editorial_dark keeps
the Apple/Tesla serif-luxury voice; cinematic_display owns the band/film/nightclub
oversized-sans voice.
