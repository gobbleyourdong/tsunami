<p align="center">
  <img src="docs/banner.png" alt="tsunami wave banner" width="800">
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
- **"replicate the Game Boy UI"** — searches for reference images, generates a reference via Z-Image-Turbo, extracts element positions with vision grounding, builds to match
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

one language model does everything: **Gemma 4 E4B** (bf16, ~10GB). native tool calling, built-in thinking, multimodal vision. wave, eddies, and watcher all run on the same server. scale parallel instances by VRAM.

**wave** — the brain. reasons, plans, researches, builds.
**eddies** — fast parallel workers. read, search, execute, judge.
**swell** — dispatches eddies in parallel.
**break** — where results converge.
**undertow** — QA gate. tests what the wave built by pulling levers.

---

## the build pipeline

tsunami doesn't just write code and ship it. it follows a pipeline:

1. **research** — searches for reference images and code examples before writing anything
2. **generate** — creates reference images via Z-Image-Turbo (in-process, no separate server)
3. **ground** — extracts element positions from reference images using vision (Gemma 4 E4B multimodal). outputs ratio-based CSS positioning
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

| tier | hardware | language model | image model |
|------|----------|----------------|-------------|
| **S** | 16GB+ GPU (4080 / 4090 / 3090 / 5090) | Gemma 4 E4B bf16 (~10GB) | Z-Image-Turbo (~6GB, default) |
| **mid** | 12–16GB GPU | `--load-in-4bit` Gemma 4 E4B (~3GB) | Z-Image-Turbo |
| **low** | 8–12GB GPU | `--load-in-4bit` + `device_map=auto` (CPU overflow) | `--image-model stabilityai/sd-turbo` (~2GB) or `none` |

tsunami auto-detects your GPU and configures itself. you never think about this.

one language model across every tier: **Gemma 4 E4B** — 128K native context, native tool calling, built-in thinking, multimodal vision. quantization via `bitsandbytes` (4-bit NF4 or 8-bit) applies to the upstream `google/gemma-4-e4b-it` weights directly — no intermediate repo, no GGUF, no llama.cpp, no cross-compilation. pure torch wheels, same code path from 4GB to 80GB GPUs.

runs on nvidia GPUs, macs with 16GB+ unified memory, windows, linux. no cloud required.

---

## what's inside

**Gemma 4 E4B** — the single language model powering everything. bf16 (~10GB) by default; `--load-in-4bit` for ~3GB via bitsandbytes NF4, `--load-in-8bit` for ~6GB. quantization runs against the upstream `google/gemma-4-e4b-it` weights — no intermediate repo, multimodal vision preserved (mmproj stays fp16), same pure-torch code path. native tool calling, built-in thinking. one server on port 8090 handles wave, eddy, and watcher roles.

**the wave** — reasons, plans, calls tools, dispatches eddies, synthesizes results. generates images via Z-Image-Turbo. builds websites, writes code, does research. no iteration limit.

**the eddies** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results.

**the undertow** — QA lever-puller. auto-generates test levers from the HTML (every ID, every key binding, every button). pulls them all. reports what it sees.

**vision grounding** — extracts UI element positions from reference images. returns ratio-based CSS (percentages, aspect-ratio). resolution-independent.

**Z-Image-Turbo** — in-process image generation served from the same port as the LM. ~6GB, auto-downloads on first use, best prompt adherence for UI mockups. point `--image-model` at any HuggingFace text2image model (SD-Turbo, FLUX variants, your own fine-tune) — tsunami auto-picks the right Diffusers pipeline via `AutoPipelineForText2Image`. supports `mode="alpha"` (feathered luminance alpha for glows) and `mode="icon"` (magenta color-key for hard-edged sprites).

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
