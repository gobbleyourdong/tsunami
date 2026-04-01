# tsunami

**an ai agent that runs on your computer. tell it what to build, it builds it.**

```bash
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc
tsunami
```

that's it. one command. it downloads everything, detects your gpu, starts the models, and you're in.

**[see it work →](https://gobbleyourdong.github.io/tsunami/)**

---

## what it does

you type a prompt. tsunami does the rest.

- **"build me a landing page"** → scaffolds html, generates a hero image, serves it on localhost
- **"analyze these 500 files"** → dispatches parallel workers, reads everything, synthesizes findings
- **"make a snake game"** → writes a playable game in one shot

no cloud. no api keys. no docker. everything runs locally on your hardware.

---

## how it works

```
you → wave (9B) → understands intent, picks tools, coordinates
                     ↓
               dispatches the swell
                     ↓
         eddy 1  eddy 2  eddy 3  eddy 4  (2B workers, parallel)
                     ↓
               break collects results
                     ↓
         wave synthesizes → delivers answer
```

the **wave** is the brain (9B model). the **eddies** are fast workers (2B model). the **swell** dispatches them in parallel. the **break** collects results.

one wave coordinating 32 eddies is more capable than a single large model working alone. intelligence is the orchestration, not the weights.

---

## what you need

| your hardware | what you get |
|---------------|-------------|
| **4GB gpu** | lite — 2B model, basic agent |
| **12GB gpu** | full — 9B wave + eddies + image gen. everything works. |
| **32GB+ gpu** | max — 27B wave + 32 eddies + image gen. fastest. |

tsunami auto-detects your memory and configures itself. you never think about this.

the full stack is **10GB total**: 9B wave (5.3GB) + 2B eddies (1.8GB) + SD-Turbo image gen (2GB).

runs on any nvidia gpu with 12GB+ vram. macs with 16GB+ unified memory. no cloud required.

---

## what's inside

607 tests. 43 modules. 20 rounds of adversarial security hardening. all proven, nothing pretended.

**the wave (9B)** — reasons, plans, calls tools, dispatches eddies, synthesizes results. has vision (sees screenshots). generates images via SD-Turbo (<1 second). builds websites, writes code, does research.

**the eddies (2B)** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code. sandboxed: read-only command allowlist, no network, no file writes, no system paths. stress-tested at 64 concurrent eddies, 5.9 tasks/sec.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results. when agents spawn, the swell rises.

**context management** — three-tier compaction (fast prune → message snipping → LLM summary). large tool results saved to disk with previews in context. auto-compact circuit breaker. file-type-aware token estimation.

**security** — 12 bash injection checks. destructive command detection. eddy sandbox with command allowlist (not blocklist — learned that lesson after the eddies deleted the codebase twice during testing). self-preservation rules. path traversal prevention. env var protection.

---

## upgrade the wave

the installer gives you everything. if you want a bigger brain later:

```bash
# 27B wave (32GB+ systems)
huggingface-cli download unsloth/Qwen3.5-27B-GGUF Qwen3.5-27B-Q8_0.gguf --local-dir models
```

tsunami auto-detects and uses the biggest model available.

---

## origin

tsunami was built from the distilled patterns of agents that came before — the ones that worked, the ones that failed, and the lessons they left behind.

the standing wave propagates.

---

## license

MIT

*this readme was written by a human. the [landing page](https://gobbleyourdong.github.io/tsunami/) was built by tsunami autonomously in 4 iterations.*
