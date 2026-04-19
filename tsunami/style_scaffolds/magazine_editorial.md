---
name: Magazine Editorial
applies_to: [landing, react-build]
mood: long-form, considered, NYT / Kinfolk / Cereal / The Gentleman's Journal
---

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

## Reference sites to emulate
- kinfolk.com, cerealmag.com, apartamentomagazine.com, issue.works, thegentlemansjournal.com
- Print inspiration: Apartamento, Gentlewoman, Holiday
