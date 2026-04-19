---
name: Shadcn Startup
applies_to: [landing, react-build, dashboard, fullstack, auth-app, ai-app]
mood: Linear-lite, Vercel-ish, utility saas, dev tooling, "just shadcn/ui done well"
default_mode: light
corpus_share: 40
anchors: bugtrackr, assetwise-insights, commcalc, continuum-daily, new-venture-news, thepipelineiq
---

<!-- corpus_share derivation: the dominant "safe baseline" — light + system
     font + saturated accent (blue 217-91-60 / purple 234-55-58 / yellow
     47-100-58). Covers 40/155 across utility apps, trackers, CRUD,
     dashboards, dev tools, startup landings. The default when no other
     doctrine has a stronger claim. -->


## Evidence note (why this exists)

~40/155 of the scraped corpus sits in this cluster: white/near-white background
+ tailwind-default system font + one saturated accent (blue `217 91% 60%`,
purple `234 55% 58%`, yellow `47 100% 58%`) + shadcn-aligned greys for surfaces.

It is NOT aspirational. It IS defensible. When no other doctrine fits — utility
apps, trackers, CRUD interfaces, admin consoles, dev tools — this is what the
market actually ships, and fighting it costs quality without buying distinction.

## Palette
- Background: pure white `#ffffff` or near-white `hsl(0 0% 99%)`.
- Foreground: near-black `hsl(0 0% 9%)` or cool-black `hsl(222 47% 11%)` (shadcn slate-950).
- Primary: ONE saturated accent, chosen for vertical:
  - signal-blue `hsl(217 91% 60%)` — generic saas, dashboards, dev tools
  - electric-purple `hsl(234 55% 58%)` — bug trackers, build tools, analytics
  - warm-yellow `hsl(47 100% 58%)` — trading, finance, hotlists
  - coral-orange `hsl(14 84% 52%)` — ecommerce / DTC utility
- Surfaces: `#fafafa` / `#f4f4f5` / `#e4e4e7` — standard shadcn greyscale.
- Destructive: `#ef4444` / `#dc2626`. Success: `#16a34a`. Warning: `#ea580c`.

## Typography
- Body + display: the tailwind default `ui-sans-serif, system-ui`. On macOS
  this resolves to San Francisco; on most linux/windows it resolves to Inter-
  adjacent system UI. **Do not load a Google Font** — 100/155 corpus templates
  don't, and loading one makes the page slower without looking better.
- Monospace: `ui-monospace, 'JetBrains Mono'` — for data tables, IDs, command
  snippets.
- Scale: 48–56px feature / 32px h2 / 24px h3 / 16px body / 14px secondary /
  12px meta. Tight — utility apps don't need display-sized type.
- Tracking: `-0.02em` on h1/h2 only; body is default tracking.

## Layout bias
- **Cards do the heavy lifting.** Not bento asymmetry — standard shadcn Card
  with border + subtle shadow, grid-of-equals. This is the cluster where
  `grid-cols-3 gap-6` is correct.
- Top nav: left-aligned wordmark + centered or right nav + right CTAs. 64px
  tall, fixed, `backdrop-blur-sm bg-white/80`.
- Dashboards: sidebar nav (220–260px) + main area with cards-on-grid. Sidebar
  has collapsible sections.
- Landing: hero = ONE sentence claim (not stacked taglines), subtitle in
  `text-muted`, TWO CTAs (primary + ghost), then a feature-grid of 3 cards
  explaining value props with lucide icons.
- Tables: shadcn Data Table pattern — sticky header, zebra rows optional,
  row hover `bg-muted/50`.

## Motion
- Functional. 150–200ms ease-out on hover states. No springs, no bounces,
  no parallax.
- Accordion/collapse uses shadcn's framer-motion animations out of the box.
- Page transitions: none. Navigation is instant.
- Skeleton shimmer during data loading is fine — use the scaffold's
  `.skeleton` class.

## Structural moves that read current
- **Hero with inline CTA input**: single email / command-palette-style input
  as the primary hero element, button "inline" right-side, not below. Suggests
  you can start using the product without clicking through.
- **Logo bar**: "Trusted by" strip with 5–6 customer logos in grey, below
  hero. Small (28–32px tall), opacity 0.6.
- **Feature cards with icons**: 3-up grid, card = lucide-icon top, h3, 2-line
  description, "Learn more" ghost link. No fluff copy.
- **Comparison table**: if the product has tiers, show them as a table (not
  stacked cards) — tight, informational.
- **Footer**: 4 columns — Product / Resources / Company / Social. Thin border
  top, small type, muted colors.

## DO-NOTs
- No cursor effects, magnetic buttons, mesh gradients — this doctrine is
  utility-first, not expressive. Reach for `playful_chromatic` if that's
  what you want.
- No Playfair / Cormorant / editorial serif — this is not a magazine.
- No dark mode UNLESS the product is explicitly dev-tools-at-3am. Even then,
  the shadcn `.dark` class toggle is the correct pattern — don't rewrite
  the doctrine, just add a toggle.
- No bento asymmetry. Equal-grid cards are fine here.
- No oversized display type — 48–56px feature is the ceiling.

## Hero shape — concrete JSX template

```tsx
export function Hero() {
  return (
    <section className="relative">
      {/* Fixed top nav with backdrop blur */}
      <nav className="sticky top-0 z-20 backdrop-blur-sm bg-white/80 border-b">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <span className="w-6 h-6 rounded-md bg-primary" />
            Triage
          </a>
          <ul className="hidden md:flex gap-8 text-sm text-muted-foreground">
            <li><a href="/features">Features</a></li>
            <li><a href="/pricing">Pricing</a></li>
            <li><a href="/changelog">Changelog</a></li>
            <li><a href="/docs">Docs</a></li>
          </ul>
          <div className="flex items-center gap-3 text-sm">
            <a href="/signin" className="text-muted-foreground">Sign in</a>
            <a href="/signup" className="bg-primary text-primary-foreground rounded-lg px-4 py-1.5">Get started</a>
          </div>
        </div>
      </nav>

      {/* Hero: one-sentence claim + subtitle + inline-CTA input */}
      <div className="max-w-4xl mx-auto px-6 py-24 text-center space-y-8">
        <span className="inline-flex items-center gap-2 bg-primary/5 border border-primary/20 rounded-full px-3 py-1 text-[11px] uppercase tracking-wider">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          New · realtime bug triage
        </span>
        <h1 className="text-5xl md:text-6xl font-semibold tracking-tight leading-[1.1]">
          Ship better,<br/>software faster.
        </h1>
        <p className="text-lg text-muted-foreground max-w-xl mx-auto">
          Triage routes every incoming bug to the right engineer in under
          thirty seconds. No more triage stand-ups.
        </p>
        {/* Inline-CTA input — work-email + start-trial button fused */}
        <form className="flex items-center gap-2 max-w-md mx-auto bg-white border rounded-xl p-1.5">
          <input
            type="email"
            placeholder="you@company.com"
            className="flex-1 px-3 py-1.5 bg-transparent outline-none text-sm"
          />
          <button className="bg-primary text-primary-foreground rounded-lg px-4 py-1.5 text-sm whitespace-nowrap">
            Start free trial
          </button>
        </form>
      </div>

      {/* Trusted-by logo strip */}
      <div className="max-w-6xl mx-auto px-6 py-10 border-t border-b">
        <p className="text-center text-xs uppercase tracking-widest text-muted-foreground mb-6">
          Trusted by engineering teams at
        </p>
        <div className="flex flex-wrap justify-center items-center gap-10 opacity-60">
          {["Stripe","Vercel","Linear","Resend","Clerk","Railway"].map(n =>
            <span key={n} className="text-lg font-semibold">{n}</span>
          )}
        </div>
      </div>

      {/* Feature cards — 3-up grid with lucide icons */}
      <div className="max-w-6xl mx-auto px-6 py-20 grid md:grid-cols-3 gap-6">
        {["Instant routing","Zero config","Full audit trail"].map(title =>
          <div key={title} className="rounded-xl border bg-white p-6 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <span className="w-5 h-5 bg-primary rounded-sm" />
            </div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">Two-line description of this value prop, tight copy.</p>
            <a href="#" className="inline-block text-sm text-primary">Learn more →</a>
          </div>
        )}
      </div>
    </section>
  );
}
```

Notes: `backdrop-blur-sm bg-white/80` sticky nav is the corpus-dominant
pattern. Hero copy is ONE sentence, not stacked taglines. Inline-CTA input
+ button fused is the specific move this cluster uses over standalone CTAs.
`bg-primary/5 border border-primary/20` pill badge with pulsing dot is the
"new feature" announcement pattern across the cluster. `rounded-xl` cards,
`text-[11px]` micro-type on meta chips, `bg-primary/10` icon backgrounds.

## Reference sites (scraped corpus)
- bugtrackr ("Triage — Ship better, software faster.")
- assetwise-insights
- commcalc
- continuum-daily (habit tracker)
- new-venture-news (Startup Scout)
- thepipelineiq

Also external for reference: linear.app, vercel.com/dashboard, clerk.com,
resend.com — all utilities-done-well in this exact visual language.
