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

**Prop signatures** (scaffold APIs — NOT Radix/shadcn/Headless conventions). Getting these wrong triggers TS2322 and a fix-loop that burns 4+ iters — seen in chiptune session `tsu_prog_chiptune_1776231968`:

| Component | Props |
|---|---|
| `Switch` | `{ checked?: boolean, value?: boolean, onChange?: (b: boolean) => void, onCheckedChange?: (b: boolean) => void, onValueChange?: (b: boolean) => void, label?, size? }` — scaffold normalizes: `checked` **and** `value` both accepted for state; `onChange` / `onCheckedChange` (Radix) / `onValueChange` (shadcn) are all accepted aliases. No TS2322 regardless of which convention you use. Source: `scaffolds/react-app/src/components/ui/Switch.tsx` commit `5d85c65`. |
| `Select` | `{ value: string, onChange?: (v: string) => void, onValueChange?: (v: string) => void, options: {value, label}[], placeholder?, label? }` — scaffold normalizes: both `onChange` and `onValueChange` accepted. `options` is an array of `{value, label}` objects, NOT `<option>` children (no children support). Source: `scaffolds/react-app/src/components/ui/Select.tsx` commit `5d85c65`. |
| `Dialog` | `{ open?: boolean, isOpen?: boolean, onClose?: () => void, onOpenChange?: (open: boolean) => void, title?, description?, children?, actions? }` — scaffold normalizes: `open` **and** `isOpen` both accepted; `onClose` (plain) and `onOpenChange` (Radix-style; invoked with `false` on dismiss) are both accepted aliases. Source: `scaffolds/react-app/src/components/ui/Dialog.tsx` commit `5d85c65`. |
| `Dropdown` | `{ trigger: ReactNode, items: {label, onClick, icon?, danger?, divider?}[], align?: "left"\|"right" }` — `trigger` is a **named prop** (not children — `<Dropdown><Button/></Dropdown>` renders nothing). Pass `<Dropdown trigger={<Button>…</Button>} items={[...]} />`. Items is an array of objects, not JSX children. Source: `scaffolds/react-app/src/components/ui/Dropdown.tsx`. |
| `Chart` | `{ type?: "line"\|"bar"\|"pie", data: {x: string\|number, y: number}[], height?, color?, palette?, showGrid?, showLegend?, showTooltip? }` — **data MUST be `{x, y}[]` objects** — `{value: n}[]` / `number[]` / `{name, count}[]` all fail TS2739. Map first: `data.map(p => ({x: p.name, y: p.count}))`. Seen in crypto session `tsu_prog_crypto_1776237712` — 21-iter regression |
| `MetricCard` | `{ label, value, delta?, deltaLabel?, prefix?, suffix?, hint?, icon?, invertDelta?, className?, style? }` — `value` is ReactNode (can be number, string, or JSX) |
| `StatGrid` | `{ stats?: {label, value, delta?, ...}[], columns?: number, minWidth?: number, gap?: number, children?, className? }` — pass `stats` array OR `children` (MetricCards). `gap` is **plain `number`** in StatGrid (default 16, passed as inline `style={{ gap }}` in pixels) — wider than Flex's scaled union. `<StatGrid gap={16}>` / `<StatGrid gap={4}>` both pass; `<StatGrid gap="4">` fails TS2322 (`Type 'string' is not assignable to type 'number'`). Don't confuse StatGrid.gap (pixel number) with Flex.gap (scaled `0\|1\|2\|3\|4\|6\|8` Tailwind-class index). Source: `scaffolds/react-app/src/components/ui/StatGrid.tsx`. |
| `Flex` | `{ direction?: "row"\|"col", align?: "start"\|"center"\|"end"\|"stretch", justify?: "start"\|"center"\|"end"\|"between"\|"around", gap?: 0\|1\|2\|3\|4\|6\|8, wrap?: boolean, children, ...HTMLAttributes }` — **that is the complete prop surface**. Same numeric-union discipline on `gap` as StatGrid: `<Flex gap={2}>` passes, `<Flex gap="2">`/`<Flex gap="sm">` fail TS2322. **NO `mt`, NO `mb`, NO `my`, NO `mx`, NO `p`, NO `px`, NO `py`, NO `grow`, NO `items` props — those FAIL TS2322 `Property 'mt' does not exist on type 'IntrinsicAttributes & FlexProps'`.** Chakra/Mantine margin-shorthand leak. For spacing use a parent `<div className="mt-4">` wrapper or scaffold utility classes (`.p-4`/`.p-8`); for cross-axis use `align="center"` (NOT `items="center"` — `items` is the Tailwind class name, not the prop name). Seen in crypto session `tsu_prog_crypto_1776360856` — 8+ fires of `mt`/`mb`/`my`/`items` across 3 rebuild attempts (#52-VARIANT FLEX-MARGIN-PROPS); earlier `gap="2"` string-coercion fires in lunchvote `tsu_prog_lunchvote_1776331493` + watchlist `tsu_prog_watchlist_1776357020`. |
| `StarRating` | `{ rating?: number, value?: number, max?, size?, color?, onChange?: (r: number) => void, onValueChange?: (r: number) => void }` — scaffold normalizes: `rating` **and** `value` both accepted for current rating; `onChange` / `onValueChange` both accepted for the change handler. `<StarRating rating={n} />`, `<StarRating value={n} />`, `<StarRating value={n} onValueChange={setN} />` all compile. Source: `scaffolds/react-app/src/components/ui/StarRating.tsx` commit `5d85c65`. |
| `Alert` | `{ type?: AlertKind, variant?: AlertKind, title?: string, children, onDismiss?, className? }` where `AlertKind = "info" \| "success" \| "warning" \| "error" \| "default" \| "destructive"` — **NO `kind`, NO `description`, NO `message`, NO `severity`**. Body text goes in `children`, not a `description` prop. Use `variant="destructive"` (shadcn alias) or `type="error"`; `"danger"` fails TS2322. Seen in crypto session `tsu_prog_crypto_1776353600` — TS2322 on `kind="danger"` hallucination (3-form cluster: Chakra/Radix/MUI leak) |
| `Button` | `{ variant?, size?, ...ButtonHTMLAttributes }` where `variant = "primary" \| "default" \| "secondary" \| "ghost" \| "outline" \| "danger" \| "destructive" \| "link"` and `size = "sm" \| "md" \| "lg" \| "icon"` — **NOT polymorphic**: no `as` prop (that's Heading-only). For Button-as-link use wrap pattern: `<Link to="/foo"><Button variant="ghost">Click</Button></Link>`. `<Button as={Link}>` fails TS2322. Seen in leads session `tsu_prog_leads_1776336039` — TS2322 ×2 on `as={Link}` (cross-class leak from `bc2abe4` Heading polymorphic-as fix) |
| `Badge` | `{ children?, className? }` — only. **NO `variant`, NO `color`, NO `size`**. For tinting, override via `className` (e.g. `className="bg-red-500/15 text-red-400"`). Scaffold default is accent-tinted |
| `Text` | `{ as?: "span" \| "p" \| "div", ...HTMLAttributes }` — **only** `as` + className. **NO `size`, NO `weight`, NO `bold`, NO `variant`**. Size/weight goes via className (Tailwind scale: `text-sm`/`text-lg`/`text-2xl`, `font-bold`/`font-medium`). Chakra/Mantine/Radix Text convention leaks (`<Text size="xl" bold>`) fail TS2322. **`as` union is restricted to `"span" \| "p" \| "div"` — `<Text as="label">`, `<Text as="h1">`, `<Text as="button">` all fail TS2322 (`Type '"label"' is not assignable to type '"span" \| "p" \| "div" \| undefined'`). For labelable form controls use native `<label htmlFor="id">` directly; for headings use `<Heading as="h1">` (Heading IS fully polymorphic). Seen in chiptune session `tsu_prog_chiptune_1776359040` — 4 fires of `<Text as="label">` on form-control label blocks, all TS2322.** |
| `Heading` | `{ level?: 1-6, size?: "sm"\|"md"\|"lg"\|"xl"\|"2xl"\|"3xl", as?: "h1".."h6" \| string, ...HTMLAttributes }` — `level` is **numeric literal** `{1\|2\|3\|4\|5\|6}`, NOT string `"h1"`/`"h2"` (HTML-tag-name convention — use `as="h1"` for that). `size` is **Tailwind-scale strings**, NOT Radix numeric (`"3"`/`"4"` fail TS2322). `as` IS supported (only polymorphic scaffold component). Seen in lunchvote session `tsu_prog_lunchvote_1776331493` — TS2322 on `<Heading level="h1">` (PROMOTED n=5 across s9/s24/s26/s35/s38). |

**Cross-cutting rule — imports match JSX, always:** every `<PascalCase />` tag must appear in the `import { ... } from "./components/ui"` statement. Using `<Badge>` or `<Text>` without importing compiles to TS2304 / crashes at runtime — seen in chiptune `tsu_prog_chiptune_s112` (Text missing import) and hnresearch `tsu_prog_hnresearch_s124` (Badge missing import). Scan imports against JSX before `shell_exec build`.

**Rich widgets:** `Card`, `Avatar`, `StarRating`, `GlowCard`, `Parallax`, `AnimatedCounter`, `BeforeAfter`, `ColorPicker`, `Timeline`, `Kanban`, `AnnouncementBar`, `Marquee`, `TypeWriter`, `GradientText`, `ScrollReveal`, `Slideshow`, `RichTextEditor`, `FileManager`, `CommandPalette`, `Calendar`, `NotificationCenter`, `AudioPlayer`, `VideoPlayer`.

**If you need anything else** (e.g. a tab bar, a table, a menubar): use raw HTML + Tailwind, don't import a name you haven't seen above. The scaffold has no `Grid`, `Tabs`, `Table`, `Menu`, `Drawer`, `Sheet`, `Popover`, `Carousel`, `Slider`, `Checkbox`, `Radio`, `Form`, `Label`, `Separator`, `Spinner`, `Pagination`. For grids, use `<div className="grid grid-2">` / `<div className="grid grid-3">` (scaffold classes) or `<StatGrid>` (for MetricCard arrays) — `<Grid>` import fails TS2307. Seen in leads session `tsu_prog_leads_1776336039` — 5 page files all imported nonexistent `Grid` from `./components/ui`. Build them from `<div>` / `<button>` / `<input>` + classes.

## Gotchas
- **No narration.** Every assistant turn is exactly one tool call, no `content` text.
- **Imports must match JSX.** Every `<PascalCase />` tag in your JSX must either (a) be in the import statement from `./components/ui`, or (b) be defined locally in the same file. Undefined components compile (they're just `undefined`) but crash at runtime with "React.createElement: type is invalid." Scan your import list against every `<Foo>` you write — a mismatch ships a blank page. Tsunami's deliver gate catches this and refuses; you'll waste iterations recovering.
- **`import "./index.css"` at the top of App.tsx.** The scaffold provides base styles.
- **Use scaffold component classes** — `.container .card .button .button.primary .grid .grid-3 .flex .flex-col .flex-center .gap-4 .p-8 .text-bold .text-2xl .text-muted` — not inline styles for layout.
- **Never `dangerouslySetInnerHTML`** unless the user explicitly asked for HTML/markdown rendering.
- **Always provide `expect` to undertow** — describe what should render, not the implementation.
- **Cleanup before adding.** If the scaffold has a "Welcome to React" header, remove it first; don't paste your content underneath it.
- **After 3 failed `file_edit` attempts on the same file, switch to `file_write`.** Each partial edit deepens the mess (unclosed tags, half-removed imports). A clean rewrite compiles predictably.
- **Don't re-read files you've already seen.** One `file_read` per file is enough — the contents are in your context. If a compile error names a line, fix it with `file_edit` against that line; don't `file_read` the whole file again to "check what's there." Re-reading the same file three times in a row is a stall loop that eats your iteration budget with zero progress — seen in pomodoro eval, session /tmp/tsu_prog_pomodoro_1776217864/ had 5 consecutive `file_read index.css` calls before timeout.
- **When `tsc` reports an error at a specific line, use `file_edit` at that line.** Don't rewrite the whole file — rewrites generate new syntax errors in different places. Extract the error line number from the compile message, craft a focused `file_edit` with `old_text` matching the broken region and `new_text` fixing just that region.

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

## Web Audio API (for synth, sequencer, chiptune, sound-FX builds)

`OscillatorNode.type` is a strict union: **`"sine" | "square" | "sawtooth" | "triangle" | "custom"`**. Any other string fails TS2322 ("Type 'string' is not assignable to type 'OscillatorType'"). Common slips:

- ❌ `osc.type = "noise"` — there is no noise oscillator type
- ❌ `osc.type = "white_noise"` / `"pink_noise"` — no
- ❌ `osc.type = "pulse"` — no (use square + duty-cycle workaround if needed)

**Indirect / conceptual form (distinct from the direct-form cases above)** — defining your own `Waveform`/`ChannelType` that includes `"noise"` and then assigning it to `osc.type` fails the same way, just with a widened error message. The type inclusion is the trap, not the specific string literal:

```ts
type Waveform = "square" | "triangle" | "noise"   // ← the widening lives here
interface Channel { id: number; type: Waveform }
// ...
osc.type = channel.type   // ❌ TS2322: Type 'Waveform' is not assignable to type 'OscillatorType'
                          //          Type '"noise"' is not assignable to type 'OscillatorType'
```

Seen in chiptune sessions `tsu_prog_chiptune_1776349531` (`ChannelType` → `OscillatorType`), `1776353247` (`Waveform` → `OscillatorType` via `osc.type = channel.type`), plus direct-form repros s24/s28/s30/s35. Fix the **shape**, not the symptom: don't include `"noise"` in the waveform union at all — make the noise channel a distinct code path, not a distinct waveform string. Canonical pattern:

```ts
type OscWaveform = "square" | "triangle" | "sawtooth" | "sine"   // OscillatorType-compatible only
type ChannelKind = OscWaveform | "noise"                         // app-domain superset
interface Channel { id: number; kind: ChannelKind }

function playChannel(ctx: AudioContext, ch: Channel, dest: AudioNode) {
  if (ch.kind === "noise") {
    const src = makeNoise(ctx)          // AudioBufferSourceNode path
    src.connect(dest); src.start()
    return
  }
  const osc = ctx.createOscillator()
  osc.type = ch.kind                    // narrowed to OscWaveform by the branch — no cast needed
  osc.connect(dest); osc.start()
}
```

If you truly can't restructure (e.g. mid-build compile-fix only), the one-line rescue is `osc.type = ch.kind as OscillatorType` **guarded** by `if (ch.kind !== "noise")` — the cast alone is unsafe because runtime `"noise"` will silently produce an `InvalidStateError` from the Web Audio engine.

**For noise channels** (chiptune NES-style), use `AudioBufferSourceNode` with a random-filled buffer:

```ts
function makeNoise(ctx: AudioContext, durationSec = 1) {
  const buf = ctx.createBuffer(1, ctx.sampleRate * durationSec, ctx.sampleRate)
  const data = buf.getChannelData(0)
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
  const src = ctx.createBufferSource()
  src.buffer = buf
  return src  // connect to gain → destination, then src.start()
}
```

For pitched noise (snare-like), filter the noise with a `BiquadFilterNode` (bandpass, Q=10).
