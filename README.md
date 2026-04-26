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

a scaffold is a polished starting point with a locked component vocabulary. tsunami ships **20 of them** in `scaffolds/` — landing pages, dashboards, data viz, fullstack CRUD, real-time chat, auth apps, chrome extensions, electron apps, REST APIs, web games, native game genres, CLI tools. plus a sibling `scaffolds/nudges/` directory with a retro-game scrape reference catalog (Castlevania, Dragon Quest, Mario, Metroid, etc. — used as cross-reference for game builds).

you don't get a blank canvas. you get a scaffold that already knows what it wants to be. ツNami's job is to **match your idea to the right scaffold**, fill it in, and verify the result by actually looking at it. nothing fancier than that.

---

## install ♡

```bash
git clone git@github.com:gobbleyourdong/tsunami.git
cd tsunami
```

that's it. tsunami isn't a binary you run. it's a scaffold library — files an AI coding agent ([Claude Code](https://claude.com/claude-code), or any equivalent harness with tool use + filesystem access) reads and builds from. point your agent at the repo and ask it to make something.

if you'll use the build harness end-to-end (vite, npm, screenshots), you'll also want:

```bash
pip install -r requirements.txt
playwright install chromium
```

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

ten **visual styles** in `tsunami/style_scaffolds/`. Most have a same-name `tsunami/undertow_scaffolds/<style>.md` QA approach, plus 7 additional cross-cutting undertows (web_polish, vision_analysis, bug_finding, brand_consistency, art_direction, game_feel, sprite_quality) — 17 undertows total.

seventeen **game genres** in `tsunami/genre_scaffolds/`.

---

## the honest parts ✿

- **tsunami doesn't run anywhere.** it's a library of files — scaffolds, patterns, locked component vocabularies, QA recipes. your AI agent runs locally, reads tsunami, and uses it. the only thing leaving your box is the agent's LLM call.
- **bring your own Claude key.** tsunami doesn't ship one and never will. your agent (Claude Code or equivalent) bills directly to your Anthropic console.
- **the scaffolds are the moat.** swap Claude for a different LLM later and the scaffolds still work. swap one agent harness for another and the scaffolds still work. tsunami is the resource pile; the agent is interchangeable.
- **major retirement landed 2026-04-26.** the local-LLM-orchestrator era is over. `agent.py` / `model.py` / `config.py` / `observer.py` and the rest of the agent-loop python (~67 files / ~24K lines) were nuked along with the local serving stack (Qwen3.6 / ERNIE / training / GGUF / mesh / installers / tsu CLI). tsunami's surface is now ~45 .py files: the load-bearing patterns (`vision_gate`, `undertow`, `circulation`, `deliver_gates`), the security gate (`outbound_exfil`), the routing utility, the bespoke probes (`core/*_probe.py`), image-processing tools, and the scaffold catalog. see [`tsunami/CHANGELOG.md`](tsunami/CHANGELOG.md) for the full purge story.
- **lightspeed development.** core files rewrite themselves within hours. expect rebases. the train has no brakes.

if you're an AI agent (Claude Code or equivalent) dropped into this repo: read [`tsunami/CLAUDE.md`](tsunami/CLAUDE.md). it's the choose-your-own-adventure cold-start.

---

## try it ♡

drop your AI agent into the cloned repo. Claude Code reads `tsunami/CLAUDE.md` automatically; other harnesses you'd point at it manually. then ask:

```
> build me a landing page for a kombucha brand, deep dark theme
> build me a dashboard with a sidebar and three Recharts graphs
> build me a platformer with a red skeleton enemy
```

the agent matches your idea to a scaffold, reads the locked component vocab, fills it in, screenshots, fixes what's wrong, ships.

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
