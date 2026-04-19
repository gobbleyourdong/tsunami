---
name: Magazine Editorial
applies_to: [landing, react-build]
mood: long-form, considered, NYT / Kinfolk / Cereal / The Gentleman's Journal
default_mode: neutral
corpus_share: 6
anchors: huggy-data-play, food-stories-personal-blog, cheer-weave, vesper-blog
---

<!-- corpus_share derivation: ~6 templates combine warm-paper bg + serif
     display (DM Serif Display / Playfair / Merriweather) + longform
     vocabulary ("essays", "stories", "blog", "journal"). Overlaps with
     atelier_warm on tone; magazine_editorial is the LONGFORM voice
     specifically — drop caps, multi-column body, pull quotes. -->


## Palette
- Cream / newsprint base `#f6f1e8` or `#ede8dc`
- Deep ink text `#1a1612` (not pure black)
- One muted accent: terracotta `#c76b4a`, forest `#2d4a3e`, navy `#1a2b4a`, oxblood `#6b1f2e`
- Faded neutrals: `#b8a890`, `#857765` for captions and rules

## Typography
- Two-family system: serif display + sans caption
  - Display: `Canela`, `GT Sectra`, `Playfair Display`, `DM Serif Display`. 500 weight, not bold.
  - Body serif: `Source Serif Pro`, `Lora`, `Spectral` for long-form paragraphs
  - Caption / label: `Inter` or `Söhne` at 500, small-caps or all-caps
- Scale: 96px display → 56px feature → 32px section → 20px body → 14px caption → 11px fineprint
- Paragraph copy: max-width 65ch, `text-indent: 1.5em` on every paragraph except first after heading

## Layout bias
- Multi-column body copy (CSS `columns: 2`) for long-form narrative sections
- Drop cap on opening paragraph: first letter floats left, 5 lines tall, serif
- Pull quotes break the column grid — right-aligned, italics, 2x scale
- Byline, dateline, section-number visible ("Issue 04 / Heritage / 2025")
- Images with caption beneath, rule above, italicized

## Motion
- Sparing. Content-first, movement second.
- Fade-in with slight upward translate (8px) on scroll reveal, 600ms ease-out
- No hover animations on text. Images get a 3% desaturate → full-colour on hover.
- Page transitions: solid color wipe (200ms) feels like turning a page

## Structural moves
- Contents page at entry — numbered sections with page-number equivalents and short descriptions
- Sidenotes in margin (use `<aside>`, 220px right-column, smaller type, rule between)
- Section openers: blank page with just a number and title, large serif centered, lots of air
- "Continued on next section" pattern for scrolling narrative
- Footnotes at section end: superscript in body, numbered list below

## Hero shape — concrete JSX template

```tsx
export function Masthead() {
  return (
    <header className="max-w-6xl mx-auto px-6 pt-12 pb-6">
      {/* Issue / date / section number — tiny uppercase serif */}
      <div className="flex justify-between items-center text-[11px] uppercase tracking-[0.25em] text-[#857765]">
        <span>Issue 04 · Heritage</span>
        <span>Spring 2026</span>
        <span>Vol. VII</span>
      </div>
      {/* Flagname — large serif, centered */}
      <h1 className="font-serif text-7xl md:text-9xl text-center mt-10 mb-12 tracking-tight text-[#1a1612]">
        Apartamento
      </h1>
      <hr className="border-t border-[#b8a890]" />
    </header>
  );
}

export function FeatureOpener() {
  return (
    <article className="max-w-4xl mx-auto px-6 py-16">
      {/* Section-opener page: number + title in huge serif, lots of air */}
      <div className="text-center space-y-8 py-20">
        <span className="font-serif text-9xl text-[#c76b4a]">01</span>
        <h2 className="font-serif text-5xl md:text-6xl leading-[1.1]">
          The Quiet Rooms of Eleanor Voss
        </h2>
        <p className="italic text-[#857765] text-sm uppercase tracking-[0.2em]">
          Words by Maya Chen · Photographs by David Park
        </p>
      </div>

      {/* Opening paragraph with drop cap + indent on subsequent paras */}
      <div className="font-serif text-lg leading-relaxed space-y-5 max-w-[65ch] mx-auto">
        <p className="first-letter:font-serif first-letter:float-left first-letter:text-7xl first-letter:leading-[0.9] first-letter:pr-3 first-letter:pt-1">
          Eleanor Voss does not believe in the hurried gesture. Her rooms
          breathe with a kind of patience that feels almost political, as if
          slowness itself were an argument against the age…
        </p>
        <p style={{ textIndent: '1.5em' }}>
          Continued paragraphs take a serif indent, no extra space between.
          This is the print convention — it signals the body is for reading,
          not scanning.
        </p>
        <p style={{ textIndent: '1.5em' }}>
          The third paragraph gets the same treatment…
        </p>
      </div>

      {/* Pull quote — breaks the column */}
      <blockquote className="font-serif italic text-3xl md:text-4xl text-right text-[#1a1612] border-y border-[#b8a890] py-10 my-16 max-w-3xl ml-auto">
        "I want my rooms to look as though nobody had thought
        about them at all."
        <cite className="block mt-4 text-xs uppercase tracking-widest not-italic text-[#857765]">
          — Eleanor Voss, in conversation
        </cite>
      </blockquote>

      {/* Multi-column body for long-form */}
      <div className="font-serif text-base leading-relaxed mt-16 [column-count:2] [column-gap:2.5rem] text-[#1a1612]">
        <p style={{ textIndent: '1.5em' }}>
          Lorem multi-column body paragraph that flows naturally between
          two columns like a print magazine. The columns render only on
          wider viewports…
        </p>
        <p style={{ textIndent: '1.5em' }}>
          Another paragraph continues the flow. Kinfolk / Cereal / the NYT
          long-form features use this treatment for essay-length bodies.
        </p>
      </div>
    </article>
  );
}
```

Notes: Three moves are load-bearing — the numbered section-opener
("01" huge in accent color), the drop cap on opening paragraph, and
the multi-column body via CSS `[column-count:2]`. Pull quote breaks
column and right-aligns with hairline rules above AND below.

## Reference sites to emulate
- kinfolk.com, cerealmag.com, apartamentomagazine.com, issue.works, thegentlemansjournal.com
- Print inspiration: Apartamento, Gentlewoman, Holiday
