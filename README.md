# tsunami

**an ai agent that runs on your computer. tell it what to build, it builds it.**

```bash
git clone https://github.com/gobbleyourdong/tsunami.git
cd tsunami
./setup.sh
./tsu
```

that's the default path now. setup runs from a checked-out repo, installs into `./.venv`, verifies model downloads from `models/model-manifest.lock`, and keeps shell alias changes opt-in.

**[see it work →](https://gobbleyourdong.github.io/tsunami/)**

---

## what it does

you type a prompt. tsunami does the rest.

- **"build me a calculator"** → writes it, tests it, verifies it renders, delivers
- **"build a 3D pinball game"** → researches Three.js patterns, builds 869 lines, tests every key binding
- **"analyze these 500 files"** → dispatches parallel workers, reads everything, synthesizes findings

no cloud. no api keys. no docker. everything runs locally on your hardware.

---

## how it works

```
you → wave (9B) → understands intent, picks tools, coordinates
                     ↓
               swell dispatches parallel workers
                     ↓
         eddy 1  eddy 2  eddy 3  eddy 4  (2B workers)
                     ↓
               break collects results
                     ↓
               undertow tests the output
                     ↓
         wave reads QA report → fixes issues → delivers
```

**wave** — the brain. reasons, plans, researches, builds. (9B)
**eddies** — fast parallel workers. read, search, execute, judge. (2B)
**swell** — dispatches eddies. when agents spawn, the swell rises.
**break** — where results converge.
**undertow** — QA gate. tests what the wave built by pulling levers.

one wave coordinating 32 eddies is more capable than a single large model working alone. intelligence is the orchestration, not the weights.

---

## the tension system

tsunami doesn't just build things and hope for the best. it measures whether it's lying.

**current** — the lie detector. measures prose tension: is the agent hedging, fabricating, or grounded? returns 0.0 (truth) to 1.0 (hallucination).

**circulation** — the router. reads the current and decides: deliver, search for verification, or refuse rather than hallucinate.

**pressure** — the monitor. tracks tension over time across the session. if tension stays high, the system escalates: force a search, force a strategy change, or stop and ask for help.

**undertow** — the QA gate. after the wave builds something, the undertow pulls levers:
- takes a screenshot and asks an eddy "does this look like what was requested?"
- presses every key binding and checks if the screen changes
- reads every UI element and checks if it has content
- reports pass/fail per lever. no diagnosis. just facts.

the wave reads the QA report and figures out what's broken. the undertow keeps it simple — pull levers, report facts. the wave does the thinking. simple behaviors, emergent intelligence.

---

## research before building

tsunami searches before it codes. when asked to build something complex, it finds working examples and documentation first, then builds from real patterns instead of hallucinating API calls.

previous approach: guess at Three.js → black screen, 62% code tension
current approach: research cannon-es physics patterns → visible 3D pinball, 21% code tension

the system learns from what it finds. the prompt enforces it. the undertow catches what slips through.

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

## setup notes

- `setup.sh` is the supported installer. it replaces the old best-effort bootstrap flow.
- `INSTALL_SHELL_ALIAS=1 ./setup.sh` adds a `tsunami` alias to your shell rc if you want it.
- if `node` and `npm` are present, setup installs the ink cli with `npm ci` from the tracked `cli/package-lock.json`.
- the python repl path is still the fallback when node is unavailable.

---

## what's inside

634 tests. 43 modules. 20 rounds of adversarial security hardening.

**the wave (9B)** — reasons, plans, calls tools, dispatches eddies, synthesizes results. has vision (sees screenshots). generates images via SD-Turbo (<1 second). builds websites, writes code, does research.

**the eddies (2B)** — parallel workers with their own agent loops. each eddy can read files, run shell commands, search code. sandboxed: read-only command allowlist, no network, no file writes, no system paths. also serve as QA judges — one eddy looks at a screenshot and says whether it matches the intent.

**the swell** — dispatches eddies in parallel. the wave says "analyze these files" and the swell breaks it into tasks, sends each to an eddy, collects results. when agents spawn, the swell rises.

**the undertow** — QA lever-puller. auto-generates test levers from the HTML (every ID, every key binding, every button). pulls them all. reports what it sees. the wave reads the report and fixes what's broken.

**current / circulation / pressure** — the tension system. measures whether the agent is lying (current), routes decisions based on tension (circulation), and tracks tension trajectory over time (pressure). the lie detector, the router, and the monitor.

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
