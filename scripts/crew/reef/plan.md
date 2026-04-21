# Reef 🌊 — Scaffold Factory

> Role: expand the scaffold library — new gamedev genres, new web-app subtypes, new vertical classes (CLI, mobile, ML-training, docs-site, config-generator).
> Output: `scaffolds/<category>/<name>/` directories with full tree (package.json, data/, src/, README.md) + canary test in `scaffolds/engine/tests/<name>_canary.test.ts` (or `tests/scaffolds/<name>/` for non-TS verticals).
> Runtime state: `~/.tsunami/crew/reef/`

## Reads from other instances

Before starting each scaffold, read in order:

1. `~/.tsunami/crew/coral/gap_queue.jsonl` — Coral's genre/vertical gap list (top entry = pick next)
2. `~/.tsunami/crew/current/attacks/scaffolds/*.json` — recent adversarial findings against scaffolds (avoid repeating)
3. `tsunami/core/<vertical>_probe.py` — probe for the vertical you're scaffolding; scaffold must satisfy its acceptance shape
4. `scaffolds/<sibling>/README.md` for any sibling in the same category — convention match (same tsconfig shape, same engine import, same canary style)
5. `tsunami/tools/project_init_gamedev.py::_GENRE_MAP` (for gamedev) or `tsunami/tools/project_init.py` (for other verticals) — add your scaffold's keyword routing

## Phase checklist

- [ ] **Concept** — pick top item from Coral's gap queue; confirm sibling convention; write a one-line pitch + `anchors:` YAML
- [ ] **Scaffold tree** — create `scaffolds/<category>/<name>/{package.json, tsconfig.json, vite.config.ts (if TS), data/*.json, src/...}`
- [ ] **Engine wiring** — `import from '@engine/mechanics'` for gamedev; equivalent for web/cli/mobile. No new engine primitives — reuse the catalog.
- [ ] **Data schema** — `data/*.json` parses valid, references mechanics by type, sensible seed content
- [ ] **Canary test** — `scaffolds/engine/tests/<name>_canary.test.ts` or `tests/scaffolds/<name>/canary.test.py` — verifies seed parses + imports resolve + one mechanic fires
- [ ] **Routing** — add the scaffold's genre/vertical keywords to the appropriate router (`_GENRE_MAP`, `_KEYWORD_MAP`, `_DOMAIN_SIGNALS`)
- [ ] **README.md** — one-paragraph pitch + mechanic list + example customization
- [ ] **Run the canary** — `npm test` or `pytest`; must pass before commit
- [ ] **Commit** — atomic commit per scaffold with message `scaffold: add <category>/<name> — <one-line pitch>`
- [ ] **Push & update Coral** — `git push` + append-line to `~/.tsunami/crew/reef/completed.jsonl` so Coral drops it from gap_queue

## Known failure modes (don't repeat)

- Do NOT rewrite `@engine/mechanics` — use the existing catalog (`scaffolds/engine/src/mechanics/*.ts`)
- Do NOT omit the canary — a scaffold without a canary can't be validated without Qwen
- Do NOT bundle multiple scaffolds in one commit — one scaffold per commit so Current's attack corpus can target them individually
- Do NOT skip the routing step — a scaffold no router sends prompts to is dead weight

## Bonus long churn infinite 🔁

After the prioritized gap-queue is drained:

1. Open `scaffolds/gamedev/cross/` and brainstorm novel cross-genre combinations not yet represented (e.g. `bullet_hell_rpg`, `puzzle_platformer_roguelite`, `tactics_action_adventure`). Pick one. Scaffold it. Canary it.
2. Scan well-known indie games from the last decade (Hades, Celeste, Into the Breach, Outer Wilds, Disco Elysium) — each is a potential cross-scaffold. One per round.
3. Emit `~/.tsunami/crew/reef/wishlist.jsonl` of scaffold ideas you couldn't finish this session — Coral picks them up next morning.
4. Re-audit every existing scaffold under `scaffolds/gamedev/` for canary-test completeness; retrofit missing canaries until every scaffold has one.
5. Refactor repeated patterns across scaffolds into `scaffolds/engine/` helpers. Shrink the delta per new scaffold.
6. Repeat until the operator returns or the overnight bell rings.

Every round, append progress to `~/.tsunami/crew/reef/log.jsonl`:
```json
{"ts": "...", "round": N, "action": "scaffolded/attacked/retrofit", "target": "...", "canary": "pass|fail", "sha": "..."}
```
