# tsunami — repo-root pointer for AI coding agents

You're an AI coding agent (Claude Code or equivalent) that just opened
this repo at the root. **Tsunami is a scaffold library, not a binary you
run.** Your cold-start orientation lives one directory deeper:

→ **Read [`tsunami/CLAUDE.md`](tsunami/CLAUDE.md) first.** Choose-your-own-adventure
  catalog. ~390 lines. Tells you which scaffold to clone, which patterns
  to follow, and which load-bearing files to respect. The doc is designed
  to make you self-orient in one read.

## Quick map of what's here

- **`scaffolds/`** — 21 top-level dirs, but ~42 buildable templates total
  once you count sub-scaffolds. Top-level: 9 React (7 self-contained + 2
  inheriting), 3 bespoke-gate (api-only, chrome-extension, electron-app),
  1 web-game (`game`), 1 WebGPU engine (`engine`), 1 gamedev category, 5
  lighter categories (`cli`, `mobile`, `web`, `infra`, `training`), plus
  `scaffolds/nudges/` — the retro-game scrape reference catalog (Castlevania,
  Dragon Quest, Mario, etc., 69 game dirs). The 5 lighter categories
  contain 10 sub-scaffolds (cli/3, mobile/2, web/3, infra/1, training/1)
  + gamedev contains 9 standard sub-genres + `gamedev/cross/` is itself
  a category with 9 cross-genre sub-scaffolds. See `tsunami/CLAUDE.md`
  choose-your-own-adventure tables for the full enumeration.
- **`tsunami/`** — patterns + utilities the catalog references (vision_gate,
  undertow, circulation, deliver_gates, core probes, image processing, skills)
- **`deliverables/`** — past builds (reference, not active work)
- **`README.md`** — human-facing public pitch ("tsunami is a scaffold")
- **`requirements.txt`** — Python deps for the build/QA primitives

## What you should NOT do at this level

- Don't try to run a `tsunami` binary or `python -m tsunami` — neither
  exists. The agent loop was retired 2026-04-26; you ARE the agent loop now.
- Don't modify `scaffolds/` ad-hoc. The catalog is the product.
- Don't recreate deleted modules (`agent.py`, `cli.py`, `model.py`,
  `config.py`, `eddy.py`, `server.py`, etc.) just because something
  references them — those references are historical. See
  `tsunami/CLAUDE.md` "What was deleted" for the full purge story.

## If you're a human reading this

You probably wanted [`README.md`](README.md). That's the public pitch and
install instructions. This file is a 30-second orientation pointer for
AI agents that land at the repo root.
