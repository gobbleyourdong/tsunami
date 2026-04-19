---
name: Swiss Modern
applies_to: [dashboard, data-viz, landing, react-build]
mood: functional, rigorous, Müller-Brockmann / Base Design / Bureau Mirko Borsche
---

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

## Reference sites to emulate
- kunsthaus.ch, moma.org old archive, hatchetgordon.com, experimentaljetset.nl
- Monograph: any Muller-Brockmann grid book
