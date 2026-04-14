# Build a React app from a scaffold

The scaffold is a foundation, not a final product. Map the request, read what's there, then refine incrementally.

## When
- User says "build", "make", "create", or "I need a/an" + an app name
- The app does not already exist in `workspace/deliverables/`
- Default if the prompt doesn't match `iteration`, `in-place-cwd`, `visual-clone`, or `build-multi-page`
- Single-page scope: counter, calculator, dice roller, timer, todo, color picker, calendar, quiz, note-taking, chart, single-form contact page

## When NOT
Branch to `build-multi-page` instead if the prompt mentions: dashboard, multi-page, routing, tabs, sidebar, nav, login, signup, auth, profile, settings, SaaS, admin panel, OR asks for 2+ explicit pages. Those apps need dependency-ordered building (routing → pages → auth → protected pages), which this skill doesn't handle.

## Pipeline (incremental, not one-shot)

### 1. Scaffold
`project_init(name)` — kebab-case from prompt. The scaffold output tells you what template was picked (react-app / dashboard / data-viz / landing / game / etc) and what's already in `src/`.

### 2. Map requirements against scaffold defaults
- Missing components? (e.g. user asked for a pricing table, scaffold only has a hero) → plan to add them
- Data needs? (list of items, form state) → plan the state shape
- Styling? (dark theme, specific brand colors) → plan CSS variable overrides

### 3. Read the scaffold entry point
`file_read(path="workspace/deliverables/<name>/src/App.tsx")` — see what placeholder/example code is there. The scaffold ships with stub content like `<div>Loading...</div>` or a sample hero. You need to know what's there before overwriting.

### 4. Replace, don't append
`file_write(path="workspace/deliverables/<name>/src/App.tsx", content=<COMPLETE TSX>)` — overwrite the placeholder with the real implementation. Full code, no `// TODO`, no `// Phase 1` comments. One file_write should produce a working app for most simple cases (counter, todo, calc, clock, dice, color picker).

### 5. Compile
`shell_exec("cd workspace/deliverables/<name> && npm run build")` — must compile clean. If it fails → switch to `build-recovery`.

### 6. QA
`undertow(path="workspace/deliverables/<name>/dist/index.html", expect="<plain-language description of what should render>")`. If FAIL → switch to `qa-loop`.

### 7. Deliver
`message_result(text="<one-line summary>", attachments=["workspace/deliverables/<name>/dist/index.html"])`

## Decomposition for larger apps (>200 LOC)
After reading the scaffold (step 3), if the app is genuinely modular:
1. `file_write` shared types → `src/types.ts`
2. `file_write` each component → `src/components/<Name>.tsx`
3. `file_write` App.tsx that imports them
4. Then build / undertow / deliver as above

Don't decompose for simple apps — one App.tsx is more reliable than 4 files for a counter.

## Available components (react-app scaffold)

Import from `./components/ui` — these are the only exports:

**Primitives:** `Text`, `Heading`, `Flex`, `Box`, `Image` — use for layout/typography instead of hallucinating Chakra/Mantine APIs.

**Interactive:** `Button`, `Input`, `Select`, `Switch`, `Dropdown`, `Dialog`, `Tooltip`, `Accordion`, `Alert`, `Badge`, `Progress`, `Skeleton`.

**Rich widgets:** `Card`, `Avatar`, `StarRating`, `GlowCard`, `Parallax`, `AnimatedCounter`, `BeforeAfter`, `ColorPicker`, `Timeline`, `Kanban`, `AnnouncementBar`, `Marquee`, `TypeWriter`, `GradientText`, `ScrollReveal`, `Slideshow`, `RichTextEditor`, `FileManager`, `CommandPalette`, `Calendar`, `NotificationCenter`, `AudioPlayer`, `VideoPlayer`.

**If you need anything else** (e.g. a tab bar, a table, a menubar): use raw HTML + Tailwind, don't import a name you haven't seen above. The scaffold has no `Tabs`, `Table`, `Menu`, `Drawer`, `Sheet`, `Popover`, `Carousel`, `Slider`, `Checkbox`, `Radio`, `Form`, `Label`, `Separator`, `Spinner`, `Pagination`. Build them from `<div>` / `<button>` / `<input>` + classes.

## Gotchas
- **No narration.** Every assistant turn is exactly one tool call, no `content` text.
- **Imports must match JSX.** Every `<PascalCase />` tag in your JSX must either (a) be in the import statement from `./components/ui`, or (b) be defined locally in the same file. Undefined components compile (they're just `undefined`) but crash at runtime with "React.createElement: type is invalid." Scan your import list against every `<Foo>` you write — a mismatch ships a blank page. Tsunami's deliver gate catches this and refuses; you'll waste iterations recovering.
- **`import "./index.css"` at the top of App.tsx.** The scaffold provides base styles.
- **Use scaffold component classes** — `.container .card .button .button.primary .grid .grid-3 .flex .flex-col .flex-center .gap-4 .p-8 .text-bold .text-2xl .text-muted` — not inline styles for layout.
- **Never `dangerouslySetInnerHTML`** unless the user explicitly asked for HTML/markdown rendering.
- **Always provide `expect` to undertow** — describe what should render, not the implementation.
- **Cleanup before adding.** If the scaffold has a "Welcome to React" header, remove it first; don't paste your content underneath it.
- **After 3 failed `file_edit` attempts on the same file, switch to `file_write`.** Each partial edit deepens the mess (unclosed tags, half-removed imports). A clean rewrite compiles predictably.

## Design constraints (quality floor)

These prevent the generic "AI slop" look that Manus/v0/Lovable all flag as a core failure mode. Apply every build, no exceptions.

- **Max 4-5 colors total.** Primary, surface/background, text, accent, one neutral. Any more and it looks like a pitch deck. Define as CSS variables in `src/index.css`, reference everywhere.
- **Max 2 font families.** A heading font + a body font. Usually just one (body font inheriting for headings). Don't pile on decorative fonts.
- **All styles in the design system, not ad-hoc in components.** Build component classes in CSS, reference them in JSX. Never `style={{color: '#abc123', padding: '17px'}}` inline — that's how designs drift across pages.
- **Mobile-first sizing.** Minimum touch target 44x44px for any interactive element. Inputs at least 16px font (smaller triggers iOS Safari zoom-on-focus). Start every layout in mobile viewport, scale up.
- **Stay strictly in scope.** Don't add "nice-to-have" features the user didn't request. Counter app = counter. Landing page = hero + CTA. Gallery = the images. Over-delivery creates maintenance debt and rarely matches what the user actually wanted.

## Live data — use real APIs, not mocks

If the prompt says "live", "real-time", "current", "latest", or names a specific market/feed, fetch from a real public API. Mocked-with-Math.random hardcodes prices from your training data that are already stale (BTC at "$65k" when it's since moved). The user sees WRONG data and calls it broken. A free CORS-enabled API is always better than a stub.

Known-good browser-callable APIs (no key, CORS-enabled, HTTPS):

| Domain | API | Example endpoint |
|---|---|---|
| Crypto prices | CoinGecko | `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true` |
| Weather | Open-Meteo | `https://api.open-meteo.com/v1/forecast?latitude=40.7&longitude=-74.0&current_weather=true` |
| Stocks/FX | Yahoo Finance (via yfinance proxies, check freshness) | — |
| Code/repos | GitHub | `https://api.github.com/repos/OWNER/REPO` |
| Exchange rates | Frankfurter | `https://api.frankfurter.app/latest?from=USD&to=EUR` |
| News (headlines) | Hacker News | `https://hacker-news.firebaseio.com/v0/topstories.json` |

Pattern:
```tsx
useEffect(() => {
  const load = async () => {
    const r = await fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true")
    setPrices(await r.json())
  }
  load()
  const id = setInterval(load, 15000)
  return () => clearInterval(id)
}, [])
```

Only mock when: (a) the prompt explicitly says "mocked" or "fake", (b) no free public API exists for that data domain, or (c) the API requires a key we don't have. When you do mock, say so in the UI ("mock data; refresh to see variance") — don't let it LOOK live when it isn't.
