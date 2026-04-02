# Landing Page Template

React 19 + TypeScript + Vite. For marketing pages, portfolios, product sites.

## Pre-built Components

Import from `./components`:
- `Navbar` — sticky top nav with brand + links
- `Hero` — full-height hero with title, subtitle, CTA button
- `Section` — content section with title, subtitle, dark/light variants
- `FeatureGrid` — responsive grid of feature cards with icons
- `Footer` — footer with links and copyright

## Build Loop

1. Customize `Navbar` with your brand name and nav links
2. Set `Hero` title, subtitle, and CTA
3. Add `Section` blocks for features, about, pricing, etc.
4. Use `FeatureGrid` inside sections for card layouts
5. Wire everything in `src/App.tsx`

## Usage Example

```tsx
import { Navbar, Hero, Section, FeatureGrid, Footer } from "./components"

<Navbar brand="Acme" links={[
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "#pricing" },
]} />
<Hero
  title="Build faster with Acme"
  subtitle="The tool that changes everything"
  cta={{ label: "Get Started" }}
/>
<Section id="features" title="Features">
  <FeatureGrid features={[
    { title: "Fast", description: "Blazing speed", icon: "⚡" },
    { title: "Secure", description: "Bank-grade security", icon: "🔒" },
  ]} />
</Section>
<Footer brand="Acme" />
```

## File Structure

```
src/
  App.tsx            ← Wire your landing page here
  components/
    Navbar.tsx        ← Top navigation (ready to use)
    Hero.tsx          ← Hero section (ready to use)
    Section.tsx       ← Content section (ready to use)
    FeatureGrid.tsx   ← Feature cards (ready to use)
    Footer.tsx        ← Page footer (ready to use)
    index.ts          ← Barrel exports
```
