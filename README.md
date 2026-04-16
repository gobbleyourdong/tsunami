<p align="center">
  <img src="docs/banner.png?v=5" alt="tsunami — the wave that builds" width="800">
</p>

# tsunami

**an ai agent that runs on your computer. tell it what to build, it builds it.**

**[see it work →](https://gobbleyourdong.github.io/tsunami/)**

**Mac / Linux:**

```bash
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc
tsunami
```

**Windows** (open **Windows PowerShell** — not CMD, not Git Bash, not WSL):

```powershell
iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
# close and reopen PowerShell, then:
tsunami
```

that's it. `tsunami` auto-installs git (via winget on Windows), clones the repo, detects your gpu, downloads the models, starts the server, opens the UI. Run the same `tsunami` command to launch on subsequent sessions.

---

## what it does

you type a prompt. tsunami does the rest.

- **"build me a calculator"** — writes it, tests it, verifies it renders, delivers
- **"build a 3D pinball game"** — uses the Tsunami Engine (WebGPU), builds 869 lines, tests every key binding
- **"replicate the Game Boy UI"** — searches for reference images, generates a reference via ERNIE-Image, extracts element positions with vision grounding, builds to match
- **"analyze these 500 files"** — dispatches parallel workers, reads everything, synthesizes findings

no cloud. no api keys. everything runs locally on your hardware.

---

## how it works

```
you → wave → understands intent, picks tools, coordinates
                     ↓
               swell dispatches parallel workers
                     ↓
         eddy 1  eddy 2  eddy 3  eddy 4  (parallel instances)
                     ↓
               break collects results
                     ↓
               undertow tests the output
                     ↓
         wave reads QA report → fixes issues → delivers
```

one language model does the reasoning: **Gemma-4-26B-A4B** (MXFP4, ~15GB via llama.cpp). native tool calling, built-in thinking, multimodal vision. wave, eddies, and watcher all talk to the same LM. **ERNIE-Image** (separate server) handles generation. scale parallel instances by VRAM.

**wave** — the brain. reasons, plans, researches, builds.
**eddies** — fast parallel workers. read, search, execute, judge.
**swell** — dispatches eddies in parallel.
**break** — where results converge.
**undertow** — QA gate. tests what the wave built by pulling levers.

---

## the build pipeline

tsunami doesn't just write code and ship it. it follows a pipeline:

1. **research** — searches for reference images and code examples before writing anything
2. **generate** — creates reference images via ERNIE-Image (dedicated server, three-path pipeline: GENERATE / BG_EXTRACT / PIXELIZE, composable into workflows like `logo` / `icon` / `sprite` / `pixelize` / `infographic`)
3. **ground** — extracts element positions from reference images using vision (Gemma 4 multimodal). outputs ratio-based CSS positioning
4. **build** — writes React components using the grounded positions. auto-wires App.tsx mid-loop
5. **compile** — vite build must pass. auto-checks after every .tsx write
6. **test** — undertow QA: screenshots, key presses, click tests, console error checks
7. **iterate** — no iteration limit. keeps going until all gates pass

the agent never guesses positions or colors. it sees the reference and matches it.

---

## quality gates

tsunami doesn't trust what the model says about its output. it verifies against reality.

every delivery runs through four observable gates, in order:

1. **scaffold-unchanged check** — did you actually replace the placeholder or just ship the stub?
2. **compile gate** — `npm run build` must pass (`tsc --noEmit && vite build`). typecheck catches missing imports.
3. **runtime gate** — page must render without JS errors. blank pages caught via pixel-color entropy.
4. **undertow** — browser QA. live-DOM scan finds interactables (buttons, inputs, `[role=button]`, `cursor:pointer` divs), injects click + type levers, waits for React state to settle, screenshots the post-interaction state, asks the multimodal LM what it sees.

all four are deterministic. no prose heuristics on the model's summary text. delivery fails only when a real artifact is broken.

undertow auto-injects interactions — you don't tell it which button to click. it scans the rendered DOM, pulls the first clickable, waits 1.5s for animations + setTimeout to settle, screenshots, reports. apps with buttons should DO something when clicked; undertow checks that they do.

---

## what you need

**24GB+ GPU minimum; 40GB+ recommended.** three-tier stack, one `tsu` command.

| tier | model | port | VRAM | cold load |
|---|---|---|---|---|
| LM | Gemma-4-26B-A4B MXFP4 (llama.cpp GGUF) | :8091 | ~15 GB | ~10s |
| image | ERNIE-Image-Turbo (bf16 swap-capable) | :8092 | ~25 GB peak | ~50s |
| proxy | tsunami FastAPI (forwards /v1/chat + /v1/images) | :8090 | trivial | <1s |

ports 8093–8095 are reserved for future animation backends (SDXL+ControlNet for rigid motion libraries, Qwen-Edit for rotation sprite sheets, Wan Animate for unique effect animations).

**for ≤24 GB cards**, set `ERNIE_MODE=gguf` before `tsu up` — runs the Q4_K_M Turbo DiT (~5 GB VRAM) instead of bf16. Loses the Turbo↔Base swap but fits on consumer hardware comfortably.

supported hardware: Blackwell (GB10, B100, 5090) gets MXFP4 native tensor cores; Ada (4080/4090, L40, H100) runs fine on bf16/Q4_K_M; macs with 40GB+ unified memory work via the same code path. Windows, Linux, macOS — no cloud, no API keys.

---

## what's inside

**Gemma-4-26B-A4B MXFP4** — the language model. 26B MoE with 4B active params, MXFP4 quantization native to Blackwell's fp4 tensor cores. ~15GB VRAM, ~48 tok/s decode. Native tool calling, built-in thinking, multimodal vision via mmproj-26B-F16. Served by llama.cpp's llama-server on :8091. One model handles wave, eddy, and watcher roles.

**the wave** — reasons, plans, calls tools, dispatches eddies, synthesizes results. generates images via ERNIE-Image. builds websites, writes code, does research. no iteration limit.

**the eddies** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results.

**the undertow** — QA lever-puller. auto-generates test levers from the HTML (every ID, every key binding, every button). pulls them all. reports what it sees.

**vision grounding** — extracts UI element positions from reference images. returns ratio-based CSS (percentages, aspect-ratio). resolution-independent.

**ERNIE-Image** — dedicated image-gen server on :8092 (own process so LM + image can coexist on one GPU cleanly). Three precision modes via `ERNIE_MODE` env var:
- `gguf` (Q4_K_M Turbo, ~5GB) — fastest, fits on 24GB consumer cards
- `bf16` (Turbo bf16, ~25GB) — best text rendering, supports live Turbo↔Base swap without restart via `tsu swap base`
- `base` (ERNIE-Image Base, ~25GB) — 50-step keeper quality for infographics and hero imagery

**three-path image pipeline** — primitives are composable: `GENERATE`, `BG_EXTRACT`, `PIXELIZE`. Workflows at `/v1/workflows/{kind}` compose them: `logo` = gen+bg_extract (wordmarks survive), `icon` = gen+bg_extract (single-subject), `sprite` = gen+bg_extract+pixelize, `pixelize` = gen+pixelize, `infographic` = Base-quality gen only. Standalone endpoints (`/v1/images/pixelize`, `/v1/images/extract-bg`) work on existing images too (user photos, not just gen output).

**observable gates** — scaffold-unchanged, compile, runtime, undertow. every delivery runs through all four. no prose heuristics.

**auto-install** — file_write scans imports, runs `npm install` for anything missing. saves 2-3 iterations per build.

**component library** — 45+ shadcn-style components pre-exported (Card with compound subcomponents, Box/Flex/Heading/Text/Image primitives, interactive widgets). project_init surfaces the exact export list on scaffold so the model can't hallucinate an import.

**context management** — three-tier compaction. large tool results saved to disk with previews. auto-compact circuit breaker.

**auto-deliver** — if the build is green but the model keeps trying to rebuild (stuck in post-build loop), tsunami synthesizes the delivery itself. better to ship a working build than loop until timeout.

**stack lifecycle** — `tsu up` brings everything online (idempotent, skips tiers already listening). `tsu down` does SIGTERM→SIGKILL-after-20s graceful teardown. `tsu swap <base|turbo>` switches ERNIE mode at runtime (bf16 only).

**observable gates** — scaffold-unchanged, compile, runtime, undertow. every delivery runs through all four. no prose heuristics.

**auto-install** — file_write scans imports, runs `npm install` for anything missing. saves 2-3 iterations per build.

**component library** — 45+ shadcn-style components pre-exported (Card with compound subcomponents, Box/Flex/Heading/Text/Image primitives, interactive widgets). project_init surfaces the exact export list on scaffold so the model can't hallucinate an import.

**context management** — three-tier compaction. large tool results saved to disk with previews. auto-compact circuit breaker.

**auto-deliver** — if the build is green but the model keeps trying to rebuild (stuck in post-build loop), tsunami synthesizes the delivery itself. better to ship a working build than loop until timeout.

---

## install paths

| platform | install | run |
|----------|---------|-----|
| **Mac / Linux** | `curl -sSL .../setup.sh \| bash` | `tsunami` |
| **Windows** | `iwr -useb .../setup.ps1 \| iex` | `tsunami` (after PowerShell restart) |

both paths auto-update on every launch. the install command clones the repo, installs dependencies (including git itself on Windows via winget if missing), downloads model weights, and wires `tsunami` into your shell so you can invoke it from anywhere.

---

## contributing

this codebase is under heavy active development. PRs against core files will likely conflict within hours.

**best approach:**
1. open an issue first to discuss what you want to change
2. target isolated new files (new scaffolds, new tools, new tests)
3. keep PRs small and focused
4. expect rebases — main moves fast

we read every PR and incorporate good ideas even if we can't merge directly.

---

## license

MIT
