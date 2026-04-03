# Landing Page Scaffold

Vite + React 19 + TypeScript. Atmospheric dark theme, scroll animations, glassmorphism.

## Components (import from `./components/ComponentName`)

| Component | Usage |
|-----------|-------|
| **Navbar** | `<Navbar brand="Acme" links={[{label:"Features",href:"#features"}]} cta={{label:"Sign Up",href:"#"}} />` — Fixed glass nav, mobile hamburger menu |
| **Hero** | `<Hero title="Ship Faster" subtitle="Build in minutes" cta={{label:"Get Started",href:"#"}} />` — Full viewport, radial gradient bg, staggered entrance |
| **ParallaxHero** | `<ParallaxHero bgImage="/hero.jpg" speed={0.4}><h1>Title</h1></ParallaxHero>` — Scroll parallax |
| **Section** | `<Section id="features" title="Features" subtitle="What we offer" dark centered>` — Alternating bg |
| **FeatureGrid** | `<FeatureGrid features={[{title:"Fast",description:"...",icon:"⚡"}]} columns={3} />` — Scroll-triggered staggered entrance |
| **Testimonials** | `<Testimonials testimonials={[{quote:"...",name:"Jane",role:"CEO"}]} />` — Glass cards with avatars |
| **StatsRow** | `<StatsRow stats={[{value:"10K+",label:"Users"}]} />` — Animated count-up on scroll |
| **CTASection** | `<CTASection title="Ready?" subtitle="..." buttonLabel="Get Started" buttonHref="#" />` — Glass panel with ambient glow |
| **PortfolioGrid** | `<PortfolioGrid items={[{title:"...",image:"...",tags:["React"]}]} />` — Filterable image grid |
| **Footer** | `<Footer brand="Acme" links={[...]} socials={[{icon:"🐦",href:"..."}]} />` |

## Landing CSS Classes
- `.hero`, `.hero-title`, `.hero-subtitle`, `.hero-cta` — hero with staggered entrance
- `.feature-grid.grid-2/3/4`, `.feature-card` — cards with top-edge glow on hover
- `.glass` — glassmorphism (blur backdrop + subtle border)
- `.pricing-grid`, `.pricing-card.featured` — pricing with glow on featured
- `.gallery-grid`, `.gallery-item` — image grid with zoom on hover
- `.section`, alternating backgrounds on even sections
- `.navbar`, `.navbar-cta`, `.navbar-hamburger` — glass nav + mobile menu
- `.badge.accent` — pill badge

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Use CSS classes — avoid inline styles for colors, spacing, or layout
- `App.tsx` is YOUR file — compose from the components above
