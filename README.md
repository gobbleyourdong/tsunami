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

that's it. `tsunami` auto-installs git (via winget on Windows), clones the repo, detects your gpu, downloads the models, starts the server, opens the UI. run the same `tsunami` command to launch on subsequent sessions.

---

## what it does

you type a prompt. tsunami does the rest.

- **"build me a calculator"** — scaffolds, writes it, compiles, runs a real-browser QA pass, delivers
- **"build a 3D pinball game"** — uses the Tsunami Engine (WebGPU), writes hundreds of lines of code, tests every key binding
- **"replicate this Game Boy reference"** — drops the image path in the prompt; tsunami auto-grounds it with vision before writing any code
- **"analyze these 500 files"** — dispatches parallel eddy workers, reads everything, synthesizes findings

no cloud. no api keys. everything runs locally on your hardware.

---

## how it works

```
you → wave → understands intent, picks tools, coordinates
                     ↓
         pre-build riptide gate auto-grounds any image in the prompt
                     ↓
               swell dispatches parallel workers
                     ↓
         eddy 1  eddy 2  eddy 3  eddy 4  (parallel instances)
                     ↓
               break collects results
                     ↓
               wave writes code, runs shell build, iterates
                     ↓
         post-build undertow gate auto-QAs the deliverable
                     ↓
            only real failures loop back to the wave to fix
```

one language model does the reasoning: **Qwen3.6-35B-A3B-FP8** (hybrid linear/full-attention MoE, native transformers, block-128 FP8 e4m3 weights, ~34 GB VRAM). native tool calling, reasoning mode, multimodal vision. wave, eddies, and QA compare all talk to the same LM. **ERNIE-Image** (separate server) handles generation. **Qwen3-Embedding-0.6B** (separate server) handles embeddings. scale parallel instances by VRAM.

**wave** — the brain. reasons, plans, researches, builds.
**eddies** — fast parallel workers. read, search, execute, judge.
**swell** — dispatches eddies in parallel.
**break** — where results converge.
**undertow** — playwright QA harness. screenshots, clicks, reads text, detects console errors + ghost classes.
**riptide** — vision grounding. extracts UI element positions from reference images as CSS percentages.

---

## system-forced gates

the model does as little decision-making as possible. the **system** decides when to call undertow and riptide; the model only gets re-engaged if there's a real failure to fix.

**pre-build riptide gate** — at the start of every run, the agent scans the user prompt for an image path (png/jpg/webp). if one exists on disk, the system calls `riptide.execute(image_path, generic_elements)` directly and injects the grounding result as a user-turn note. the model sees precise positions before it plans any file_write.

**post-build undertow gate** — when the model thinks it's done (calls `message_result`), the agent intercepts once, runs `undertow.pull_levers` against the latest dist's index.html with a minimal lever set (console errors only — narrow, unambiguous). if the lever passes, delivery stands. if it fails, task_complete is reset to False, the failures are injected as a user turn, and the model iterates on fixes.

both gates fire exactly once per run. the tool_history records `undertow` / `riptide` entries regardless of whether the model decided to call them — so eval tool-coverage accounting reflects the system's work, not the model's choices.

---

## the build pipeline

tsunami doesn't just write code and ship it. it follows a pipeline:

1. **research** — searches for reference images and code examples before writing anything
2. **ground** — auto-grounds any image in the prompt via riptide (system-forced, not model-decided)
3. **generate** — creates reference images via ERNIE-Image when asked (three-path pipeline: GENERATE / BG_EXTRACT / PIXELIZE)
4. **build** — writes React components using the grounded positions. auto-wires App.tsx mid-loop
5. **compile** — `vite build` must pass. auto-checks after every .tsx write
6. **qa** — system-forced undertow pass on the built dist (console errors = real ship-blocker)
7. **iterate** — model only re-engaged if QA found a concrete failure; deliver-gate forces message_result once the build + QA both pass

---

## quality gates

tsunami doesn't trust what the model says about its output. every delivery runs through deterministic gates:

1. **scaffold-unchanged check** — did you actually replace the placeholder or just ship the stub?
2. **compile gate** — `npm run build` must pass (`tsc --noEmit && vite build`). typecheck catches missing imports.
3. **runtime gate** — page must render without JS errors. blank pages caught via pixel-color entropy.
4. **system undertow** — playwright console lever on the built dist. no prose heuristics.

delivery fails only when a real artifact is broken.

---

## what you need

**40 GB+ unified memory / VRAM recommended.** four-tier stack, one `tsu` command.

| tier | model | port | VRAM | cold load |
|---|---|---|---|---|
| proxy | tsunami FastAPI (forwards /v1/chat + /v1/images + /v1/embeddings) | :8090 | trivial | <1s |
| image | ERNIE-Image-Turbo (native transformers, bf16, swap-capable → Base) | :8092 | ~22 GB | ~60s |
| embed | Qwen3-Embedding-0.6B (native transformers, last-token pool + L2 norm) | :8093 | ~1.2 GB | ~10s |
| LM | Qwen3.6-35B-A3B-FP8 (native transformers, hybrid linear/full-attn MoE) | :8095 | ~34 GB | ~110s load + ~90s multi-shape warmup |

the proxy exposes OpenAI-compatible `/v1/chat/completions`, `/v1/images/generate`, and `/v1/embeddings`. forward body passthrough (extras like `enable_thinking`, `chat_template_kwargs`, `min_p`, `presence_penalty` thread through untouched).

supported hardware: Blackwell (GB10, B100, 5090) is primary — FP8 native tensor cores, 128 GB unified on GB10 fits the full stack comfortably. Ada (4080/4090, L40, H100) runs the embed + ERNIE tiers fine; Qwen3.6-35B-A3B-FP8 needs 40 GB+ VRAM on Ada. macs with 64 GB+ unified memory work via the same code path. Windows, Linux, macOS — no cloud, no API keys.

**anti-GGUF repo policy** — every tier is native transformers. no llama.cpp, no sd.cpp. the proxy used to forward to `llama-server` / `sd-server` over localhost; that path is removed. all inference is pure transformers + our FP8 kernel shim (DeepSeek reference Triton GEMM for Qwen3.6's block-128 e4m3 shape).

---

## what's inside

**Qwen3.6-35B-A3B-FP8** — the language model. 35B MoE with 3B active params, native block-128 FP8 e4m3 weights, hybrid linear+full attention layers. ~34 GB VRAM, static cache implementation (262144 native context, no YaRN needed up to that ceiling), pinned-thread boot warmup across 3 prompt shapes so the first real request isn't cold. Native `<tool_call><function=NAME><parameter=KEY>value</parameter></function></tool_call>` emission parsed server-side into OpenAI `message.tool_calls[]`. Reasoning mode toggle via top-level `enable_thinking` request field.

**MTP (multi-token prediction)** — Qwen3.6 ships an MTP speculative-decoding head. research target, not yet wired into prod serving. current measurement: 13% greedy / ~30% sample accept under eager attention (up from 9% / ~27% with the default SDPA dispatch — iter-33 landed the eager fix after pinning a BF16 round-trip precision drift in the fc projection). full root-cause chain documented in `tsunami/serving/mtp_module.py`.

**the wave** — reasons, plans, calls tools, dispatches eddies, synthesizes results. generates images via ERNIE. builds websites, writes code, does research. no per-run iteration cap (safety valves force delivery after specific stall patterns, not absolute counts).

**the eddies** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results.

**undertow** — playwright-backed QA lever-puller. actions: `screenshot`, `press`, `click`, `read_text`, `type`, `console`, `ghost_classes`, `motion`, `sequence`, `wait`. levers with `expect=` phrases trigger an LLM compare call (routed through the proxy so it honours `enable_thinking=False`); expect-free levers are pure DOM/pixel.

**riptide** — vision grounding tool. calls the proxy's multimodal chat endpoint (Qwen3.6 handles vision natively) with an image + element list, parses the 0-1000 normalized bbox coordinates Qwen emits, and returns CSS-percent positions. scan ratio is resolution-independent.

**ERNIE-Image** — dedicated image-gen server on :8092. bf16 Turbo by default (~22 GB, supports live Turbo↔Base swap via `tsu swap base`/`tsu swap turbo`). the Base model (50-step keeper quality) is reserved for infographics and hero imagery where Turbo's 8-step sampling isn't sharp enough.

**three-path image pipeline** — primitives are composable: `GENERATE`, `BG_EXTRACT`, `PIXELIZE`. Workflows at `/v1/workflows/{kind}` compose them: `logo` = gen+bg_extract (wordmarks survive), `icon` = gen+bg_extract (single-subject), `sprite` = gen+bg_extract+pixelize, `pixelize` = gen+pixelize, `infographic` = Base-quality gen only. Standalone endpoints (`/v1/images/pixelize`, `/v1/images/extract-bg`) work on existing images too.

**Qwen3-Embedding-0.6B** — dedicated embeddings server on :8093 (native transformers). last-token pooling + L2 normalization per the model card, optional Matryoshka dim truncation via `dim=` (32–1024), instruction prefix for retrieval queries (`Instruct: {task}\nQuery:{q}`). warmup forward at module load so first request isn't cold. served via proxy at `/v1/embeddings`.

**component library** — 45+ shadcn-style components pre-exported (Card with compound subcomponents, Box/Flex/Heading/Text/Image primitives, interactive widgets). project_init surfaces the exact export list on scaffold so the model can't hallucinate an import.

**auto-install** — file_write scans imports, runs `npm install` for anything missing. saves 2-3 iterations per build.

**context management** — three-tier compaction. large tool results saved to disk with previews. auto-compact circuit breaker.

**auto-deliver** — if the build is green but the model keeps trying to rebuild (stuck in post-build loop), the agent's #14 deliver-gate forces message_result. better to ship a working build than loop until timeout.

**stack lifecycle** — `tsu up` brings everything online (idempotent, skips tiers already listening). `tsu down` does SIGTERM→SIGKILL-after-20s graceful teardown. `tsu swap <base|turbo>` switches ERNIE mode at runtime.

---

## tool registry

the wave calls exactly these 11 tools. the eval exercises every one.

| tool | what it does |
|---|---|
| `project_init` | scaffold a new project from a template (react-app, vanilla-html, three-game) |
| `file_write` | write a file; auto-runs `npm install` for any new imports |
| `file_read` | read a file; honours large-file chunking |
| `file_edit` | replace-a-string or patch edit |
| `shell_exec` | run a shell command in the project dir; auto-deliver trips when build passes here |
| `search_web` | DuckDuckGo lite scrape |
| `undertow` | playwright QA — levers on a running HTML file |
| `riptide` | vision grounding on a reference image |
| `generate_image` | ERNIE-Image generate / bg-extract / pixelize / workflow |
| `message_chat` | conversational turn (not a delivery) |
| `message_result` | final delivery — triggers the system undertow gate |

---

## eval

`python3 -m tsunami.tests.eval_tiered` runs a 5-tier suite, 1 prompt per tier, each adding one new tool on top of the previous tier's baseline.

| tier | app | new tool exercised | budget |
|---|---|---|---|
| T1 | counter app | (baseline: project_init + file_write + shell_exec + undertow + message_result) | 600s |
| T2 | pomodoro timer | file_edit / file_read (iteration) | 900s |
| T3 | birthday card maker | generate_image | 1200s |
| T4 | calculator matching a reference image | riptide (system-forced via pre-build gate) | 1500s |
| T5 | crypto price tracker | search_web | 1500s |

run the full suite: `python3 -m tsunami.tests.eval_tiered`. single tier: `--tier T3`. plan-only: `--dry-run`. results drop to `workspace/training_data/eval_tiered.{json,md}` with pass / delivered / tool-coverage per tier + overall.

separate from the build eval, `python3 tsunami/tests/test_stack_smoke.py` is a 30-second end-to-end smoke that confirms all four tiers are healthy, generation returns a correct one-token answer via the proxy, embeddings return 1024-dim vectors, and the undertow harness can pull levers on a local HTML page.

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
