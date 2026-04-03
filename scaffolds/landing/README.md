# Landing Page Scaffold

Vite + React 19 + TypeScript. Dark theme with animations, smooth scroll, glassmorphism.

## Components (import from `./components`)

### Navbar
`<Navbar brand="Acme" links={[{label:"Features",href:"#features"}]} cta={{label:"Sign Up",href:"#"}} />`

### Hero
`<Hero title="Ship Faster" subtitle="Build in minutes" cta={{label:"Get Started",href:"#"}} />`
- Full viewport, gradient background, fade-up animation

### Section
`<Section id="features" title="Features" subtitle="What we offer" dark centered>`

### FeatureGrid
`<FeatureGrid features={[{title:"Fast",description:"...",icon:"⚡"}]} columns={3} />`

### Footer
`<Footer brand="Acme" links={[...]} socials={[{icon:"🐦",href:"..."}]} />`

## CSS Classes
- `.hero`, `.hero-title`, `.hero-cta` — hero with fade-up animations
- `.feature-grid.grid-2/3/4`, `.feature-card` — responsive card grid with hover
- `.glass` — glassmorphism (frosted blur + border)
- `.pricing-grid`, `.pricing-price` — pricing layout
- `.section`, `.section-dark` — alternating page sections
- `.navbar`, `.navbar-cta` — fixed blurred navigation
- Smooth scroll, responsive breakpoints included
