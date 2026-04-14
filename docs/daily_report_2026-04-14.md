<p align="center">
  <img src="banner.png" alt="tsunami" width="800">
</p>

# Tsunami Daily Report — 2026-04-14

Reporting window: 2026-04-13 17:00 CDT → 2026-04-14 06:30 CDT (~13 hours, one consolidation session).

## Commits pushed (last 24h)

25 commits. Grouped by theme:

**Scaffold + primitives (6)**
- `3cf84ac` Box/Flex/Heading/Text primitives
- `fb9b0c7` Image primitive
- `ce99915` compound Card (CardHeader/Content/Footer/Title/Description) + auto-deliver
- `92e5cbc` `@/` path alias wired into tsconfig + vite.config
- `3bdf891` `project_init` surfaces actual component exports
- `0fefa5c` skills/build-multi-page/ added + loader cap 16k→32k

**Observable QA + undertow (5)**
- `07aeb8c` undertow hardening overhaul (live-DOM click, type lever, wait, port-flex, traceback)
- `20a6fad` undertow: click only first clickable (not all 3)
- `f75464f` icon mode: fringe kill + erosion (superseded)
- `953d16f` icon mode: binary magenta-family key (superseded prior)
- `d9820a1` file_write parse-validates .json/.yaml/.toml/.xml/.svg

**Tension system excised (1)**
- `8e42225` removed current/circulation/pressure/adversarial (~400 lines + tests)

**Agent plumbing (5)**
- `88e9c8a` auto-install missing npm deps at file_write time
- `aefdd81` .env var awareness at delivery
- `98314eb` tool-role guards: file_edit path inference + message_chat-as-code reroute
- `1bffe3a` design constraints + anti-over-engineering + context hygiene
- `d27e02d` surgical-edit vs rewrite thresholds in skills + escalation nudges

**Image gen (2)**
- `07aeb8c` Z-Image HTTP backend in generate_image, alpha/icon modes, public/assets routing
- `52ad20c` sprite_pipeline: Z-Image via tsunami server only (dropped SD-Turbo)

**Server (1)**
- `4008a06` serve: AutoPipelineForText2Image (unblocks Z-Image-Turbo load)

**CLI + README + infra (5)**
- `0f8e71c` CLI: auto-detect in-place CWD mode + `--in-place` flag
- `5cabb03` setup.ps1: auto-install git via winget
- `bc9e439` + `5e4af4b` + `fca2467` + `c71a622` + `ae7756a` + `b9f6e8b` README passes
- `e82512c` removed GitHub workflows
- `e4dc276` banner installed to docs/

**Meta (1)**
- `8466c77` eval 2026-04-13 resistor map

## Eval scoreboard

9-prompt tiered run (T1 single-page / T2 multi-view / T3 auth). **3/9 counted, 2/9 actual** (crypto was a REFUSED ship the harness miscounted).

| tier | prompt | iters | time | result |
|---|---|---|---|---|
| T1 | crypto | 5 | 260s | ✗ (shipped undefined `<Alert>` — harness didn't catch the REFUSED) |
| T1 | lunchvote | 9 | 600s | ✗ (undertow 3-click; fixed after run) |
| T1 | pomodoro | 3 | 600s | ✗ (message_chat-as-code; fixed after run) |
| T1 | chiptune | 7 | 900s | ✗ (same; fixed after run) |
| T2 | watchlist | 9 | 555s | ✓ (auto-deliver saved it) |
| T2 | leads | 16 | 900s | ✗ (file_edit without path; fixed after run) |
| T2 | writer | 8 | 900s | ✗ (same; fixed after run) |
| T3 | event | 5 | 576s | ✓ (RSVP platform, clean) |
| T3 | course | 19 | 1200s | ✗ (20-iter cap during multi-file auth build) |

**Projected on rerun** against current main: 7-8/9. Five of seven failures have fixes already merged.

## Known failures + resistor category

| Failure | Category | Fix status |
|---|---|---|
| Undefined JSX component imports slip past gates | **Unobserved resistor** — need pre-deliver JSX-name validator | **OPEN** |
| Undertow sequential-click DOM mutation | Observable, fixed | ✓ `20a6fad` |
| Model emits code as message_chat.text | Tool-shape confusion, fixed | ✓ `98314eb` |
| file_edit emitted without path arg | Tool-shape confusion, fixed | ✓ `98314eb` (extended to old_text/new_text shapes) |
| Multi-file auth build hits iter cap | **Budget + skill routing** — either raise cap or force build-multi-page phased dispatch | **OPEN** |

## What's running

Just the Tsunami server (`serve_transformers.py --model google/gemma-4-e4b-it --port 8090 --image-model Tongyi-MAI/Z-Image-Turbo`), pid 1014580, ~13h uptime. No eval, no test, no background jobs.

## What's parked

- **Multi-model sweep** (2B / 4B / a4b / 31B) — harness is already model-pluggable; run after Phase 1 stabilizes
- **Phase 1.5 engine-dogfood suite** — react-engine-app scaffold + particle editor / texture editor / model viewer / chiptune maker / physics playground / etc. Each app exercises one engine module and doubles as its canonical demo
- **Audio generation** — mirror generate_image architecture (`generate_audio` with mode="music"/"sfx"/"ambient"); Tone.js / native Web Audio for procedural
- **Parallel undertow** — fire-and-forget QA task with system_note return channel. For games specifically (3-5s+ browser checks would otherwise block the builder)
- **bitsandbytes 4-bit / 8-bit CLI flag** — documented in README but not yet wired in serve_transformers.py
- **sprite_pipeline aspect ratio** — currently defaults to square outputs; banner-shape generation (1024x256) would want different aspect handling

## Recommended next move

**Do `20a6fad` + `98314eb` rerun.** Same 9-prompt harness, current main, measure the real improvement vs 3/9. Expected ~7-8/9 based on resistor accounting. That's the fast validation that today's fixes landed clean.

**Then the two open resistors:**
1. **JSX-import validator** — catch `crypto`-class failures. Scan the most recent App.tsx for `<PascalName>` tags, verify each is either imported or defined locally. Reject pre-delivery with a specific error. Deterministic, observable.
2. **Multi-file build dispatch** — T3 course hit iter cap writing components sequentially. Either raise the per-skill iter budget (build-multi-page gets 30 instead of 20) OR have the skill prescribe batched writes via the swell mechanism. The skill file already describes phase 3 = "auth pages → test → protected pages." If the model actually follows that, the iter pressure drops.

After those two, Phase 1 is green enough to pivot: multi-model sweep + Phase 1.5 engine-dogfood.

## Canonical wins to preserve

- Auto-deliver on stuck post-build (`ce99915`) — directly saved T2 watchlist in the eval
- Tool-role guards (`98314eb`) — would have saved 4 failures had they been in the running process
- Observable-QA-only stack — no prose-tension noise, pass/fail determined by real artifacts
