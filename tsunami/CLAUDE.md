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
(your locked component vocab), build using your own tools (Bash/Edit/Write/etc.),
verify the build by following the patterns in `vision_gate.py` + `undertow.py`,
let `circulation.py`'s drift-detection shape catch you if you spiral, ship.
Don't try to be clever — the scaffolds are already clever. **The directory
`../scaffolds/` is the product catalog and is off-limits for ad-hoc edits.**

The python files in this directory are **patterns you read**, not modules you
import. Tsunami used to be a binary that ran an agent loop calling these
modules; that loop was retired (see "What was deleted" below). Now you (the
agent harness) are the loop. The patterns describe what you do.

Your first move: read the choose-your-own-adventure table below. Match the user's
request to a row. That row tells you the next 3 files to read.

## What tsunami is, in one paragraph

Tsunami is a **scaffold library plus the patterns for executing scaffolds well**.
The hard work — picking the right project shape, the right visual style, the
right QA strategy, the right game genre — is already done and lives as a catalog
of named scaffolds in `../scaffolds/` and in the four `*_scaffolds/` directories
at this level. Your job is to **match the user's request to the right scaffolds,
read the relevant patterns, fill the scaffold in, and verify the build with
screenshots and Playwright levers.** Don't think of yourself as a sophisticated
reasoning agent. Think of yourself as a fast, accurate scaffold matcher plus a
relentless visual-grounding QA loop, both of which the scaffolds + patterns make
straightforward.

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

### No-vision-gate adventures (use the bespoke probe in `core/`)

| User says... | scaffold | plan | gate (in `core/`) |
|---|---|---|---|
| "REST API", "no UI", "OpenAPI spec" | `api-only` | `plan_scaffolds/api-only.md` | `core/openapi_probe.py` (handler-vs-spec) |
| "Chrome extension", "browser plugin" | `chrome-extension` | `plan_scaffolds/chrome-extension.md` | `core/extension_probe.py` (load-unpacked) |
| "Electron desktop app" | `electron-app` | `plan_scaffolds/electron-app.md` | `core/electron_probe.py` (build + artifact check) |
| "CLI tool" | `cli` | (light) | `core/cli_probe.py` |
| "mobile app" | `mobile` | (light) | `core/mobile_probe.py` |
| "infrastructure / deploy" | `infra` | (light) | `core/infra_probe.py` |
| "data pipeline" | (custom) | (custom) | `core/data_pipeline_probe.py` |
| "docs / static site" | (custom) | (custom) | `core/docs_probe.py` |
| "WebSocket / SSE backend" | (custom) | (custom) | `core/ws_probe.py` / `core/sse_probe.py` |
| "training run" | `training` | (light, deferred) | `core/training_probe.py` |

### Games

For ALL games: read `plan_scaffolds/gamedev.md` first (applies to every genre — covers the data-driven scaffold flow + `data/*.json` editing + `vite build` emit pattern). Then read the matching `genre_scaffolds/<name>.md` for genre-specific mechanics.

| User says... | scaffold | genre template | engine |
|---|---|---|---|
| "platformer", "Mario-like", "side-scrolling action" | `gamedev/platformer/` | `genre_scaffolds/platformer.md` | `../scaffolds/engine/` (WebGPU) |
| "fighter", "Street Fighter-like", "1v1 combat" | `gamedev/fighting/` | `genre_scaffolds/fighter.md` | engine |
| "JRPG", "Final Fantasy-like", "turn-based" | `gamedev/jrpg/` | `genre_scaffolds/jrpg.md` | engine |
| "FPS", "Doom-like", "first person shooter" | `gamedev/fps/` | `genre_scaffolds/fps.md` | engine |
| "beat-em-up", "Streets of Rage" | `gamedev/beat_em_up/` | `genre_scaffolds/beat_em_up.md` | engine |
| "racing", "kart racer", "Mario Kart-like" | `gamedev/racing/` | `genre_scaffolds/kart_racer.md` | engine |
| "stealth", "Metal Gear-like" | `gamedev/stealth/` | `genre_scaffolds/stealth.md` | engine |
| "action adventure", "Zelda-like" | `gamedev/action_adventure/` | `genre_scaffolds/action_adventure.md` | engine |
| something more exotic | `gamedev/custom/` | check `genre_scaffolds/` for: action_rpg_atb, immersive_sim, magic_hoops, metroidvania, metroid_runs, ninja_garden, open_world, rhythm_fighter, rts | engine |

**Important:** The actual `gamedev/` subdirs are exactly: `action_adventure,
beat_em_up, cross, custom, fighting, fps, jrpg, platformer, racing, stealth`.
**If the user asks for a genre that isn't one of those (metroidvania, jrpg-atb,
rhythm-fighter, etc.), use `gamedev/custom/` as the scaffold base and apply
the matching `genre_scaffolds/<name>.md` for genre-specific conventions** — do
NOT try to find a `gamedev/metroidvania/` or similar; it doesn't exist.

For any game with retro-game pattern matching (sprite styling, enemy behaviors,
level structure), check `../scaffolds/.claude/nudges/<year>_<game>/` for the
existing scrape catalog (Castlevania I & II, Dragon Quest, etc.).

**Game-flow vs web-flow distinction:** Games use `genre_scaffolds/<name>.md` +
`core/gamedev_scaffold_probe.py` (the canonical new-flow probe; the older
`core/gamedev_probe.py` is the legacy `public/game_definition.json` flow —
prefer `gamedev_scaffold_probe`). Games do NOT use `style_scaffolds/` or
`undertow_scaffolds/` — those are web-only. Game QA is genre-driven, not
visual-style-driven.

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

Default for React-app-family scaffolds: `react-app`'s baked-in atmospheric dark
theme (Plus Jakarta Sans, deep palette). Only override when the user asks.

## The build pattern (what you do)

This describes you (the agent harness) doing the work — not a tsunami binary
calling functions:

1. **Read the user request** → pick scaffold + plan_scaffold + style_scaffold
   (the choose-your-own-adventure above)
2. **Read** `../scaffolds/<scaffold>/README.md` and
   `../scaffolds/<scaffold>/__fixtures__/drone_natural.tsx` (the locked prop
   vocab — fixtures exist so you don't drift the API surface)
3. **Read** `plan_scaffolds/<scaffold>.md` (conventions + gotchas specific to
   that build target)
4. **Build** by writing files in a working dir, using your own tools (Bash for
   `npm install`, Write/Edit for source, etc.). Use the helpers in `tools/`
   when relevant (image processing, project init).
5. **Verify** by following the gates pattern in `deliver_gates.py`:
   - Did you write the entry point? (code_write)
   - Do all `<img>` tags reference real files? (asset_existence)
   - Does `tsc --noEmit` pass? (prop_type)
   - Does `page.goto()` not throw? (runtime_smoke — Bash + Playwright)
   - Does the screenshot match the intent? (vision_gate — see pattern below)
6. **If a gate fails**, follow the lever pattern in `undertow.py`: take a
   screenshot, read console errors, click the broken affordance, get back
   concrete failures. Fix and loop.
7. **If you spiral** (3+ identical failures, infinite read-loop, context
   overflow), follow the drift-detection pattern in `circulation.py`:
   acknowledge the loop, compress, try one different approach, then break
   cleanly. Don't grind.

## Three load-bearing patterns — read these before you touch anything visual

If your work touches build verification, visual matching, or QA in any way,
read these three files first. They are patterns to follow, not modules to
import.

- **`vision_gate.py`** — the visual verification pattern: take a screenshot
  of the built page, send it to the vision-capable LLM (you, in this
  conversation, with image content), ask "list visual issues", iterate.
- **`undertow.py`** — the Playwright lever-pulling pattern. Async wrapper
  that takes screenshots, presses keys, clicks elements, reads the console,
  and returns a structured `QAReport`. The "wander off path then turn around
  if too crazy" pattern. Lever names = stable API; if you re-implement, keep
  the names.
- **`circulation.py`** — the drift-detection state-machine pattern
  (`flowing → eddying → probing → broken`). Counts repeated failures, triggers
  cool-downs, gives one recovery shot, breaks cleanly rather than runaway.

Honorable mention:

- **`deliver_gates.py`** — the cascading verification gates pattern. Add new
  gates here rather than scattering checks throughout the build flow.
- **`target_layout.py`** — extracts UI element bboxes from a reference image
  and returns ratio-based CSS. Useful when the user provides a visual mockup.

## What's actually here (current surface, after the 2026-04-26 purge)

The repo went from 200+ python files to ~56. The trimmed surface:

- **`CLAUDE.md`** — this file (the cold-start scaffold)
- **Top-level patterns (.py, 7 files)** — `vision_gate`, `target_layout`,
  `undertow`, `circulation`, `deliver_gates`, `outbound_exfil`, `__init__`
- **`tools/` (7 files)** — image processing + scaffold init utilities
  (`emit_design`, `pixel_extract`, `image_ops`, `riptide`, `project_init`,
  `project_init_gamedev`, `__init__`)
- **`core/` (17 files)** — bespoke verification probes (one per non-vision
  scaffold: api-only, electron, chrome-extension, mobile, cli, gamedev,
  data-pipeline, docs, ws, sse, training, infra, server) plus
  `dispatch.py` and `_probe_common.py`
- **`animation/`, `game_content/`** — game-rendering primitives
- **`vendor/BPAD/`** — image processing (edges, resize, pattern noise, denoise)
- **`scripts/regen_scaffold_yaml.py`** — scaffold maintenance utility
- **`plan_scaffolds/` (16 files)** — per-scaffold + work-type plan templates
- **`style_scaffolds/` (9 files)** — visual style templates
- **`undertow_scaffolds/` (9 files)** — QA approach templates matched to styles
- **`genre_scaffolds/` (18 files)** — game-genre templates
- **`skills/` (7 skills)** — canonical named workflows for common build situations.
  Each is a directory with a `SKILL.md`. Use them when their trigger fits —
  they encode hard-won patterns for the specific situation:
  - `build-react/` — single-page React app build (the most-common path)
  - `build-multi-page/` — multi-page web app build
  - `build-recovery/` — recovering a broken / stuck build
  - `in-place-cwd/` — operating in the user's existing project dir vs. creating new
  - `iteration/` — iterating on an existing build (additive changes)
  - `qa-loop/` — QA-focused iteration when the build compiles but the QA fails
  - `visual-clone/` — replicating a reference image (use with `target_layout.py`
    + `tools/pixel_extract.py`)

**Skill files use the legacy tsunami-agent tool API** — names like
`shell_exec`, `file_write`, `file_read`, `file_edit`, `project_init`,
`generate_image`, `match_glob`, `message_result`, `message_chat`.
Those tools were deleted along with the agent loop on 2026-04-26 — when
a skill instructs you to use one, map it to your own harness's equivalent.

For Claude Code, the mapping is:

| Skills say... | Claude Code tool to use |
|---|---|
| `shell_exec` | `Bash` |
| `file_read` | `Read` |
| `file_write` | `Write` |
| `file_edit` | `Edit` (uses `old_string` + `new_string`) |
| `match_glob` | `Glob` |
| `project_init` | no direct equivalent — copy a scaffold dir via `Bash` + customize via `Edit`/`Write` |
| `generate_image` | no direct equivalent — image-gen is deferred ("Generations TBD") |
| `message_result` | just respond in your text output (no special tool call) |
| `message_chat` | **NEVER do this** — skills call this out as the anti-pattern. The `build-recovery` skill explicitly warns "NEVER fall back to message_chat saying 'I'll look into it.'" Translation: don't punt back to the user; do the work. |

The skills' workflow logic (the WHEN / WHAT / GOTCHAS sections) is current and
correct — only the tool-call syntax is from the dead-agent era.

That's the entire surface. If you find yourself looking for `agent.py`,
`cli.py`, `model.py`, `config.py`, `prompt.py`, `routing.py`, `eddy.py`,
`server.py`, `serve.py`, etc. — they were intentionally deleted. See below.

## What was deleted on 2026-04-26 (and why)

A six-commit purge retired the local-LLM-orchestrator era of tsunami. Total
removal: ~65,000 lines across ~317 files. Major waves:

1. **`0a02c80` — Local-LLM serving stack.** `serving/` (Qwen3.6 / ERNIE / embed
   serving, NVFP4 quant, MTP, decode), `serve_transformers.py`, `gemma_args.py`,
   `chat_template_safety.py`, `adapter_router.py`, `adapter_swap.py`,
   `wilson_loop.py`, `model_fallback.py`, `training/`, `gguf_ops/`,
   `tools/ernie_eval.py`, `harness/server_monitor.py`. Reason: pivot from
   self-hosted inference to Claude (your harness's API) as the orchestrator.
2. **`2ba795b` — Installers + tsu CLI + config.yaml.** `setup.sh`, `setup.ps1`,
   `tsu`, `tsu.ps1`, `config.yaml`. Reason: tsunami isn't a binary anymore;
   no installer or wrapper needed. The README was rewritten around "tsunami is
   a scaffold" in the same commit.
3. **`c94b029` — 67 orchestration python files.** The agent loop and everything
   that supported it: `agent.py` (325K!), `prompt.py`, `model.py`, `observer.py`,
   `planfile.py`, `phase_machine.py`, `task_decomposer.py`, `hooks.py`,
   `skills.py`, `session.py`, `session_memory.py`, `state.py`, `watcher.py`,
   `compression.py`, `microcompact.py`, `semantic_dedup.py`, `snip.py`,
   `token_estimation.py`, `tool_dedup.py`, `tool_timeout.py`,
   `tool_result_storage.py`, `dynamic_tool_filter.py`, `routing.py`,
   `routing_telemetry.py`, `behavior_infer.py`, `cost_tracker.py`,
   `quality_telemetry.py`, `speed_audit.py`, `notifier.py`, `feedback.py`,
   `progress.py`, `doctrine_history.py`, `pending_files.py`, `abort.py`,
   `phase_filter.py`, `worker.py`, `run.py`, `__main__.py`, `cli.py`,
   `config.py`, `loop_guard.py`, `bash_security.py`, `server.py` (FastAPI
   Mission Control), `brand_scaffold.py`, `error_fixer.py`, `engine_catalog.py`,
   `runtime_check.py`, `pre_scaffold_naming.py`, `source_analysis.py`,
   `git_detect.py`, `jsx_import_check.py`, `content_probe.py`, `auto_build.py`,
   `test_compiler.py`, `vision_preview.py`, `qa_rubrics.py`, `eddy.py`,
   `eddy_communication.py`, `serve.py`, `harness/` (entire dir),
   `tools/{base,discovery,toolbox,filesystem,generate,message,plan,search,shell,undertow}.py`.
   Reason: file system as context. Anything that was loading something or
   performing a very specific function got nuked. The agent loop is now you,
   the harness — not a python module.
4. **`ca9604d` — `tests/` + `pytest.ini` + `cufile.log`.** 149 test files,
   ~5.6 MB. ~128 tested modules already deleted; the rest can be regenerated
   from the surviving primitives. Reason: tests of dead code are dead.

If you see references to any of the above in older docs / commits / case
studies / sigma archives, they're historical. Don't try to use them.

## Files NOT to touch unless you know what you're doing

- **`outbound_exfil.py`** — security gate that BLOCKS literal API keys / private
  keys / exfil-shaped URLs from being written to disk. The name reads as
  "outbound exfiltration" — it's the OPPOSITE: the defense AGAINST exfil. This
  module has its own production-firing-audit history (12+ commits of `return None`
  stub before a real ruleset landed). Do not stub or weaken without a strong reason.
- **`circulation.py`**, **`undertow.py`**, **`vision_gate.py`** — the load-bearing
  patterns. Read and follow; don't gut.
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
- **`animation/`, `game_content/`, `vendor/BPAD/`** — game-rendering and
  image-processing primitives. Use as-is.

## Where to dig deeper

- `../README.md` — the public-facing tsunami pitch ("tsunami is a scaffold")
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
- `core/dispatch.py` — multi-modal task dispatch pattern
- `core/<name>_probe.py` — bespoke verification probe per non-vision scaffold

## The cold-instance test (you, right now)

If you can answer these three questions after reading this file, the doc worked:

1. **The user said "build me a dashboard with a sidebar and three Recharts graphs."**
   Which scaffold do you clone? Which plan_scaffold do you read first? Which
   undertow_scaffold gates your QA?
2. **Your first build attempt fails the vision_gate** ("the sidebar is on the right,
   should be on the left"). Which file do you read to figure out what Playwright
   lever to pull, and which file decides whether to retry or break?
3. **You find a python module like `agent.py` referenced in an old commit message
   or sigma case study, but it doesn't exist in the repo.** What's going on?

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
   - Read `undertow.py` to find the `screenshot` lever pattern (returns base64
     PNG you can re-inspect in your own conversation)
   - Read `circulation.py` to know your retry budget — if you've burned 3+
     vision-gate fails on the same intent without progress, the pattern is
     to compress your context, try one different approach, then break
     cleanly rather than grind
   - Practical fix path: re-read `target_layout.py` for ratio-based
     positioning, regenerate the JSX with the corrected sidebar position
     (the layout system is ratio-anchored — don't hard-code px), retry

3. **`agent.py` (or `cli.py`, `model.py`, `config.py`, `eddy.py`, `server.py`,
   etc.) referenced but missing.**
   - Historical artifact. The 2026-04-26 purge retired the entire
     local-LLM-orchestrator era — see "What was deleted" above. Tsunami isn't
     invoked anymore; nothing imports `tsunami.agent` or
     `tsunami.serve_transformers`. If a doc points you at one of these
     modules, the doc is stale. Update the doc; don't try to revive the module.
   - The patterns the deleted modules encoded survive in the surviving
     primitives (`vision_gate`, `undertow`, `circulation`, `deliver_gates`)
     and in this CLAUDE.md.

## Iteration log

This doc evolves. Each refresh adds a row.

| Date | Iteration | What changed |
|---|---|---|
| 2026-04-26 | v1 | Initial cold-start scaffold. 21 scaffolds catalogued. Adventure-table for web/games/CLI. Three load-bearing primitives named. Deleted-module list. Refactor-in-flight note. |
| 2026-04-26 | v2 | TL;DR added. Work-type plans (refactor/replicator/research) called out as orthogonal to scaffold choice. Lighter-scaffolds note. Concrete answers for the cold-instance self-check. |
| 2026-04-26 | v3 | Aligned with the post-purge reality. "Major refactor in flight" section deleted (executed, not pending). "What was deleted" expanded to the full 6-commit / ~317-file / ~65K-line story. Added "What's actually here (current surface)" enumeration. Reframed agent-loop language ("you do the work, not a tsunami binary"). Updated cold-instance Q3 (no more lazy-import-in-agent.py since agent.py is gone — the question is now about historical references in stale docs). Added `core/<name>_probe.py` table for non-vision scaffolds. Removed `eddy.py` references (deleted in c94b029). |
| 2026-04-26 | v3.1 | Cold-tested with a fresh Explore agent. Four gaps fixed: (1) added explicit "if the genre isn't in the table, fall back to `gamedev/custom/`" note (the table establishes a `gamedev/<genre>/` pattern that breaks for metroidvania / rhythm-fighter / etc.). (2) Added explicit game-flow-vs-web-flow distinction: games use `genre_scaffolds/` + `core/gamedev_scaffold_probe.py`, NOT `style_scaffolds/` + `undertow_scaffolds/`. (3) Picked `gamedev_scaffold_probe.py` as canonical (the new data-driven flow) and explained why the older `gamedev_probe.py` exists. (4) Expanded the `skills/` entry from a one-liner to a real catalog with one-line trigger hints per skill (build-react / build-multi-page / build-recovery / in-place-cwd / iteration / qa-loop / visual-clone). Cold-test independent answers matched the doc's expected answers; v3.1 closes the remaining ambiguities. |
| 2026-04-26 | v3.2 | Second cold-test passed all 4 scenarios with exact ground-truth match (metroidvania flame-knight, brutalist photographer portfolio, broken vite-build recovery, vision_gate-fail-3-strikes). One minor v3.2 gap closed: Games table now opens with a one-line note pointing at `plan_scaffolds/gamedev.md` as the universal game-build plan (applies to every genre — covers data-driven scaffold flow + `data/*.json` editing + `vite build` emit). The 4 web-app rows have explicit per-row plans; the games rows did not. Now they do. |
| 2026-04-26 | v3.3 | Audited `skills/*/SKILL.md` and found 83 references to the deleted agent-tool API (shell_exec, file_write, file_read, file_edit, project_init, generate_image, match_glob, message_chat, message_result). The skills are written for the dead tsunami-agent loop's tool registry; their workflow logic is still correct but the tool-call syntax is historical. Added a tool-API translation table to the skills section: `shell_exec` → Bash, `file_read` → Read, `file_write` → Write, `file_edit` → Edit, `match_glob` → Glob, `project_init` → no direct equivalent (copy + customize), `generate_image` → no direct equivalent (image-gen deferred), `message_result` → just respond in text, `message_chat` → NEVER (anti-pattern). Less invasive than rewriting 7 skill files; cold instance reads CLAUDE.md, sees the table, can interpret skills correctly. WAVEFORM.md mention removed from the skills bullet (no skills currently have one — the gitignore exception is precautionary). |
| 2026-04-26 | v3.4 | Iteration-14 audit caught a major mis-categorization. `mesh/` (21 files / 392 KB) was kept across iterations 1-13 as "game-rendering 3D mesh utilities" based on the directory name. Reading its README revealed it's actually **MegaLAN — a decentralized compute mesh** for distributing tsunami agent jobs across networked nodes (P2P, identity / peer / ledger / discovery layers). With tsunami not invoked anymore + no agent jobs to distribute, the entire subsystem is dead orchestration infrastructure. Nuked the dir; verified no external dependents in the surviving codebase. CLAUDE.md mentions of `mesh/` removed from "What's actually here" + "Files NOT to touch" sections. Also short-circuited `tools/riptide.py` vision grounding (same pattern as `seed_from_image.py` in iteration 13 — was iterating through 3 dead localhost endpoints, now returns a deferred-error immediately with a re-enable hint pointing at Claude vision API). All 13 `core/<name>_probe.py` files audited and verified clean (zero broken imports, zero dead-endpoint refs, all import-test successfully). |
