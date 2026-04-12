# tsunami

**an ai agent that runs on your computer. tell it what to build, it builds it.**

**[see it work →](https://gobbleyourdong.github.io/tsunami/)**

**Windows (installer):**

Download [TsunamiSetup.exe](https://github.com/gobbleyourdong/tsunami/releases/latest) — double-click, it handles everything.

**Windows (manual):**

```powershell
.\setup.ps1
.\tsu.ps1
```

**Mac / Linux:**

```bash
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc
tsunami
```

**Docker:**

```bash
docker compose up
# or: docker run -p 9876:9876 tsunami "build me a calculator"
```

that's it. it downloads everything, detects your gpu, starts the models, opens the UI.

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

## the tension system

tsunami measures whether it's lying.

**current** — prose tension: is the agent hedging, fabricating, or grounded? 0.0 (truth) to 1.0 (hallucination).

**circulation** — reads the current and decides: deliver, search for verification, or refuse.

**pressure** — tracks tension over time. if tension stays high: force a search, force a strategy change, or stop and ask for help.

**undertow** — QA gate. pulls levers: screenshots, key presses, click tests, text reads. reports pass/fail. the wave reads the report and fixes what's broken.

---

## what you need

| tier | hardware | language model | image model |
|------|----------|----------------|-------------|
| **god** | 24GB+ GPU (5090 / A6000 / A100) | Gemma 4 E4B bf16 | Z-Image-Turbo + FLUX.2-klein-4B preloaded |
| **S** | 16GB+ GPU (4080 / 4090 / 3090) | Gemma 4 E4B bf16 | Z-Image-Turbo (~6GB, default) |
| **mid** | 8–16GB GPU | `--load-in-8bit` Gemma 4 E4B | `--image-model black-forest-labs/FLUX.2-klein-4B` (~4B, smaller) |
| **shit** | <8GB GPU / no GPU | `--load-in-4bit` or CPU | `--image-model stabilityai/sd-turbo` (~2GB legacy) or `none` |

tsunami auto-detects your GPU and configures itself. you never think about this.

one language model across every tier: **Gemma 4 E4B** — 128K native context, native tool calling, built-in thinking, multimodal vision.
image model swaps with the tier: **Z-Image-Turbo** (god/S, best text rendering) → **FLUX.2-klein-4B** (mid, smaller) → **SD-Turbo** (shit, legacy 2GB).

runs on nvidia GPUs, macs with 16GB+ unified memory, windows, linux. no cloud required.

---

## what's inside

**Gemma 4 E4B** — the single language model powering everything. bf16 (~10GB) by default; `--load-in-8bit` and `--load-in-4bit` flags available for smaller GPUs. native tool calling, built-in thinking, multimodal vision. one server on port 8090 handles wave, eddy, and watcher roles.

**the wave** — reasons, plans, calls tools, dispatches eddies, synthesizes results. generates images via Z-Image-Turbo. builds websites, writes code, does research. no iteration limit.

**the eddies** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results.

**the undertow** — QA lever-puller. auto-generates test levers from the HTML (every ID, every key binding, every button). pulls them all. reports what it sees.

**vision grounding** — extracts UI element positions from reference images. returns ratio-based CSS (percentages, aspect-ratio). resolution-independent.

**Z-Image-Turbo** — in-process image generation. no server needed. ~6GB, auto-downloads on first use. best text rendering for UI mockups. swap to `FLUX.2-klein-4B` (smaller, faster) via the `--image-model` flag. generates textures, icons, backgrounds, reference images.

**current / circulation / pressure** — the tension system. measures lies, routes decisions, tracks trajectory.

**context management** — three-tier compaction. large tool results saved to disk with previews. auto-compact circuit breaker.

**auto-fix layers** — research gate, mid-loop auto-wire, swell compile gate, dedup loop detection, React hook auto-import, reference save.

---

## install paths

| platform | install | run |
|----------|---------|-----|
| **Windows (installer)** | `TsunamiSetup.exe` | Desktop shortcut / Start Menu |
| **Windows (manual)** | `.\setup.ps1` | `.\tsu.ps1` |
| **Mac / Linux** | `setup.sh` | `tsu` |
| **Docker** | `docker compose build` | `docker compose up` |

the desktop shortcut opens the webUI in your browser. `tsu` auto-updates on every launch.

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
