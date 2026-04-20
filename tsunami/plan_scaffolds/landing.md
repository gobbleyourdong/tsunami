# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Sections](#sections)
- [ ] [Copy](#copy)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
Single-page marketing site. Pick which sections this landing actually
needs (omit any that don't apply): Nav, Hero, Features, SocialProof,
Pricing, Waitlist, FAQ, CTA, Footer. Compose them top-to-bottom in
src/App.tsx — no router, no state library, just sectioned divs.

Hooks worth reaching for: `useLocalStorage` (waitlist email), `useInterval`
(countdown for limited offers), `useMediaQuery` (mobile-first variants).

## Sections
For each section, write one component file:
- **Name** — `src/components/<Name>.tsx` — props — purpose

Use `./components/ui` primitives heavily:
- Hero: `GradientText` for headline, `TypeWriter` for sub-rotation, `Parallax` for depth.
- Features: `GlowCard` per feature; 3- or 4-column `Flex wrap gap`.
- Pricing: `Card variant="elevated"` for the popular tier; `Badge variant="primary" pill` to flag it; `Button fullWidth`.
- Waitlist: `Input` + `Button`; persist in `useLocalStorage("waitlist", [])`.
- SocialProof: `Marquee` of `Avatar` + `StarRating value={5} readOnly`.
- CTA: `ScrollReveal animation="slide-up"` wrapping a final `Button variant="primary" size="xl"`.
- AnnouncementBar at the very top for promos.

Drone-natural prop coverage is locked into `__fixtures__/landing_patterns.tsx` —
read it for canonical shapes.

## Copy
Headline ≤ 8 words, subhead ≤ 18 words, feature titles ≤ 3 words.
Use a real value proposition — no "Lorem ipsum". Read the goal one
more time and write copy that sells THAT specific thing.

## Tests
Write `src/App.test.tsx`. One behavioral test per interactive element:
- `<Nav> Sign-in click → navigates / opens dialog`
- `<Waitlist> submit valid email → stored + success state shown`
- `<Waitlist> submit invalid email → error visible`
- `<AnnouncementBar> dismiss → bar hidden`
- `<CTA> primary button click → analytics call / link follow`

vitest + @testing-library/react. Tests gate delivery — `npm run build`
runs them after vite build.

## Build
shell_exec cd {project_path} && npm run build
(runs tsc --noEmit + vite build; tsc also checks `__fixtures__/`)

## Deliver
message_result with one-line description.
