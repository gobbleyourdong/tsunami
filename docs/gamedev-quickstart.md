# Gamedev build — server quickstart

Brief guide for bringing up the tsunami stack and driving a gamedev build end-to-end. Assumes you're inside the repo (`~/ComfyUI/CelebV-HQ/ark/`).

## 1. Bring the stack up

```bash
./tsu up           # background all model servers, then exit (no REPL)
```

Brings up four ports. First boot is ~2 min (Qwen load + warmup).

| Port | Service | Health | Log |
|------|---------|--------|-----|
| 8090 | tsunami proxy (OpenAI-compat: `/v1/chat`, `/v1/images`, `/v1/embeddings`) | `curl :8090/health` | `/tmp/tsu-proxy.log` |
| 8092 | ERNIE-Image-Turbo bf16 (swap-capable → Base for keepers) | `curl :8092/healthz` | `/tmp/tsu-ernie.log` |
| 8093 | Qwen3-Embedding-0.6B (opt-out with `EMBED=off tsu up`) | `curl :8093/health` | `/tmp/tsu-embed.log` |
| 8095 | Qwen3.6-35B-A3B-FP8 (LM + vision, MTP-capable, ~35 GB) | `curl :8095/health` | `/tmp/tsu-qwen36.log` |

Verify the whole stack answered before dispatching any build:

```bash
curl -sf :8090/health && curl -sf :8092/healthz && curl -sf :8095/health && echo OK
```

## 2. Choose your driver

### Option A — Web UI (FastAPI on :3000)

```bash
./tsu              # launches stack (if down) + WebUI (Ink CLI or python REPL)
# then open http://localhost:3000
```

UI backend is `tsunami.server`. WS bridge on `:3002` streams agent iterations, file watcher on `:3003` pushes deliverable changes. UI lives in `ui/index.html`.

### Option B — Headless (one-shot smoke)

```bash
# Drop a prompt that names a genre so the dispatcher routes cleanly
python3 -c "
import asyncio
from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
cfg = TsunamiConfig.from_env(TsunamiConfig.from_yaml('config.yaml'))
print(asyncio.run(Agent(cfg).run(
    'Build a metroidvania-roguelike called Sunken Halls — 4 rooms, 2 abilities (dash, double-jump), 1 boss. Use the metroid-runs scaffold.'
)))
"
```

### Option C — Overnight harness (batch matrix)

```bash
python -m tsunami.harness.matrix_gen --tracks gamedev --count 8 --out ~/.tsunami/overnight/matrix.jsonl
python -m tsunami.harness.dispatcher --root ~/.tsunami/overnight --workers 2
# morning:
python -m tsunami.harness.morning_report --root ~/.tsunami/overnight
```

## 3. Genre surface

`tsunami/tools/project_init_gamedev.py` genre-map routes prompt terms → scaffold dir. Current library (`scaffolds/gamedev/`):

**Root genres:** `action_adventure`, `fighting`, `fps`, `jrpg`, `platformer`, `racing`, `stealth`, `custom`
**Cross genres:** `cross/action_rpg_atb`, `cross/magic_hoops`, `cross/metroid_runs`, `cross/ninja_garden`, `cross/rhythm_fighter`

To force a specific scaffold, either use the canonical genre name in the prompt (`action_adventure`, `metroid-runs`, `dead-cells`, `zelda-ff`, …) or pass `genre=<key>` to the `project_init_gamedev` tool call.

## 4. Delivery-gate probes (what validates a gamedev build)

`tsunami/core/dispatch.py::detect_scaffold()` auto-routes to one of two probes:

- **`gamedev_scaffold_probe`** (data-driven flow): `package.json` present + engine dep, `data/*.json` parses, at least one `data/*.json` differs from seed (so the agent actually customized the scaffold), `src/scenes/*.ts` imports from `@engine/mechanics` or references a mechanic by type.
- **`gamedev_probe`** (legacy flow): `public/game_definition.json` validates + assets manifest resolves.

Both probes return structured reasons on failure. A delivery that fails the probe is rejected by the agent's delivery gate — the agent keeps iterating.

## 5. Where output lands

- **Web UI path:** `workspace/deliverables/<project>/` (from `config.yaml::workspace_dir`).
- **Headless path:** same, under the workspace directory resolved at run time.
- **Overnight harness:** `~/.tsunami/overnight/runs/<row_id>/deliverable/`.

The probe runs against the deliverable's project dir. If it passes, the agent writes `tsunami.md` into the project dir and flags the build complete.

## 6. Common failures

| Symptom | Check |
|---------|-------|
| Stack up but agent hangs | `curl :8090/v1/models` — if it 502s, proxy started before :8095. `./tsu down && ./tsu up` |
| `detect_scaffold` returns `generic` on a gamedev prompt | Prompt didn't name a genre, AND the scaffold wasn't provisioned. Name a genre or call `project_init_gamedev` first |
| Probe says "data files identical to seed" | Agent provisioned but didn't customize. Re-prompt with specific content (enemies, levels, abilities) by name |
| ERNIE swap hangs | Only `ERNIE_MODE=bf16` (default) supports swap. Base-mode stacks don't swap |
| Port collision | `./tsu down` clears :3000,:3002,:3003,:8090,:8092,:8093,:8095. Then `./tsu up` |

## 7. Teardown

```bash
./tsu down         # SIGTERM → 20s grace → SIGKILL stragglers across all ports
```

---

**Full stack reference:** `README.md` (section "models") and `tsu` (shell script itself — all flags and env vars are documented inline).

**Scaffold reference:** `scaffolds/gamedev/*/README.md` per genre.

**Probe reference:** `tsunami/core/gamedev_scaffold_probe.py`, `tsunami/core/dispatch.py::detect_scaffold`.
