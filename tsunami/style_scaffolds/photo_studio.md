---
name: Photo Studio
applies_to: [landing, react-build, portfolio]
mood: photographer portfolio, atelier, between-NY-LA, large imagery, restraint
default_mode: light
corpus_share: 22
anchors: cinematic-photographer, contemporary-photographer, clean-photographer, creative-photographer, julien-moreau-folio
---

<!-- corpus_share derivation: portfolio vertical = 40/155; photo_studio covers
     the subset that is *photography voice* specifically (Cormorant serif, near-
     black primary, coral accent, full-bleed imagery). Estimated 22/40. -->


## Palette
- Background: pure white `#ffffff` or warm-paper `#fafafa`. Not off-white-cream.
- Foreground: near-black `#09090b` / `#0a0a0a`. Not pure `#000`.
- One vivid accent reserved for hover / hotspot: coral-orange `hsl(17 100% 61%)`,
  signal-blue `hsl(217 91% 60%)`, or deep-red `#dc2626`. Used on < 3% of pixels.
- Secondary surface: `#f4f4f5` for cards / inset panels.
- Border: `#e4e4e7` hairline only.

## Typography
- Display: elegant serif at 400–500 weight — `Cormorant Garamond` (corpus dominant),
  `Instrument Serif`, `Playfair Display`, or `EB Garamond`. Italics welcome for
  author names, location, small metadata.
- Body: tailwind system stack `ui-sans-serif, system-ui` — DO NOT replace with
  Plus Jakarta Sans or similar. System font is the dominant corpus choice.
- Scale: 96px display / 56px feature / 32px subhead / 16px body / 13px meta.
  Display is LARGE — hero headline should fill 60–80% of viewport width.
- Letter-spacing: `-0.03em` on display; `0.2em` uppercase on tiny labels (CITY,
  YEAR, CATEGORY).

## Layout bias
- **The photograph IS the page.** Hero is a single bleed image occupying 80–100vh.
  No overlay text on image — headline BELOW image, flush-left with generous top
  margin.
- Nav: tiny, top-right, all-caps, letter-spaced. "WORK / ABOUT / JOURNAL / CONTACT".
  No logo mark — name as text. No burger menu until mobile.
- Gallery: edge-to-edge image grid, NOT card-with-padding. Gap = 1–2px only.
  Hover = caption slides up from below image.
- Project page: single column text max-w-65ch, images full-bleed between paragraphs,
  captions small-grey below each image.

## Motion
- Fades only. 400–600ms ease-out on image reveal; no bounce, no spring, no parallax.
- Cursor: custom — small solid black dot, expands to 32px circle on interactive
  elements. Optional but characterful.
- Image hover: subtle `filter: grayscale(0) → grayscale(0.15)` over 400ms.
- Page transition: 200ms crossfade of main content; nav stays fixed.

## Structural moves that read current
- **Caption grid**: below each image, 3-column line: `01 / CITY / YEAR`. Tabular nums.
- **Location header**: "BETWEEN NEW YORK AND LOS ANGELES" as a permanent top-right
  metadata block.
- **Contact = email, not form**: big mailto link, serif italic, nothing else.
- **Index page**: text-only list of every project, one per line, hover reveals
  thumbnail to the right.
- **"01/12"** project counter pinned bottom-left, advances on scroll.

## DO-NOTs
- No card components with rounded corners + drop shadow.
- No dark mode toggle. Commit to light.
- No hero text overlaid on hero image with dim-the-image gradient.
- No "Get in touch" CTA button — serif mailto is the CTA.
- No stock photography or gradient placeholder blocks.

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <section className="min-h-screen flex flex-col">
      {/* Tiny top nav — name left, 4 links right, no logo mark */}
      <nav className="flex justify-between items-baseline px-6 md:px-12 py-6 text-sm">
        <span className="font-serif text-lg">Alex Chen</span>
        <ul className="flex gap-8 uppercase tracking-[0.2em] text-xs">
          <li><a href="/work">Work</a></li>
          <li><a href="/about">About</a></li>
          <li><a href="/journal">Journal</a></li>
          <li><a href="mailto:hello@alexchen.com">Contact</a></li>
        </ul>
      </nav>

      {/* Hero IS the photograph — edge-to-edge, 75vh, no overlay text */}
      <div className="flex-1 relative overflow-hidden bg-gray-100">
        <img
          src="/hero.jpg"
          alt="Portrait, Los Angeles, 2026"
          className="absolute inset-0 w-full h-full object-cover"
        />
      </div>

      {/* Headline BELOW the image, flush-left, serif, generous top margin */}
      <div className="px-6 md:px-12 pt-10 pb-16 max-w-4xl">
        <h1 className="font-serif text-5xl md:text-7xl leading-[1.05] tracking-tight">
          Portrait, fashion,<br/>and editorial work<br/>from the coast.
        </h1>
        <p className="mt-6 text-sm uppercase tracking-[0.2em] text-gray-600">
          Between Los Angeles and New York · 2015 — 2026
        </p>
      </div>
    </section>
  );
}
```

Notes: no centered layouts, no overlay text on hero image, serif display
below the photograph, tiny uppercase metadata. `bg-gray-100` is the corpus
tell — photographers frame their hero image in a soft grey wrapper so the
image floats. Nav uses `justify-between` + `items-baseline` (not centered).

## Reference sites (scraped corpus)
- cinematic-photographer
- contemporary-photographer
- clean-photographer
- creative-photographer
- julien-moreau-folio (light-yellow variant)

## Evidence note
Portfolio vertical = **40/155** of the scraped corpus (26%). This doctrine
anchors that wedge. Dominant traits across anchors: white bg, Cormorant or
system font, black primary, single vivid accent used sparingly, image-first
composition, tiny metadata-style nav.
