<p align="center">
  <img src="docs/banner.png?v=14" alt="ツNami" width="800">
</p>

<h1 align="center">tsunami</h1>
<h2 align="center">ツNami ♡</h2>

<p align="center"><b><i>tsunami is a scaffold.</i></b></p>

<p align="center">
  ツNami picks the right one, fills it in, screenshots the result,<br/>
  fixes what's wrong, ships.
</p>

---

## the whole idea ♡

a scaffold is a polished starting point with a locked component vocabulary. tsunami ships **21 of them** in `ark/scaffolds/` — landing pages, dashboards, data viz, fullstack CRUD, real-time chat, auth apps, chrome extensions, electron apps, REST APIs, web games, native game genres, CLI tools.

you don't get a blank canvas. you get a scaffold that already knows what it wants to be. ツNami's job is to **match your idea to the right scaffold**, fill it in, and verify the result by actually looking at it. nothing fancier than that.

---

## install ♡

```bash
# Mac / Linux
curl -sSL https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.sh | bash
source ~/.bashrc && tsunami

# Windows (PowerShell)
iwr -useb https://raw.githubusercontent.com/gobbleyourdong/tsunami/main/setup.ps1 | iex
# close/reopen, then:
tsunami
```

set `ANTHROPIC_API_KEY` before first run. ツNami uses Claude as her brain.

---

## how she builds ♡

```
   prompt → match scaffold → read its locked component vocab
              ↓
          write code, run vite build, install npm deps as needed
              ↓
          drive a real headless browser, screenshot the output
              ↓
          ask Claude vision: "does this match the intent?"
              ↓
          if no → fix the specific thing → loop
          if yes → ship
```

three things keep her honest:

- **vision_gate** — Claude looks at the screenshot. opinion is concrete.
- **undertow** — Playwright pulls the levers (clicks, keys, console reads). reality is concrete.
- **circulation** — if she spirals (3+ identical fails, context overflow, infinite read), it catches her, cools her down, gives one recovery shot, then breaks cleanly.

she wanders off the beaten path. if it gets too crazy, the system turns her around.

---

## the catalog ✧

| family | scaffolds |
|---|---|
| **web (vision-gated)** | `react-app` · `landing` · `dashboard` · `data-viz` · `form-app` · `fullstack` · `realtime` · `ai-app` · `auth-app` |
| **bespoke gate** | `api-only` · `chrome-extension` · `electron-app` |
| **games** | `game` · `engine` (WebGPU) · `gamedev/{platformer, fighting, fps, jrpg, beat_em_up, racing, stealth, action_adventure, custom, cross}` |
| **lighter** | `cli` · `mobile` · `infra` · `web` · `training` |

orthogonal **work-type plans** in `tsunami/plan_scaffolds/`: `refactor`, `replicator` (compositional inner-app-inside-outer-shell), `research`.

eight **visual styles** in `tsunami/style_scaffolds/`, each paired with a matching `tsunami/undertow_scaffolds/<style>.md` QA approach.

eighteen **game genres** in `tsunami/genre_scaffolds/`.

---

## the honest parts ✿

- **bring your own Claude key.** ツNami doesn't ship one, doesn't proxy, doesn't add a billing layer. usage shows up on your Anthropic console. cost is visible and yours.
- **tsunami runs on your machine.** filesystem, vite build, Playwright, screenshots — all local. only the LLM call leaves the box.
- **the scaffolds are the moat.** the agent loop is just an executor. swap Claude for a different LLM later and the scaffolds still work.
- **major refactor in flight (April 2026).** the local-LLM stack was retired; Claude is the new orchestrator. expect transitional state in `agent.py` / `model.py` / `config.py` until the swap PR lands.
- **lightspeed development.** core files rewrite themselves within hours. expect rebases. the train has no brakes.

if you're an instance dropped into the codebase: read [`ark/tsunami/CLAUDE.md`](tsunami/CLAUDE.md). it's the choose-your-own-adventure cold-start.

---

## try it ♡

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
tsunami

> build me a landing page for a kombucha brand, deep dark theme
> build me a dashboard with a sidebar and three Recharts graphs
> build me a platformer with a red skeleton enemy
```

---

## want to contribute? ✿

**file an issue. don't open a PR.** (｡◕‿◕｡)

one dev drives the train. core files rewrite within hours. PRs conflict before reviewers can touch them. an issue is the contract:

- one paragraph: feature or bug
- repro if it's a bug, mock or sketch if it's a feature
- tag the surface — `agent`, `undertow`, `vision_gate`, `circulation`, `scaffold/<name>`

good ideas get built. you get credit in the commit. if you genuinely need to ship code yourself, say so — we'll carve out a branch with a contract so the rebase pain lands on me, not you. ♡

---

## license ✧

**public domain.** released under [the Unlicense](https://unlicense.org/). fork it, ship it, sell it, rename it. it belongs to everybody now.

<p align="center"><sub>made with ♡ by one dev and a lot of coffee · ツNami 2026</sub></p>
