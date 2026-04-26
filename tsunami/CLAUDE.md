# tsunami — cold-start, choose your own adventure

> You are an AI coding agent (Claude Code or equivalent harness) that just landed in
> `tsunami/` — the patterns + scaffold-library subdir of the repo. **Tsunami is not
> a binary you invoke; it is files you read.** This doc is the only thing you have
> to read to know what to do. If after reading it you still can't answer
> "user wants X, I match it to scaffold Y, I read these N files, I start building" —
> the doc has failed. File a fix.

## TL;DR — 30-second skim

You match work to scaffolds. Pick a scaffold from the catalog, read the matching
`plan_scaffolds/<name>.md` + `../scaffolds/<name>/__fixtures__/drone_natural.tsx`
(your locked component vocab), build, verify with `vision_gate.py` +
`undertow.py`, let `circulation.py` catch you if you spiral, ship. Don't try
to be clever — the scaffolds are already clever. **The directory `../scaffolds/`
is the product catalog and is off-limits for ad-hoc edits.** Orchestrator is
Claude (you, via API) — self-hosted LLMs were deleted 2026-04-26.

Your first move: read the choose-your-own-adventure table below. Match the user's
request to a row. That row tells you the next 3 files to read.

## What tsunami is, in one paragraph

Tsunami is a **scaffold executor**. The hard work — picking the right project shape,
the right visual style, the right QA strategy, the right game genre — is already done
and lives as a catalog of named scaffolds in `../scaffolds/` and in the four
`*_scaffolds/` directories at this level. Your job is to **match the user's request
to the right scaffolds, then drive the agent loop that fills the scaffold in and
verifies the build with screenshots and Playwright levers.** Don't think of this as
a sophisticated reasoning agent. Think of it as a fast, accurate scaffold matcher
plus a relentless visual-grounding QA loop.

The agent loop is **Claude (you, via API) as orchestrator**. Tsunami is the framework
around you. There is no local LLM anymore — that infrastructure was deleted on
2026-04-26. If you find imports of `serve_transformers`, `gemma_args`,
`chat_template_safety`, `adapter_router`, `adapter_swap`, `wilson_loop`, or
`model_fallback`, they are dead and need to be stripped or refactored.

## Choose your own adventure — what work just landed?

Match the user's request to one row. Each row tells you which scaffold to
clone-and-fill, which plan_scaffold to read for conventions, which style_scaffold
to apply for visuals, and which undertow_scaffold to use for QA.

### Web apps (React / Vite / TS)

| User says... | scaffold | plan | undertow gate |
|---|---|---|---|
| "build me a React app", "single-page app" | `react-app` | `plan_scaffolds/react-build.md` | vision + runtime smoke |
| "landing page", "marketing site", "splash" | `landing` | `plan_scaffolds/landing.md` | vision + scroll-anim QA |
| "dashboard", "admin panel", "sidebar layout" | `dashboard` | `plan_scaffolds/dashboard.md` | vision + recharts API |
| "data viz", "chart this CSV", "graph my data" | `data-viz` | `plan_scaffolds/data-viz.md` | vision + chart-type catalog |
| "form", "spreadsheet upload", "file ingester" | `form-app` | `plan_scaffolds/form-app.md` | vision + validation conventions |
| "fullstack", "CRUD app", "local-first" | `fullstack` | `plan_scaffolds/fullstack.md` | vision + shared/types.ts pin |
| "real-time chat", "WebSocket app", "rooms + presence" | `realtime` | `plan_scaffolds/realtime.md` | vision + reconnect protocol |
| "chatbot", "AI app", "streaming chat" | `ai-app` | `plan_scaffolds/ai-app.md` | vision + SSE wire format |
| "auth", "login", "JWT users" | `auth-app` | `plan_scaffolds/auth-app.md` | vision + `useAuth` contract |

### No-vision-gate adventures (need bespoke QA harness — see `../scaffolds/GAPS.md`)

| User says... | scaffold | plan | gate type |
|---|---|---|---|
| "REST API", "no UI", "OpenAPI spec" | `api-only` | `plan_scaffolds/api-only.md` | OpenAPI handler-vs-spec probe |
| "Chrome extension", "browser plugin" | `chrome-extension` | `plan_scaffolds/chrome-extension.md` | playwright load-unpacked |
| "Electron desktop app" | `electron-app` | `plan_scaffolds/electron-app.md` | playwright-electron mode |

### Games

| User says... | scaffold | genre template | engine |
|---|---|---|---|
| "platformer", "Mario-like", "side-scrolling action" | `gamedev/platformer/` | `genre_scaffolds/platformer.md` | `scaffolds/engine/` (WebGPU) |
| "fighter", "Street Fighter-like", "1v1 combat" | `gamedev/fighting/` | `genre_scaffolds/fighter.md` | engine |
| "JRPG", "Final Fantasy-like", "turn-based" | `gamedev/jrpg/` | `genre_scaffolds/jrpg.md` | engine |
| "FPS", "Doom-like", "first person shooter" | `gamedev/fps/` | `genre_scaffolds/fps.md` | engine |
| "beat-em-up", "Streets of Rage" | `gamedev/beat_em_up/` | `genre_scaffolds/beat_em_up.md` | engine |
| "racing", "kart racer", "Mario Kart-like" | `gamedev/racing/` | `genre_scaffolds/kart_racer.md` | engine |
| "stealth", "Metal Gear-like" | `gamedev/stealth/` | `genre_scaffolds/stealth.md` | engine |
| "action adventure", "Zelda-like" | `gamedev/action_adventure/` | `genre_scaffolds/action_adventure.md` | engine |
| something more exotic | `gamedev/custom/` | check `genre_scaffolds/` for: action_rpg_atb, immersive_sim, magic_hoops, metroidvania, metroid_runs, ninja_garden, open_world, rhythm_fighter, rts, ninja_garden | engine |

For any game with retro-game pattern matching (sprite styling, enemy behaviors,
level structure), check `../scaffolds/.claude/nudges/<year>_<game>/` for the
existing scrape catalog (Castlevania I & II, Dragon Quest, etc.).

### Other

| User says... | scaffold | plan |
|---|---|---|
| "CLI tool", "command-line script" | `cli` | (light-weight, scaffold-driven) |
| "mobile app" | `mobile` | (light-weight) |
| "infrastructure", "deploy script" | `infra` | (light-weight) |
| "training data prep" (rare now — local-LLM era) | `training` | (likely dead path; verify before building) |

**Lighter scaffolds (no README — read the dir contents directly):** `cli`,
`game`, `gamedev`, `infra`, `mobile`, `training`, `web`. These are smaller
templates without a polished scaffold catalog. The gamedev sub-genres live at
`../scaffolds/gamedev/{action_adventure, beat_em_up, cross, custom, fighting,
fps, jrpg, platformer, racing, stealth}/`.

### Work-type plans — orthogonal to scaffold choice

These plan_scaffolds describe HOW you're working, regardless of WHICH scaffold
you picked. Use them in addition to the scaffold-specific plan.

| Plan | When to use |
|---|---|
| `plan_scaffolds/refactor.md` | User has an existing codebase, wants changes. Walk: Target → Baseline → Changes → Verify → Deliver. |
| `plan_scaffolds/replicator.md` | Compositional replica — build an inner app INSIDE an outer visual shell (e.g. pomodoro timer inside an Apple-Watch frame). Two scaffolds nested. |
| `plan_scaffolds/research.md` | Research / report task with no executable deliverable. Walk: Question → Sources → Analysis → Report. No vision_gate; deliverable is a markdown doc. |

### When nothing matches

1. Don't invent a new scaffold mid-build. The catalog exists for a reason.
2. Pick the **closest** existing scaffold and tell the user "I'll use `react-app`
   as the base, here's what I'm adapting" — let them confirm before you diverge.
3. If the work is genuinely new-shape, write a one-paragraph note in
   `../scaffolds/GAPS.md` proposing the new scaffold as a future build, then
   fall back to the closest match.

## Visual style — orthogonal to scaffold choice

After picking a scaffold, pick a visual style (or let the user pick). Style is
chosen from `style_scaffolds/`. Each style has a matching `undertow_scaffolds/`
file with the QA approach for that aesthetic.

| Style | When to use | undertow_scaffold |
|---|---|---|
| `atelier_warm.md` | Warm, hand-crafted, Etsy/maker brands | `undertow_scaffolds/atelier_warm.md` |
| `brutalist_web.md` | Raw, structural, exposed-grid type-driven | `undertow_scaffolds/brutalist_web.md` |
| `cinematic_display.md` | Dark, immersive, hero-image dominant | `undertow_scaffolds/cinematic_display.md` |
| `editorial_dark.md` | NYT/long-read, serif-led, dark mode | `undertow_scaffolds/editorial_dark.md` |
| `magazine_editorial.md` | Magazine spread, mixed columns + pull quotes | `undertow_scaffolds/magazine_editorial.md` |
| `newsroom_editorial.md` | News site, dense above-the-fold | `undertow_scaffolds/newsroom_editorial.md` |
| `photo_studio.md` | Portfolio, image-first, minimal chrome | `undertow_scaffolds/photo_studio.md` |
| `playful_chromatic.md` | Bright, animated, motion-rich | `undertow_scaffolds/playful_chromatic.md` |

The default for React-app-family scaffolds is `react-app`'s baked-in atmospheric
dark theme (Plus Jakarta Sans, deep palette). Only override when the user asks
for a specific style.

## How the agent loop runs (the standing wave, simplified)

You don't need to understand the full loop to be useful — the loop's job is to
match work to scaffolds and verify visually. But here's the shape:

1. **Read user request** → pick scaffold, plan_scaffold, style_scaffold (the
   choose-your-own-adventure above)
2. **Read** `../scaffolds/<scaffold>/README.md` and
   `../scaffolds/<scaffold>/__fixtures__/drone_natural.tsx` (the locked prop vocab
   you must use — fixtures exist so you don't drift the API surface)
3. **Read** `plan_scaffolds/<scaffold>.md` (conventions + gotchas specific to that
   build target)
4. **Build** by writing files in a working dir, using tools from `tools/`
5. **Verify** via `deliver_gates.py` — cascading gates that must all pass:
   - `code_write_gate` — did you write anything?
   - `asset_existence_gate` — do all `<img>` tags reference real files?
   - `prop_type_gate` — does `tsc --noEmit` pass?
   - `runtime_smoke_gate` — does `page.goto()` not throw?
   - `vision_gate` — screenshot → Claude vision → "list visual issues" → loop
   - `accessibility_gate` — axe-core (future)
6. **If a gate fails**, `undertow.py` pulls Playwright levers (screenshots,
   keypresses, clicks, console reads) and reports back with concrete failures.
   Fix and loop.
7. **If you spiral** (3+ context overflows, repeated identical errors, infinite
   read loops), `circulation.py` catches you, compresses context, warns you,
   and gives you a recovery window. If you fail recovery, it breaks cleanly
   rather than runaway.

## Three load-bearing primitives — read these before you touch anything visual

If your work touches build verification, visual matching, or QA in any way,
read these three files first. They are the most-load-bearing modules in
the entire codebase.

- **`vision_gate.py`** — verifies the build by screenshot + Claude vision API.
  Currently hardcoded to a Qwen3.6-VL endpoint that no longer exists; needs swap
  to `anthropic.Anthropic().messages.create(...)` with vision content. **Refactor
  target.**
- **`undertow.py`** — Playwright lever-puller. Async wrapper that takes
  screenshots, presses keys, clicks elements, reads the console, and returns
  a structured `QAReport`. The "wander off path then turn around if too crazy"
  pattern lives here. Don't touch the lever API — agents depend on it.
- **`circulation.py`** — circuit-breaker state machine
  (`flowing → eddying → probing → broken`). The "drift detection" mechanism.
  Don't disable; only extend.

Two more honorable mentions:

- **`deliver_gates.py`** — cascading verification gates. Add new gates here
  rather than scattering checks throughout the agent loop.
- **`eddy.py` + `eddy_communication.py`** — parallel lightweight worker dispatch.
  When you need to read 10 files at once or grep across the codebase, dispatch
  eddies. They share findings via `eddy_communication.py` so you don't duplicate
  work. Think of them as boids racing for the fastest path; the first to
  arrive wins, the rest die.

## What was deleted on 2026-04-26 (don't try to use these)

The local-LLM-serving infrastructure. If you find references in old docs or
commits, they're historical. Specifically gone:

- `serving/` (entire directory — Qwen3.6 / ERNIE serving, NVFP4 quant, MTP, decode)
- `serve_transformers.py` (transformers serving)
- `gemma_args.py`, `chat_template_safety.py` (Gemma-specific tool-call parsing)
- `adapter_router.py`, `adapter_swap.py` (LoRA hot-swapping)
- `wilson_loop.py` (embedding server probe)
- `model_fallback.py` (local-server failover)
- `training/` (LLM fine-tuning data prep)
- `gguf_ops/` (GGUF dequantization / loading)
- `tools/ernie_eval.py`, `harness/server_monitor.py`
- 9 stale tests of the above
- `~/.tsunami/server_monitor.{jsonl,md}` and `~/.tsunami/opportunistic_runs/`

What still references the deleted modules (waiting on the orchestrator-swap
refactor): `agent.py` (3 lazy imports inside function bodies), `observer.py`
(Gemma role-marker logic). These are dead-code-paths-in-waiting; don't try to
hit them, and feel free to strip them when you're refactoring.

## Files NOT to touch unless you know what you're doing

- **`outbound_exfil.py`** — security gate that BLOCKS literal API keys / private
  keys / exfil-shaped URLs from being written to disk. The name reads as
  "outbound exfiltration" — it's the OPPOSITE: the defense AGAINST exfil. This
  module has its own production-firing-audit history (12+ commits of `return None`
  stub before a real ruleset landed). Do not stub or weaken without a strong reason.
- **`circulation.py`**, **`undertow.py`**, **`vision_gate.py`** — see above.
- **`../scaffolds/`** entirely — the catalog is the product. Modifying a scaffold
  changes every future build that uses it. If you need a new scaffold, propose
  it in `../scaffolds/GAPS.md` first.
- **`../scaffolds/.claude/nudges/`** — the retro-game scrape catalog. Castlevania,
  Dragon Quest, Castlevania II nudges live here. Don't lose these.
- **`../../sdf_modeling_research/`** — the active SDF/sculpt research project. Has
  its own gap.md / attempts/ structure (sigma method standard). Off-limits.
- **`../scaffolds/engine/demos/skeleton_demo.{html,ts}`** and
  **`modeler_demo.*` / `sdf_modeler.*`** — the latest skeleton+modeler demo work.
  Off-limits.
- **`../deliverables/`** — past tsunami builds (chiptune-maker, crypto-tracker,
  hn-trend-dashboard, pomodoro-pro, pomodoro-timer). Reference material.

## Major refactor in flight — don't be surprised if you find half-state

The Claude-as-orchestrator pivot is in progress. Expected residual state:

- `agent.py`, `model.py`, `config.py` still reference the old localhost:8090
  endpoint and the deleted `serve_transformers` module. They will not import
  cleanly until the swap lands.
- `observer.py` still has Gemma role-marker logic that needs to come out.
- The `model_backend` config field exists but is ignored — the abstraction is
  a lie until the refactor lands.
- The public-facing `../README.md` still claims "no OpenAI. no Anthropic. no
  API keys." — this was true in the local-LLM era, no longer accurate. Update
  separately when the orchestrator-swap PR is ready.

If you are doing the orchestrator swap: start with `model.py` (smallest unit),
then `agent.py`'s `model.generate()` callers, then `config.py`'s endpoint
defaults, then `vision_gate.py`'s VLM call. Tests will be the canary.

## Where to dig deeper

- `../scaffolds/GAPS.md` — current scaffold-rollout status (10 closed, 3 open),
  per-scaffold work shape, contention rules
- `../scaffolds/<name>/GAP.md` (open scaffolds only) — what's left for that scaffold
- `../scaffolds/<name>/__fixtures__/drone_natural.tsx` — the locked prop vocab
  for that scaffold (the API surface you must use)
- `../scaffolds/<name>/__fixtures__/<scaffold>_patterns.tsx` — domain-pattern
  fixtures (e.g. `landing_dashboard_gallery.tsx` for layouts)
- `plan_scaffolds/<name>.md` — domain conventions + gotchas
- `style_scaffolds/<name>.md` — visual style templates
- `undertow_scaffolds/<name>.md` — QA approach matched to style
- `genre_scaffolds/<name>.md` — game-genre templates
- `cli.py` — agent entry point
- `agent.py` — the standing-wave loop (in transitional state — see refactor note)
- `core/dispatch.py` — multi-modal task dispatch (gamedev, mobile, training,
  infra, openapi, etc.)

## The cold-instance test (you, right now)

If you can answer these three questions after reading this file, the doc worked:

1. **The user said "build me a dashboard with a sidebar and three Recharts graphs."**
   Which scaffold do you clone? Which plan_scaffold do you read first? Which
   undertow_scaffold gates your QA?
2. **Your first build attempt fails the vision_gate** ("the sidebar is on the right,
   should be on the left"). Which file do you read to figure out how to pull a
   Playwright lever to confirm the screenshot, and which file decides whether
   to retry or break?
3. **You notice a file that imports `from .serve_transformers import ChatRequest`.**
   Is this dead code? What's the right action — delete the import, refactor, or
   leave it?

If you can't answer all three, file an issue against this CLAUDE.md before
proceeding. The cold-start scaffold is the codebase, and a cold instance who
can't orient is the failure mode the whole thing is designed against.

### Answers (in case you got stuck)

1. **Dashboard with sidebar + 3 Recharts graphs.**
   - Scaffold: `../scaffolds/dashboard/`
   - Plan first: `plan_scaffolds/dashboard.md` (recharts API hints)
   - Locked component vocab: `../scaffolds/dashboard/__fixtures__/drone_natural.tsx`
     (gives you the full vocabulary — `Card`, `GlowCard`, `Heading`, `Flex`,
     `Box`, `Avatar`, `Badge`, `Dialog`, `Dropdown`, `NotificationCenter`,
     `Progress`, `ScrollReveal`, `Skeleton`, `Switch`, etc. — that you must
     use rather than inventing your own)
   - Style: default react-app dark theme unless user overrides
   - Undertow gate: `vision_gate.py` first; if recharts-specific failure, see
     `undertow_scaffolds/<style>.md` for the QA approach matched to the chosen
     visual style

2. **vision_gate fails on "sidebar is on the right, should be on the left".**
   - Read `undertow.py` to find the `screenshot` lever (returns base64 PNG
     you can re-inspect)
   - Read `circulation.py` to know your retry budget — if you've burned 3+
     vision-gate fails on the same intent without progress, circulation
     trips to `eddying`, compresses your context, warns you, and gives you
     one recovery attempt before going terminal
   - Practical fix path: re-read `target_layout.py` for ratio-based
     positioning, regenerate the JSX with the corrected sidebar position
     (the layout system is ratio-anchored — don't hard-code px), retry

3. **`from .serve_transformers import ChatRequest` in some file.**
   - Dead code (deleted 2026-04-26). Action depends on file:
     - **Lazy import inside an `agent.py` function body**: leave it for the
       Claude-orchestrator-swap PR (don't touch agent.py until that lands)
     - **Top-of-file import in any other module**: strip the import + the
       now-dead code path it feeds. If the whole file is *purely* about the
       dead module, delete the file
     - **Test file**: delete the test (the module under test is gone)

## Iteration log

This doc evolves. Each refresh adds a row.

| Date | Iteration | What changed |
|---|---|---|
| 2026-04-26 | v1 | Initial cold-start scaffold. 21 scaffolds catalogued. Adventure-table for web/games/CLI. Three load-bearing primitives named. Deleted-module list. Refactor-in-flight note. |
| 2026-04-26 | v2 | TL;DR added. Work-type plans (refactor/replicator/research) called out as orthogonal to scaffold choice. Lighter-scaffolds note (cli/game/gamedev/infra/mobile/training/web — no README, read dir directly). Concrete answers added for the cold-instance self-check. |
