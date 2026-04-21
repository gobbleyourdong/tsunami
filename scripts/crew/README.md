# Crew — overnight 6-instance orchestration

Six named Claude instances churning on parallel pools. Each has a plan, a reads-from-others section, a phase checklist, and a bonus long-churn-infinite phase. The crew's job is to explode tsunami coverage without blocking on single-threaded Qwen inference.

## The crew

| Name | Role | Output |
|------|------|--------|
| **Reef** 🌊 | Scaffold Factory — new genres, web-app subtypes, CLI, mobile, ML-training scaffolds | `scaffolds/<category>/<name>/` + canary tests |
| **Tide** 🌀 | Probe Factory — new verticals + hardened delivery-gate probes | `tsunami/core/*_probe.py` + `tests/fixtures/<vertical>/{pass,fail}/` |
| **Kelp** 🌿 | Orchestration Hardening — pain points + replay tests | patches to `agent.py`/`loop_guard.py`/`phase_machine.py` + `tsunami/tests/replays/` |
| **Coral** 🪸 | Telemetry Miner — reads logs, emits work queues | `~/.tsunami/crew/coral/{gap_queue,vertical_gap,pain_points,asset_gap}.jsonl` |
| **Current** 🌊 | Counter-Propagating Auditor — adversarial attacks on scaffolds + probes | `~/.tsunami/crew/current/attacks/*.json` + PR comments |
| **Shoal** 🐟 | ERNIE Sprite & Asset Pipeline — 55+ workflows (characters, VFX, tilesets, blocks, props, UI) with explicit animation sets per category | `scaffolds/engine/asset_workflows/<category>/` + `scaffolds/engine/asset_library/` |

Cross-feed: **Coral → Reef/Tide/Kelp/Shoal** (what to build), **Reef/Tide/Kelp/Shoal → Current** (what to attack), **Current → Coral** (what broke). Shoal is the visual-assets specialist — every scaffold Reef ships needs an asset workflow from Shoal.

## Launch

```bash
./scripts/crew/crew.sh launch       # spawns 5 instances
./scripts/crew/crew.sh status       # health check
./scripts/crew/crew.sh tail <name>  # tail a specific log
./scripts/crew/crew.sh stop         # SIGTERM all, grace, SIGKILL stragglers
```

## Per-instance state dirs

Shared plan path inside repo: `scripts/crew/<name>/plan.md`
Live state outside repo: `~/.tsunami/crew/<name>/` (pid, log, queues, attacks).

## Rules of the road

1. **No single instance ever runs the model.** All five are Claude Code instances — they write code, read logs, propose PRs. Qwen validation happens later via the replay/live pools (see `docs/orchestration-proposal.md` when drafted).
2. **Commit every artifact.** Maps Include Noise. Failed attempts stay as dated artifacts.
3. **Read before you write.** The reads-from-others section of each plan exists to keep the crew coordinated.
4. **Bonus long churn infinite.** After the phased checklist, each plan includes an open-ended "keep going until the heat death" phase. Use it.
