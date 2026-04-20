<p align="center">
  <img src="docs/banner.png?v=5" alt="tsunami — the wave that builds" width="800">
</p>

# tsunami

**an ai coding agent that runs on your computer. nothing leaves your machine.**

you type a prompt. it scaffolds a project, writes the code, compiles it, drives a real browser to QA the output, and ships you a working build. on your GPU. no OpenAI. no Anthropic. no Google. no API keys. no telemetry. no "unexpected usage" bill.

**[see it work →](https://gobbleyourdong.github.io/tsunami/)**

```bash
# Mac / Linux
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc && tsunami

# Windows (PowerShell — not CMD, not Git Bash, not WSL)
iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
# close/reopen PowerShell, then:
tsunami
```

installer clones the repo, detects your GPU, downloads the models, starts the four local servers, opens the UI. same command on subsequent launches.

---

## why this exists

the hyperscalers have convinced everyone that intelligence belongs in someone else's datacenter. that you need a subscription to edit a text file. that "AI" means piping your code, your data, your *keystrokes* through their revenue funnel.

a consumer GPU runs a 35B MoE with 3B active params in FP8 at real-time speed. the model knows how to code, how to reason, how to use tools, how to call a browser. **the only reason you're still paying someone else to do this is that nobody built the harness.**

we built the harness.

---

## what's running

four processes on your box. one command to bring them up.

| tier | what | port |
|---|---|---|
| **LM** | Qwen3.6-35B-A3B-FP8 — hybrid linear/full-attention MoE, native FP8, tool calling, vision, reasoning mode | `:8095` |
| **image** | ERNIE-Image-Turbo (live-swappable to Base for keeper quality) | `:8092` |
| **embed** | Qwen3-Embedding-0.6B | `:8093` |
| **proxy** | OpenAI-compatible `/v1/chat` + `/v1/images` + `/v1/embeddings` passthrough | `:8090` |

Blackwell (GB10, 5090, B100) is the target — FP8 tensor cores + enough VRAM for all four tiers. Ada (40-series, L40) works on smaller configurations. macs with 64 GB+ unified memory run the same code path.

**everything is native transformers.** no llama.cpp, no sd.cpp, no vendor SDKs. the proxy wraps real model servers, not black boxes.

---

## how a build actually works

```
prompt → wave (LM) reasons about intent, picks scaffold, plans
           ↓
     pre-build riptide: if prompt has an image, system auto-grounds
     element positions before the model plans any write
           ↓
     swell dispatches parallel eddies (workers) as needed
           ↓
     wave writes code, auto-runs vite build after every .tsx write,
     auto-installs missing npm packages
           ↓
     post-build undertow: system drives a real headless browser,
     reads console errors, checks DOM, screenshots, grades
           ↓
     deliver when build + QA pass. iterate only on concrete failures.
```

the **system** decides when to call undertow and riptide. the model doesn't get to hand-wave a delivery — the gates are observable: `vite build` either compiles or it doesn't, playwright either finds the button or it doesn't.

---

## the agentic-speed stack

small-model drones fail in predictable ways — they generate 11 images before writing a file, they prop-guess components without reading the source, they emit narrative when they mean `project_init`. 12 layers of fingerprinted safeguards catch each failure mode and route the drone out of it. `python3 -m tsunami.speed_audit` exits 0 only if all 12 are wired. see `tsunami/speed_audit.py`.

measured: **25 min → 6 min** wall clock on the same landing-page brief, with regression tests that make the wins permanent.

---

## what this replaces

- Cursor / Windsurf / Copilot — piping your code to a vendor you don't own
- ChatGPT / Claude for coding — API fees, rate limits, "unexpected usage" dashboards
- v0 / bolt / lovable — hosted tree of templates
- local LM Studio / Ollama wrappers — no build loop, no QA, no pipeline

tsunami runs the same model they run, on hardware you already bought, with a pipeline designed for actual software engineering instead of marketing-demo output.

---

## the honest parts

- 40 GB+ VRAM recommended. anything less and you're squeezing the LM into swap.
- cold start is ~2 minutes (model load + multi-shape warmup). subsequent builds are real-time.
- QA is playwright-backed, not vibes. false-positive rate is below what a model could generate from prose heuristics. false-negatives happen when the model writes code that compiles but renders wrong in edge cases we don't yet lever.
- the smaller the drone, the more it ignores nudges. some layers are advisory; the HARD ones (L9 ceiling, turn-1 narration block, asset-existence gate) reject at the exec site.
- this is under heavy active development. core files conflict within hours. expect rebases.

---

## install / run / stop

```bash
tsunami                # install + run
tsu up                 # bring the 4-tier stack online (idempotent)
tsu down               # SIGTERM → SIGKILL-after-20s graceful teardown
tsu swap base          # switch ERNIE to keeper-quality mode
tsu swap turbo         # switch back
```

stack smoke test: `python3 tsunami/tests/test_stack_smoke.py`. end-to-end build eval: `python3 -m tsunami.tests.eval_tiered`.

---

## want to contribute?

**file an issue. don't open a PR.**

one dev drives the train. **the train has no brakes.** core files rewrite themselves within hours, PRs conflict before reviewers touch them, rebases eat the weekend. an issue is the contract:

- describe the feature or bug in one paragraph
- attach a repro if it's a bug, a mock or sketch if it's a feature
- tag it with the surface (`agent`, `undertow`, `ernie`, `scaffold/<name>`, `eval`)

good ideas get built. you get credit in the commit. if you genuinely need to ship code yourself, say so in the issue — we'll carve out a branch with a contract so the rebase pain lands on me, not you.

---

## license

**public domain.** this is a utility service for the open web, not a product.

released under [the Unlicense](https://unlicense.org/). fork it, ship it, sell it, rename it — we don't care and we can't stop you. there is no copyright to assign, no license to honour, no attribution clause to trip on. it belongs to everybody now.
