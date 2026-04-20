<p align="center">
  <img src="docs/banner.png?v=9" alt="ツNami — the agent that builds" width="800">
</p>

<h1 align="center">tsunami 津波 ♡</h1>

<p align="center"><b><i>an ai coding agent that lives on your computer.<br/>nothing leaves your machine. ever.</i></b></p>

<p align="center">
  you type a prompt. <b>Nami (ナミ)</b> scaffolds a project, writes the code, compiles it,<br/>
  drives a real browser to QA the output, and hands you a working build.<br/>
  on your GPU. no OpenAI. no Anthropic. no Google. no API keys. no telemetry.<br/>
  no "unexpected usage" email at 2am.
</p>

<p align="center"><b>→ <a href="https://gobbleyourdong.github.io/tsunami/">see Nami work live</a> ←</b></p>

---

## install ♡

```bash
# Mac / Linux
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc && tsunami

# Windows (PowerShell — not CMD, not Git Bash, not WSL)
iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
# close/reopen PowerShell, then:
tsunami
```

the installer clones the repo, finds your GPU, downloads the models, lights up the four local servers, opens the UI. run `tsunami` again next time — same command, Nami's waiting.

---

## meet Nami ナミ ✿

Nami is the agent. she's the **ナミ** in **ツナミ** — literally the *wave* half of *tsunami*. 津 (tsu, harbor) + 波 (nami, wave) = 津波.

she's a coder who happens to run on your hardware. when you ask her to build something she:

- reads the brief, thinks about it, picks a scaffold
- auto-grounds any reference image with computer vision before planning
- writes code, auto-installs npm deps, iterates until the build compiles
- drives a real headless browser to QA her own output
- hands you a working build, not a story about one

nothing leaves your box. not your code, not your prompt, not a single keystroke.

---

## what's running under the hood ♡

four processes, one command to light them all up.

| tier | what | port |
|---|---|---|
| **LM** | Qwen3.6-35B-A3B-FP8 — hybrid MoE, native FP8, tool calling, vision, reasoning mode | `:8095` |
| **image** | ERNIE-Image-Turbo (live-swappable to Base for keeper quality) | `:8092` |
| **embed** | Qwen3-Embedding-0.6B | `:8093` |
| **proxy** | OpenAI-compatible `/v1/chat` + `/v1/images` + `/v1/embeddings` passthrough | `:8090` |

Blackwell (GB10, 5090, B100) is home base — FP8 tensor cores plus enough VRAM for the whole stack. Ada (40-series, L40) runs smaller configurations fine. macs with 64 GB+ unified memory use the same code path.

**everything is native transformers.** no llama.cpp, no sd.cpp, no vendor SDKs. the proxy wraps real model servers, not black boxes wrapped in marketing.

---

## how Nami builds something ♡

```
  prompt → Nami reasons about intent, picks scaffold, plans
              ↓
   ✿ pre-build riptide: if the prompt has an image,
     the system auto-grounds element positions before
     Nami plans any write
              ↓
   ✿ swell dispatches parallel workers (eddies) as needed
              ↓
   ✿ Nami writes code, auto-runs vite build after every
     .tsx write, auto-installs missing npm packages
              ↓
   ✿ post-build undertow: the system drives a real
     headless browser, reads console errors, checks
     the DOM, screenshots, grades the output
              ↓
   ✿ deliver when build + QA both pass.
     iterate only on concrete failures.
```

the **system** decides when to call undertow and riptide. Nami doesn't get to hand-wave a delivery — the gates are observable: `vite build` either compiles or it doesn't, playwright either finds the button or it doesn't.

---

## the 12-layer speed stack ✧

small-model drones fail in predictable ways — they'll generate 11 images before writing a file, they'll prop-guess components without reading the source, they'll emit narrative text when they mean `project_init`. so we built twelve fingerprinted safeguards, one per failure mode. `python3 -m tsunami.speed_audit` exits `0` only if all twelve are wired. see `tsunami/speed_audit.py` for the layer map.

**measured:** ~25 min → ~6 min wall clock on the same landing-page brief. the wins are permanent because every layer has a regression test.

---

## what Nami replaces ♡

| instead of | Nami gives you |
|---|---|
| Cursor / Windsurf / Copilot | the same agentic loop, but your code stays on your disk |
| ChatGPT / Claude for coding | no API fees, no rate limits, no "unexpected usage" dashboards |
| v0 / bolt / lovable | a hosted template tree → a local agent that actually iterates |
| LM Studio / Ollama wrappers | you get the build loop + QA + pipeline those don't ship |

Nami runs the same-class model the hyperscalers run, on hardware you already own, with a pipeline designed for actual software engineering — not marketing-demo output.

---

## the honest parts ✿

- **40 GB+ VRAM** recommended. less and you'll be swapping the LM to system memory. you won't like it.
- **~2 min cold start** (model load + multi-shape warmup). subsequent builds are real-time.
- **QA is playwright-backed**, not vibes. false-positive rate is below what a model could generate from prose heuristics. false-negatives happen when the model writes code that compiles but renders wrong in edge cases we haven't levered yet.
- **smaller drones ignore nudges.** some of the twelve layers are advisory; the hard ones (L7 turn-1 narration block, L9 image-ceiling enforce, asset-existence gate) reject at the exec site.
- **this codebase is under lightspeed development.** core files rewrite themselves within hours. expect rebases. the train has no brakes.

---

## install / run / stop ♡

```bash
tsunami                # install + run everything
tsu up                 # bring the 4-tier stack online (idempotent)
tsu down               # SIGTERM → SIGKILL-after-20s graceful teardown
tsu swap base          # switch ERNIE to keeper-quality mode (50 steps)
tsu swap turbo         # switch back to fast Turbo (8 steps)
```

stack smoke test: `python3 tsunami/tests/test_stack_smoke.py` — 30s all-green check.
end-to-end build eval: `python3 -m tsunami.tests.eval_tiered` — 5-tier build suite.

---

## want to contribute? ✿

**file an issue. don't open a PR.** (｡◕‿◕｡)

one dev drives the train. the train has no brakes. core files rewrite themselves within hours, PRs conflict before reviewers can touch them, rebases eat weekends. an issue is the contract:

- describe the feature or bug in one paragraph
- attach a repro if it's a bug, a mock or sketch if it's a feature
- tag it with the surface — `agent`, `undertow`, `ernie`, `scaffold/<name>`, `eval`

good ideas get built. you get credit in the commit. if you genuinely need to ship code yourself, say so in the issue — we'll carve out a branch with a contract so the rebase pain lands on me, not you. ♡

---

## license ✧

**public domain.** ツNami is a utility service for the open web, not a product.

released under [the Unlicense](https://unlicense.org/). fork it, ship it, sell it, rename it — there's no copyright to assign, no license to honour, no attribution clause to trip on. it belongs to everybody now.

<p align="center"><sub>made with ♡ by one dev and a lot of coffee · 津波 2026</sub></p>
