---
name: Newsroom Editorial
applies_to: [landing, react-build, blog]
mood: broadsheet, daily paper, trade publication, NYT-like, section rules, masthead
default_mode: light
corpus_share: 10
anchors: dear-dream-forge, daily-neighbor, sweet-dev-llama, vital-trade-news, new-venture-news
---

<!-- corpus_share derivation: blog/editorial vertical = 14/155; newsroom is the
     loud/urgent sub-cluster (Tribune voice, breaking-news red, masthead bar).
     Estimated 10 templates (remainder are magazine_editorial-quiet or
     atelier_warm blog variants). -->


## Palette
- Background: newsprint-white `hsl(0 0% 99%)` or pure `#ffffff`.
- Foreground: near-black `hsl(0 0% 10%)` or ink-blue `hsl(220 20% 12%)`.
- ONE strong primary that signals "breaking" — pure red `hsl(0 100% 60%)`,
  hot-pink `hsl(349 100% 59%)`, or ink-blue `hsl(216 12% 8%)` with a
  yellow-highlight accent `hsl(47 100% 58%)`.
- Rule-grey for section dividers: `hsl(0 0% 90%)`.
- Photo overlays: hairline 1px borders, NEVER drop shadows.

## Typography
- Display: serif at 500–700 weight — `Merriweather`, `Playfair Display`,
  `Source Serif Pro`, `Noto Serif`, `Libre Caslon Text`. Italics permitted.
- Caption / byline / dateline: `Inter` or system stack, 12–13px, all-caps
  with `tracking-widest`.
- Body: serif or sans depending on feature-vs-news — serif (`Lora`, `Crimson
  Pro`) for long-form features, sans for wire-service-feel lists.
- Scale: 56–72px headline / 32–40px feature / 20px standfirst / 16px body /
  13px caption / 11px fineprint.

## Layout bias
- **Masthead bar**: top-of-page flagname in huge serif, centered, with date +
  edition number above. Hairline rule below.
- **Section hierarchy**: above-the-fold follows print hierarchy — ONE lead
  story (left 2/3 with large photo), TWO secondary stories (right 1/3 stacked).
  Rules between columns.
- **Category chip tags**: top-right of each article card, tiny uppercase
  serif: POLITICS / CULTURE / BUSINESS. Colored only for the "LIVE" badge.
- **Byline rows**: `By Jane Doe` italic + `Staff Writer` in smaller grey +
  `Mar 3, 2026` far right. Thin rule above and below.
- **Pull quotes**: 32–40px serif italic, right-aligned in a 1/3 margin column,
  with a hairline rule above AND below, attribution in small-caps.

## Motion
- Essentially none. Editorial gravity > motion design.
- Permitted: 200ms fade-in on scroll for long-form article bodies.
- Photo hover: 3% scale-up in 400ms. That's it.
- No springs. No parallax. No scroll-hijacking.

## Structural moves that read current
- **Weather / index widget**: tiny sidebar module — "Markets ↑ 2.3%" /
  "Weather 54°F" — as a masthead accessory, even if the site isn't about news.
  Reads as "daily publication" even for a non-news product.
- **Edition number**: "Issue 142 · Vol. VII" visible somewhere, tabular-nums.
- **Contents page**: if the site has > 5 sections, include a numbered contents
  card in serif: "01 Analysis / 02 Features / 03 Op-Ed / 04 Archive".
- **Related reading**: after article end, a `MORE IN [SECTION]` block with
  3 thumbnails + headlines + date.
- **Continued-on-next-page** pattern for scrolling longform — a small
  "→ continued" line between major sections.

## DO-NOTs
- No big pill buttons. Links are underlined, buttons are flat rectangles with
  serif caps and a 1px border.
- No card shadows. Rules, never shadows.
- No dark mode. Newsroom is a morning-paper feel; commit light.
- No cursor effects, magnetic hovers, bento grids.

## Hero shape — concrete JSX template

```tsx
export function Masthead() {
  return (
    <header className="border-b border-[hsl(0_0%_90%)]">
      {/* Top meta strip — date, edition, weather — tabular nums */}
      <div className="flex justify-between items-center px-6 py-2 text-[11px] uppercase tracking-widest text-[hsl(0_0%_40%)] tabular-nums">
        <span>Issue 142 · Vol. VII</span>
        <span>Tuesday, March 3, 2026</span>
        <span>Markets ↑ 2.3% · 54°F</span>
      </div>
      {/* Masthead — serif flagname, centered, huge */}
      <div className="py-8 text-center border-y border-[hsl(0_0%_15%)]">
        <h1 className="font-serif text-6xl md:text-8xl tracking-tight">
          The Tribune
        </h1>
      </div>
      {/* Section nav — all caps, serif, underlined on hover */}
      <nav className="flex justify-center gap-8 py-3 text-xs uppercase tracking-widest">
        {["Politics","Business","Culture","Sports","Opinion","Archive"].map(s =>
          <a key={s} href={`/${s.toLowerCase()}`} className="hover:underline underline-offset-4">{s}</a>
        )}
      </nav>
    </header>
  );
}

export function LeadStory() {
  return (
    <article className="grid md:grid-cols-3 gap-8 px-6 py-10 border-b border-[hsl(0_0%_90%)]">
      {/* 2/3 column — lead photo + headline + byline */}
      <div className="md:col-span-2 space-y-5">
        <span className="inline-block text-[10px] uppercase tracking-widest bg-[hsl(0_100%_60%)] text-white px-2 py-0.5">
          Breaking
        </span>
        <img src="/lead.jpg" className="w-full aspect-[3/2] object-cover" />
        <h2 className="font-serif text-3xl md:text-5xl leading-snug max-w-4xl">
          Senate holds emergency vote on infrastructure package after overnight negotiations
        </h2>
        <div className="flex items-center gap-4 text-xs text-[hsl(0_0%_40%)]">
          <span className="italic">By Jane Doe</span>
          <span>Staff Writer</span>
          <span className="ml-auto tabular-nums">Mar 3, 2026 · 6:42 AM</span>
        </div>
        <p className="font-serif text-lg max-w-3xl leading-relaxed">
          Lead paragraph in serif body type, standfirst sets the scene…
        </p>
      </div>
      {/* 1/3 sidebar — two secondary stories stacked */}
      <aside className="space-y-8 border-l border-[hsl(0_0%_90%)] pl-8">
        {[1,2].map(i => (
          <div key={i} className="space-y-2">
            <span className="text-[10px] uppercase tracking-widest text-[hsl(0_0%_40%)]">Culture</span>
            <h3 className="font-serif text-xl leading-snug">Secondary story headline reads in under three lines</h3>
            <div className="text-xs italic text-[hsl(0_0%_50%)]">By Alex Stone · 4 min read</div>
          </div>
        ))}
      </aside>
    </article>
  );
}
```

Notes: masthead hairline rules (`border-y`) sandwich the flagname.
`max-w-3xl` / `max-w-4xl` on body copy is the corpus-dominant narrow column.
`tabular-nums` on date/time/markets is the newsroom detail. Category chip
uppercase micro-type. Breaking-news red is the ONE vivid color.

## Reference sites (scraped corpus)
- dear-dream-forge ("The Tribune", Merriweather + red breaking)
- daily-neighbor (local news)
- sweet-dev-llama (The Daily Chronicle)
- vital-trade-news (Trade Publication, Archivo)
- new-venture-news (Startup Scout, yellow-highlight accent)

## Evidence note
Sub-cluster of the light+serif bucket; distinct from `magazine_editorial`
(Kinfolk-quiet long-form with cream base, no urgency) and from `photo_studio`
(hero-image-first with Cormorant). Newsroom is about DENSITY + urgency —
several stories visible above the fold, serif masthead doing the work.
