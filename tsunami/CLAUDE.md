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
| "CLI: config generator" | `cli/config-generator/` | (light) | `core/cli_probe.py` |
| "CLI: data processor", "stream-processing CLI", "jq-/mlr-/csvkit-like" | `cli/data-processor/` | (light) | `core/cli_probe.py` |
| "CLI: file converter", "format converter" | `cli/file-converter/` | (light) | `core/cli_probe.py` |
| "mobile chat app", "messaging app" | `mobile/chat/` | (light) | `core/mobile_probe.py` |
| "mobile notes app" | `mobile/notes/` | (light) | `core/mobile_probe.py` |
| "blog", "post list + detail + tags" | `web/blog/` | (light) | `core/docs_probe.py` |
| "docs / static documentation site" | `web/docs-site/` | (light) | `core/docs_probe.py` |
| "ecommerce", "online store" | `web/ecommerce/` | (light) | `core/docs_probe.py` |
| "docker-compose", "container infra" | `infra/docker-compose/` | (light) | `core/infra_probe.py` |
| "data pipeline" | (custom) | (custom) | `core/data_pipeline_probe.py` |
| "WebSocket / SSE backend" | (custom) | (custom) | `core/ws_probe.py` / `core/sse_probe.py` |
| "finetune recipe", "training run" (rare — image/text gen deferred per "Generations TBD") | `training/finetune-recipe/` | (light) | `core/training_probe.py` |

**Important: lighter scaffolds are CATEGORIES, not single templates.**
The 10 specific sub-scaffold paths above are the actual buildable
templates. Each has its own `README.md` with a Pitch + Quick Start.
Read it. CLAUDE.md prior to v3.25 treated `cli/`, `mobile/`, `web/`,
`infra/`, `training/` as single templates and missed the 10 concrete
sub-scaffolds inside.

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

**Cross-genre scaffolds (don't fall back to `gamedev/custom/` if one of these matches):** `gamedev/cross/` is itself a category with 9 specific cross-genre sub-scaffolds, each with its own README + package.json:

| User says... | sub-scaffold |
|---|---|
| "ATB action RPG", "Final Fantasy ATB-style", "Chrono Trigger combat" | `gamedev/cross/action_rpg_atb/` |
| "bullet hell RPG", "shoot-em-up RPG hybrid" | `gamedev/cross/bullet_hell_rpg/` |
| "magic hoops", "magical sport / hoops" | `gamedev/cross/magic_hoops/` |
| "metroidvania", "metroid runs", "backtracking exploration platformer" | `gamedev/cross/metroid_runs/` |
| "ninja garden", "fast-action ninja platformer" | `gamedev/cross/ninja_garden/` |
| "platform fighter", "Smash Bros-like" | `gamedev/cross/platform_fighter/` |
| "puzzle platformer roguelite" | `gamedev/cross/puzzle_platformer_roguelite/` |
| "rhythm fighter", "music-driven combat" | `gamedev/cross/rhythm_fighter/` |
| "tactics action adventure", "Final Fantasy Tactics + Zelda hybrid" | `gamedev/cross/tactics_action_adventure/` |

For metroidvania specifically: prefer `gamedev/cross/metroid_runs/` (concrete scaffold) over `gamedev/custom/` + `genre_scaffolds/metroidvania.md` (which is the plan template fallback). Both work — metroid_runs gives you a head-start.

**Important:** The actual `gamedev/` subdirs are exactly: `action_adventure,
beat_em_up, cross, custom, fighting, fps, jrpg, platformer, racing, stealth`.
**If the user asks for a genre that isn't one of those (metroidvania, jrpg-atb,
rhythm-fighter, etc.), use `gamedev/custom/` as the scaffold base and apply
the matching `genre_scaffolds/<name>.md` for genre-specific conventions** — do
NOT try to find a `gamedev/metroidvania/` or similar; it doesn't exist.

For any game with retro-game pattern matching (sprite styling, enemy behaviors,
level structure), check `../scaffolds/nudges/<year>_<game>/` for the
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
chosen from `style_scaffolds/` (10 styles). Most styles have a same-name
`undertow_scaffolds/` file with the QA approach for that aesthetic — but the
pairing is NOT strict 1:1; see "Cross-cutting undertows" below for the
domain-categorical undertows that apply across multiple styles.

| Style | When to use | matching undertow_scaffold |
|---|---|---|
| `atelier_warm.md` | Warm, hand-crafted, Etsy/maker brands | `undertow_scaffolds/atelier_warm.md` |
| `brutalist_web.md` | Raw, structural, exposed-grid type-driven | `undertow_scaffolds/brutalist_web.md` |
| `cinematic_display.md` | Dark, immersive, hero-image dominant | `undertow_scaffolds/cinematic_display.md` |
| `editorial_dark.md` | NYT/long-read, serif-led, dark mode | `undertow_scaffolds/editorial_dark.md` |
| `magazine_editorial.md` | Magazine spread, mixed columns + pull quotes | `undertow_scaffolds/magazine_editorial.md` |
| `newsroom_editorial.md` | News site, dense above-the-fold | `undertow_scaffolds/newsroom_editorial.md` |
| `photo_studio.md` | Portfolio, image-first, minimal chrome | `undertow_scaffolds/photo_studio.md` |
| `playful_chromatic.md` | Bright, animated, motion-rich | `undertow_scaffolds/playful_chromatic.md` |
| `shadcn_startup.md` | Modern SaaS startup look (shadcn/ui aesthetic) | (no same-name undertow — use `web_polish.md` or `vision_analysis.md`) |
| `swiss_modern.md` | Helvetica-grid, restrained palette, classic Swiss | (no same-name undertow — use `web_polish.md` or `vision_analysis.md`) |

### Cross-cutting undertow_scaffolds (apply across multiple styles)

These 7 undertows are NOT tied to a specific style — they're QA categories you
combine with whatever style you picked:

| Undertow | When to apply |
|---|---|
| `web_polish.md` | General web-build polish pass (use for any web scaffold) |
| `vision_analysis.md` | Vision-VLM critique of the rendered page (currently dormant — see CHANGELOG.md v3.6) |
| `bug_finding.md` | Targeted bug-hunt undertow (functional regressions, not visual) |
| `brand_consistency.md` | Verify brand colors / typography / voice consistency across pages |
| `art_direction.md` | Higher-level art-direction QA (use with image-heavy scaffolds — landing, cinematic_display) |
| `game_feel.md` | Game-specific QA (use with `gamedev/*` scaffolds — input responsiveness, hit feedback) |
| `sprite_quality.md` | Pixel-art / sprite-asset QA (use with `gamedev/*` scaffolds + retro-game builds) |

Default for React-app-family scaffolds: `react-app`'s baked-in atmospheric dark
theme (Plus Jakarta Sans, deep palette). Only override when the user asks.

## The build pattern (what you do)

This describes you (the agent harness) doing the work — not a tsunami binary
calling functions:

1. **Read the user request** → pick scaffold + plan_scaffold + style_scaffold
   (the choose-your-own-adventure above)
2. **Read the scaffold's locked-contract files.** Three patterns based on
   scaffold shape (don't assume drone_natural.tsx exists for every scaffold —
   only 7 of 20 do):
   - **Self-contained React** (react-app, landing, dashboard, data-viz,
     form-app, fullstack, realtime): read `README.md` + `__fixtures__/drone_natural.tsx`
     (locked component prop vocab) + the matching `__fixtures__/<scaffold>_patterns.tsx`
     (domain patterns).
   - **Inheriting React** (auth-app, ai-app): read `__fixtures__/auth_flow.tsx`
     (auth-app — locks the `useAuth` contract) or `__fixtures__/chat_stream.tsx`
     (ai-app — locks the `useChat` + `parseSSE` contract). UI components
     are inherited from react-app — see `scaffold.yaml` `inherits_from: react-app`.
   - **Bespoke-gate** (api-only, chrome-extension, electron-app), **engine**,
     **game**, **gamedev**: no `__fixtures__/` dir. Read `README.md` (these
     all have one) + `package.json` + `src/` directly. Chrome-extension
     also has `manifest.json`. Gamedev edits `data/*.json` + `src/scenes/`.
   - **Lighter** (cli, mobile, infra, training, web): the top-level dir
     is a CATEGORY (no README), but it contains 10 sub-scaffolds with
     their own READMEs (`cli/data-processor/README.md`, `web/blog/README.md`,
     etc. — see the "Other" table for the full enumeration). Read the
     specific sub-scaffold's README.
3. **Read** `plan_scaffolds/<scaffold>.md` (conventions + gotchas specific to
   that build target)
4. **Build** by writing files in a working dir, using your own tools (Bash for
   `npm install`, Write/Edit for source, etc.). Use the helpers in `tools/`
   when relevant (image processing, project init).
5. **Verify** with the cascading-gates pattern. `deliver_gates.py`
   actually wires only 2 gates today (`code_write_gate`,
   `asset_existence_gate`); the rest of the verification cascade
   lives in adjacent modules or is run directly by the agent. The
   full conceptual cascade (run them in this order):
   - `code_write_gate` (in `deliver_gates.py`) — did you write the
     entry point?
   - `asset_existence_gate` (in `deliver_gates.py`) — do all `<img>`
     tags reference real files in `public/`?
   - `prop_type` — does `tsc --noEmit` pass? Run via your own `Bash`
     tool; not currently a deliver_gates function.
   - `runtime_smoke` — does `page.goto()` not throw? Run via your
     own `Bash` + Playwright; not currently a deliver_gates function.
   - `vision_gate` — does the screenshot match the intent? Lives in
     the separate `vision_gate.py` module (NOT in `deliver_gates.py`).
     Currently dormant pending Claude-vision re-wire — see below.
   - `accessibility_gate` — axe-core. Future, not implemented.
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
- **`undertow.py`** — the Playwright lever-pulling pattern. Async wrappers
  for 9 lever kinds: `screenshot`, `press`, `click`, `type`, `read_text`,
  `motion` (animation/transitions), `sequence` (run sub-levers in order),
  `autopilot` (automated exploration), `ghost_classes` (find unused CSS).
  Plus 2 static variants for non-Playwright runs (`ghost_classes_static`,
  `unused_dep_static`). Console errors are read as a side-channel (passed
  through to lever functions via `console_msgs`), NOT as a separate lever.
  Each lever returns a `LeverResult`; `pull_levers()` aggregates them into
  a `QAReport`. The "wander off path then turn around if too crazy"
  pattern lives here. Lever names = stable API; if you re-implement, keep
  the names.
- **`circulation.py`** — the drift-detection state-machine pattern
  (`flowing → eddying → probing → broken`). Counts repeated failures, triggers
  cool-downs, gives one recovery shot, breaks cleanly rather than runaway.

Honorable mention:

- **`deliver_gates.py`** — the cascading verification gates pattern. Add new
  gates here rather than scattering checks throughout the build flow.
- **`routing.py`** — pure-Python keyword routing utility (match_first /
  match_keyword). Used by the scaffold pick functions; preserved as a
  general-purpose utility. No orchestration deps.

**Reference-image bbox extraction is currently dormant.** The two pieces
of that pipeline (`target_layout.py` for ERNIE-generated reference layouts,
`tools/riptide.py` for Qwen-VL bbox extraction) both depended on the
deleted local image-gen + VLM endpoints. `target_layout.py` was nuked in
iteration 15; `tools/riptide.py` was short-circuited in iteration 14 and
returns a deferred-error with a Claude-vision re-enable hint. When
image-gen returns ("Generations TBD"), wire `tools/riptide.py` to a
Claude vision API call to re-enable the visual-clone skill.

## What's actually here (current surface, after the 2026-04-26 purge)

The repo went from 200+ python files to ~56. The trimmed surface:

- **`CLAUDE.md`** — this file (the cold-start scaffold)
- **Top-level patterns (.py, 7 files)** — `vision_gate`, `undertow`,
  `circulation`, `deliver_gates`, `outbound_exfil`, `routing`, `__init__`
- **`tools/` (7 files)** — image processing + scaffold init utilities
  (`emit_design`, `pixel_extract`, `image_ops`, `riptide`, `project_init`,
  `project_init_gamedev`, `__init__`)
- **`core/` (17 files = 13 bespoke probes + dispatch.py + _probe_common.py + __init__.py + the gamedev_scaffold_probe)** — verification probes (one per non-vision scaffold: api-only, electron, chrome-extension, mobile, cli, gamedev, data-pipeline, docs, ws, sse, training, infra, server) plus the dispatch + shared-helper modules
- **`animation/`, `game_content/`** — game-rendering primitives
- **`vendor/BPAD/`** — image processing (edges, resize, pattern noise, denoise)
- **`scripts/regen_scaffold_yaml.py`** — scaffold maintenance utility
- **`plan_scaffolds/` (16 files)** — per-scaffold + work-type plan templates
- **`style_scaffolds/` (10 files)** — visual style templates
- **`undertow_scaffolds/` (17 files)** — QA approach templates: 10 same-name pairs with style_scaffolds + 7 cross-cutting (web_polish, vision_analysis, bug_finding, brand_consistency, art_direction, game_feel, sprite_quality)
- **`genre_scaffolds/` (17 files)** — game-genre templates
- **`skills/` (7 skills)** — canonical named workflows for common build situations.
  Each is a directory with a `SKILL.md`. Use them when their trigger fits —
  they encode hard-won patterns for the specific situation:
  - `build-react/` — single-page React app build (the most-common path)
  - `build-multi-page/` — multi-page web app build
  - `build-recovery/` — recovering a broken / stuck build
  - `in-place-cwd/` — operating in the user's existing project dir vs. creating new
  - `iteration/` — iterating on an existing build (additive changes)
  - `qa-loop/` — QA-focused iteration when the build compiles but the QA fails
  - `visual-clone/` — replicating a reference image. **Currently
    degraded** — the bbox-extraction half of this pipeline
    (`tools/riptide.py`) is dormant until image-gen returns. Skill
    still works for sprite/asset extraction via `tools/pixel_extract.py`.

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

- **`outbound_exfil.py`** — security gate that BLOCKS suspicious content from
  being written to disk. The name reads as "outbound exfiltration" — it's the
  OPPOSITE: the defense AGAINST exfil. Four detector categories:
  (1) literal credentials (Anthropic / OpenAI / GitHub / Slack / Google API
  keys, JWT-shaped tokens); (2) PEM private keys; (3) env-var-value leaks
  (when an env var's literal value ≥12 chars appears in written content);
  (4) URLs to known webhook-capture services (webhook.site, requestbin,
  etc. — narrow "high-confidence" list, NOT all webhooks; legitimate hosts
  like hooks.slack.com, discord.com, pipedream.net are NOT blocked because
  they have legitimate uses). Entry point: `check_outbound_exfil(content,
  filename, task_prompt) → Optional[str]`. Returns block-reason string on
  hit, None on pass. This module has its own production-firing-audit history
  (12+ commits of `return None` stub before a real ruleset landed). Do not
  stub or weaken without a strong reason.
- **`circulation.py`**, **`undertow.py`**, **`vision_gate.py`** — the load-bearing
  patterns. Read and follow; don't gut.
- **`../scaffolds/`** entirely — the catalog is the product. Modifying a scaffold
  changes every future build that uses it. If you need a new scaffold, propose
  it in `../scaffolds/GAPS.md` first.
- **`../scaffolds/nudges/`** — the retro-game scrape catalog (69 game
  dirs / ~2K nudge JSON files). Castlevania, Dragon Quest, Mario, Metroid,
  Contra, Zelda, Final Fantasy, etc. Don't lose these. Lives at
  `scaffolds/nudges/` (NOT inside `scaffolds/.claude/nudges/` where it
  used to be) so the `.claude/` gitignore rule doesn't strip it from
  fresh clones — moved 2026-04-26.
- **`../../sdf_modeling_research/`** — the active SDF/sculpt research project. Has
  its own gap.md / attempts/ structure (sigma method standard). Off-limits.
- **`../scaffolds/engine/demos/skeleton_demo.{html,ts}`** and
  **`modeler_demo.*` / `sdf_modeler.*`** — the latest skeleton+modeler demo work.
  Off-limits.
- **`../deliverables/`** — past tsunami builds (chiptune-maker, crypto-tracker,
  hn-trend-dashboard, pomodoro-pro, pomodoro-timer). Reference material.
- **`animation/`, `game_content/`, `vendor/BPAD/`** — game-rendering and
  image-processing primitives. Use as-is.

## Adding new probes / styles / skills (META work)

If the user asks you to EXTEND tsunami itself (not USE it to build),
the conventions are:

### Add a new probe (verifies a non-vision-gated scaffold)

1. Copy the closest existing probe (e.g. `core/mobile_probe.py` for an
   iOS variant, `core/openapi_probe.py` for an API variant). Rename and
   adapt the docstring + entrypoint signature.
2. **Register it** in `core/dispatch.py` — the `_PROBES = {...}` dict
   on line ~49. The lookup at the bottom of dispatch.py errors with
   "Add one or rename the scaffold" if the dispatch can't find a
   matching probe — that's your signal you forgot this step.
3. Add a row to the **No-vision-gate adventures** table in this
   CLAUDE.md (under Choose-your-own-adventure section).
4. (Optional) Add a `scaffolds/<scaffold-name>/` template if the new
   probe needs a corresponding scaffold to verify.

### Add a new visual style

1. Write `style_scaffolds/<name>.md` — frontmatter must include
   `default_mode`, `applies_to`, `mood`, plus the body sections
   (Palette / Typography / Layout / etc. — see existing styles for
   the template).
2. **Optionally** write a same-name `undertow_scaffolds/<name>.md` if
   the style needs a style-specific QA approach. This is NOT
   required — most styles use one of the 7 cross-cutting undertows
   (`web_polish`, `vision_analysis`, `art_direction`, etc.). Earlier
   versions of this doc claimed strict 1:1 pairing — that was wrong;
   `shadcn_startup` and `swiss_modern` ship without a same-name
   undertow and that's fine.
3. **No manifest update needed.** `style_scaffolds/manifest.py` is
   on-demand auto-discovery — it scans `*.md` at query time, so a
   new style file is automatically visible.
4. Add a row to the **Visual style** table in this CLAUDE.md.

### Add a new skill

1. Make a directory `skills/<skill-name>/`.
2. Inside, create `SKILL.md` with REQUIRED sections:
   - `## When` — trigger conditions (when this skill applies)
   - A workflow section — usually `## Pipeline` for sequential
     skills, but `build-recovery/SKILL.md` uses
     `## Pattern → Action` (decision table) instead. The shape
     follows the skill type. Both use the legacy agent-tool API;
     see the translation table above.
   - `## Gotchas` — common pitfalls
   - Optional: `## When NOT` (when to use a different skill instead),
     `## After the fix` (post-action verification, see build-recovery),
     skill-specific deeper sections (build-react has `## Available components`)
3. Add a one-line bullet to the `skills/` catalog in the
   "What's actually here" section of this CLAUDE.md (with trigger
   hint).

### Modify CLAUDE.md itself

1. Edit the relevant section.
2. **Always bump the iteration log in [`CHANGELOG.md`](CHANGELOG.md)** —
   add a new row with today's date, next version (v3.8 → v3.9 etc.),
   and a one-line description of what changed. This preserves the
   audit trail for future cold instances. The orientation doc itself
   stays trim; the historical context lives one click away.
3. Verify all new file references resolve (the cold-test pattern in
   recent iterations: `for ref in <list>; do [ -e tsunami/$ref ] && echo ok; done`).

### Modify a scaffold

**Don't, ad-hoc.** The scaffolds catalog is the product. Modifying
`scaffolds/<name>/` changes every future build that uses it. If a
real scaffold-level change is needed:

1. Open an issue in `scaffolds/GAPS.md` first describing what's
   broken / missing.
2. The change should land as a single coherent commit with a
   "scaffold: <name>" prefix and explain the user-visible impact.
3. The 9 closed React-shape scaffolds have a locked-contract
   fixture — `__fixtures__/drone_natural.tsx` for the 7
   self-contained ones, or `__fixtures__/auth_flow.tsx` /
   `__fixtures__/chat_stream.tsx` for the 2 inheriting ones
   (auth-app, ai-app). Modifying any of these changes the API
   surface every drone build is expected to use, so it needs to be
   intentional.

## Where to dig deeper

- `../README.md` — the public-facing tsunami pitch ("tsunami is a scaffold")
- `../scaffolds/GAPS.md` — catalog status reference (20 scaffolds, all
  closed) + what shipped per scaffold + which probe verifies each
- `../scaffolds/<name>/GAP.md` (open scaffolds only) — what's left for that scaffold
- **Per-scaffold locked-contract fixture** — the API surface you must use.
  Naming varies by scaffold tier (see build-pattern step 2):
  - 7 self-contained React: `__fixtures__/drone_natural.tsx`
  - 2 inheriting React: `auth-app/__fixtures__/auth_flow.tsx` (useAuth contract)
    or `ai-app/__fixtures__/chat_stream.tsx` (useChat + parseSSE contract)
  - 11 others (bespoke-gate / engine / game / gamedev / lighter): no
    `__fixtures__/` dir; contract lives in `README.md` + `package.json` + `src/`
- **Per-scaffold domain-pattern fixture** (only the 7 self-contained have one).
  Naming is irregular — derived from the scaffold stem with hyphens dropped:
  - `react-app/__fixtures__/landing_dashboard_gallery.tsx` (special name, not `*_patterns.tsx`)
  - `landing/__fixtures__/landing_patterns.tsx`
  - `dashboard/__fixtures__/dashboard_patterns.tsx`
  - `data-viz/__fixtures__/dataviz_patterns.tsx` (hyphen dropped)
  - `form-app/__fixtures__/form_patterns.tsx` (`-app` dropped)
  - `fullstack/__fixtures__/fullstack_patterns.tsx`
  - `realtime/__fixtures__/realtime_patterns.tsx`
- `../scaffolds/<name>/scaffold.yaml` — auto-generated component prop
  contract (only present for React-shape scaffolds — the 9 vision-gated
  ones). Generated from `src/components/ui/*.tsx` via
  `python3 -m tsunami.scripts.regen_scaffold_yaml <name>`. Two of the 9
  (`auth-app`, `ai-app`) are inheritance markers — they re-export
  react-app's UI + add scaffold-specific contracts (`useAuth`,
  `useChat`); their scaffold.yaml has `inherits_from: react-app` and
  points at their `__fixtures__/drone_natural.tsx` for the addition.
  Bespoke-gate scaffolds (api-only, chrome-extension, electron-app),
  game scaffolds (game, engine, gamedev), and lighter scaffolds (cli,
  mobile, infra, training, web) don't have scaffold.yaml — different
  contract models (server probe / data-driven game schema / minimal
  UI surface).
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
   - Practical fix path: regenerate the JSX with the corrected sidebar
     position (use `flex-direction` / `grid-template-columns` rather than
     hardcoded px so the layout is responsive), retry. Note: the previous
     ratio-based positioning helper (`target_layout.py` + `tools/riptide.py`)
     is dormant until image-gen returns.

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

The full audit-trail of CLAUDE.md changes (v1 → current) lives in
[`CHANGELOG.md`](CHANGELOG.md) next to this file. Bump it on every doc
change (per the META section's "Modify CLAUDE.md" instructions).

Current: **v3.8** — see CHANGELOG.md for what landed.
