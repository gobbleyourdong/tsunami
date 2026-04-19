---
name: Playful Chromatic
applies_to: [landing, react-build, form-app]
mood: warm, expressive, Stripe / Linear / Vercel / Framer early
default_mode: neutral
corpus_share: 4
anchors: prompt-frame, nimble-event-hub, assetwise-insights, pinpost
---

<!-- corpus_share derivation: 4 templates with playful-modern-sans
     display faces (Syne, Bricolage Grotesque, Onest, Miranda Sans) +
     expressive accent hues (acid-yellow, magenta, signal-blue). Real
     corpus fonts differ from the original .md's references (which cited
     Clash Display / Gambarino / Satoshi — none in corpus). Font section
     updated below. -->


## Palette
- Warm off-white `#fdfcf8` or `#fcf8f3` (never pure white)
- Soft ink text `#1f1b18` (never pure black)
- Three accents used together, NOT reserved: coral `#ff6b6b`, mint `#4ecdc4`, butter `#ffe66d`
- Gradients ARE permitted — 2-stop soft mesh backgrounds on hero / card accents

## Typography
- Display: expressive modern sans — `Syne`, `Bricolage Grotesque`, `Onest`,
  `Miranda Sans`. These are what the scraped corpus anchors actually use.
  If a brand specifically calls for `Clash Display` / `Gambarino` /
  `Satoshi` those still work, but they're NOT corpus-validated — default
  to the four above.
- Body: companion sans (`Onest` as both display + body is a common move),
  or system stack `ui-sans-serif`.
- Ligatures enabled (`font-feature-settings: "liga", "dlig"`)
- Variable axis play: `Syne` weight 700 stretches great; `Onest` carries
  a wide-axis (`font-variation-settings: "wght" 500, "opsz" 18`).

## Layout bias
- Tile-based bento grids with varied sizes — some tiles 2x2, some 1x2, some 1x1
- Organic asymmetry — slight rotations on cards (`rotate: -1deg`), staggered alignment
- Rounded radii 16-24px on everything, consistently
- Layered elements — a tag badge overlapping the corner of a card, a logo breaking out of its container

## Motion
- Spring-physics everything. `transition: { type: "spring", bounce: 0.35 }`.
- Hover lifts: `translateY(-4px)` + soft shadow intensify
- Cursor-reactive: magnetic buttons that nudge toward the cursor
- Sequential reveal on scroll: children stagger in 80ms apart
- Loading state: skeleton shimmer with the accent gradient

## Structural moves
- Sticky pill-shaped navigation that shrinks on scroll
- Hover-reveal color swatches: grey state → color-wash on mouseover
- Interactive metrics: hover a number and it animates to a new value (alternate stat)
- Playful empty states: illustration + witty copy, not just "No results"
- Custom cursor: a dot that scales to 40px over interactive elements

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <div className="min-h-screen bg-[#fdfcf8] text-[#1f1b18] overflow-hidden">
      {/* Sticky pill nav that shrinks on scroll */}
      <nav className="sticky top-4 z-20 mx-auto w-fit flex gap-1 bg-white/80 backdrop-blur-md border border-[#1f1b18]/10 rounded-full p-1 text-sm">
        {["Work","Writing","Lab","About"].map(l =>
          <a key={l} href={`/${l.toLowerCase()}`} className="px-4 py-1.5 rounded-full hover:bg-[#ffe66d]/60">{l}</a>
        )}
      </nav>

      {/* Hero — display-sans with variable axis, gradient-mesh bg blob */}
      <section className="relative max-w-6xl mx-auto px-6 pt-24 pb-32">
        {/* Mesh gradient blob */}
        <div
          aria-hidden
          className="absolute -z-0 top-0 right-0 w-[500px] h-[500px] rounded-full blur-3xl opacity-50"
          style={{ background: "radial-gradient(circle at 30% 30%, #ff6b6b 0%, #ffe66d 40%, transparent 70%)" }}
        />
        <h1
          className="relative z-10 font-['Syne'] text-7xl md:text-[140px] leading-[0.95] tracking-tight"
          style={{ fontVariationSettings: '"wght" 700' }}
        >
          Build things<br/>
          that feel<br/>
          <span className="italic">slightly alive.</span>
        </h1>
        <p className="relative z-10 mt-10 max-w-xl text-lg text-[#1f1b18]/70">
          A lab for playful web tools, strange interactions, and interfaces
          that don't take themselves too seriously.
        </p>
        <div className="relative z-10 mt-10 flex gap-4">
          <a href="/work" className="px-6 py-3 rounded-full bg-[#1f1b18] text-white font-medium hover:-translate-y-1 hover:shadow-lg transition-transform">
            See the work
          </a>
          <a href="/writing" className="px-6 py-3 rounded-full border border-[#1f1b18]/20 hover:bg-[#ffe66d]/60">
            Read the writing
          </a>
        </div>
      </section>

      {/* Bento grid — mixed tile sizes, subtle rotation */}
      <section className="max-w-6xl mx-auto px-6 pb-24 grid grid-cols-4 auto-rows-[160px] gap-4">
        <div className="col-span-2 row-span-2 bg-[#ff6b6b] rounded-3xl p-8 text-white rotate-[-1deg] hover:rotate-0 transition-transform">
          <p className="text-xs uppercase tracking-wider opacity-80">Featured</p>
          <h3 className="font-['Syne'] text-4xl mt-2">Chromatic keyboard — playable synth in 10kB</h3>
        </div>
        <div className="col-span-2 bg-[#4ecdc4] rounded-3xl p-6 rotate-[1deg] hover:rotate-0 transition-transform">
          <h3 className="font-['Syne'] text-2xl">Tiny parsers</h3>
          <p className="text-sm mt-1">A column on grammars</p>
        </div>
        <div className="col-span-1 bg-[#ffe66d] rounded-3xl p-6 rotate-[-0.5deg] hover:rotate-0 transition-transform">
          <p className="text-xs uppercase">Lab 02</p>
          <h3 className="font-['Syne'] text-xl mt-1">Ballistic</h3>
        </div>
        <div className="col-span-1 bg-[#1f1b18] text-white rounded-3xl p-6 rotate-[0.5deg] hover:rotate-0 transition-transform">
          <p className="text-xs uppercase opacity-60">New</p>
          <h3 className="font-['Syne'] text-xl mt-1">→</h3>
        </div>
      </section>
    </div>
  );
}
```

Notes: Three moves combine into the doctrine tell —
(1) sticky pill-nav that shrinks, (2) mesh-gradient blur blob behind
oversized display type, (3) bento grid with `rotate-[-1deg]` + hover
de-rotation. Accent gestures are the three warm chromatic hues
(`#ff6b6b coral`, `#4ecdc4 mint`, `#ffe66d butter`) used TOGETHER, not
hoarded. `font-['Syne']` with `fontVariationSettings: "wght" 700`
gives the expressive display character that the corpus shows.

## Reference sites to emulate
- stripe.com, linear.app, vercel.com, framer.com, raycast.com
- Personal sites: brittanychiang.com, rauno.me, jhey.dev
