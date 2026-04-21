# Crew — overnight 6-instance orchestration

Six named Claude instances churning on parallel pools. Each has a plan, a copy-paste launch prompt, a reads-from-others section, a phase checklist, and a bonus long-churn-infinite phase.

## The crew

| Name | Role | Output |
|------|------|--------|
| **Reef** 🌊 | Scaffold Factory — new genres, web-app subtypes, CLI, mobile, ML-training | `scaffolds/<category>/<name>/` + canary tests |
| **Tide** 🌀 | Probe Factory — new verticals + hardened delivery-gate probes | `tsunami/core/*_probe.py` + `tests/fixtures/<vertical>/{pass,fail}/` |
| **Kelp** 🌿 | Orchestration Hardening — pain points + replay tests | patches + `tsunami/tests/replays/` |
| **Coral** 🪸 | Telemetry Miner — reads logs, emits work queues | `~/.tsunami/crew/coral/{gap_queue,vertical_gap,pain_points,asset_gap}.jsonl` |
| **Current** 🌊 | Counter-Propagating Auditor — adversarial attacks | `~/.tsunami/crew/current/attacks/*.json` + PR-comment `.md` |
| **Shoal** 🐟 | ERNIE Sprite & Asset Pipeline — 55+ workflows | `scaffolds/engine/asset_workflows/<category>/` + asset library |

Cross-feed: **Coral → Reef/Tide/Kelp/Shoal** (what to build) · **Reef/Tide/Kelp/Shoal → Current** (what to attack) · **Current → Coral** (what broke).

## Launch sequence

### 1. Seed Coral's queues (once, idempotent)
```bash
./scripts/crew/seed.sh
```
Writes 36 work items to `~/.tsunami/crew/coral/` (15 scaffold gaps, 6 vertical gaps, 4 pain points, 7 asset gaps + 4 seed-script variants). Safe to re-run; appends only new ids.

### 2. If using the dedicated RunPod ERNIE for Shoal
```bash
export SHOAL_ERNIE_URL=http://<runpod-ip>:8092
```
Only needed before launching Shoal's instance. Other 5 don't read this.

### 3. Spawn each instance

Each crew member has a ready-to-copy launch prompt:

```
scripts/crew/reef/prompt.txt
scripts/crew/tide/prompt.txt
scripts/crew/kelp/prompt.txt
scripts/crew/coral/prompt.txt
scripts/crew/current/prompt.txt
scripts/crew/shoal/prompt.txt
```

Open six terminals (or tmux panes). In each, spawn a fresh Claude session and paste the contents of one `prompt.txt`. The prompt is self-contained — it tells the instance its name, plan path, inbox, crew mates, and start sequence.

Example (using Claude Code CLI):
```bash
# terminal 1
cd /home/jb/ComfyUI/CelebV-HQ/ark
claude --permission-mode bypassPermissions --add-dir . --add-dir ~/.tsunami/crew/reef < scripts/crew/reef/prompt.txt

# terminal 2
claude --permission-mode bypassPermissions --add-dir . --add-dir ~/.tsunami/crew/tide < scripts/crew/tide/prompt.txt

# ... and so on for kelp / coral / current / shoal
```

Or paste the prompt into the Claude Code interactive prompt if you prefer.

## Monitoring

```bash
# Structured round-by-round logs (every instance appends one line per round):
tail -F ~/.tsunami/crew/*/log.jsonl

# Commits landing from the fleet:
watch -n 30 'git log --oneline --since="1 hour ago"'

# Coral's queues draining (shrinking = progress):
watch -n 60 'wc -l ~/.tsunami/crew/coral/*.jsonl ~/.tsunami/crew/*/completed.jsonl'

# Attack findings from Current:
ls -lat ~/.tsunami/crew/current/findings/ 2>/dev/null | head
```

Tmux six-pane layout:
```bash
tmux new-session -d -s crew
for n in reef tide kelp coral current shoal; do
  tmux split-window -t crew "tail -F ~/.tsunami/crew/$n/log.jsonl 2>/dev/null || tail -F /tmp/null"
  tmux select-layout -t crew tiled
done
tmux attach -t crew
```

## Stop an instance

Find its PID in whichever shell you spawned it from; `Ctrl+C` or `kill <pid>`. No central kill-switch — manual spawn = manual stop. Trade-off for simplicity.

## Rules of the road

1. **No single instance runs Qwen.** All six are Claude Code — they write code, read logs, propose PRs. Qwen validation (live end-to-end runs) happens separately via whoever the operator delegates.
2. **Commit every artifact.** Maps Include Noise. Failed attempts stay as dated artifacts.
3. **Read before you write.** The reads-from-others section of each plan exists to keep the crew coordinated.
4. **Pull before push.** Six instances committing to `main` will race. Pull-rebase-retry on non-fast-forward. **Never force-push.**
5. **Bonus long churn infinite.** After the phased checklist, each plan has an open-ended phase for when the prioritized queue drains.

## Caveats for first overnight run

- No auto-restart — if an instance crashes, you'll notice when its `log.jsonl` stops growing
- No push serialization — if collisions get bad, move each instance to its own branch (`crew/reef`, `crew/tide`, …) and open PRs; for now they share `main` with pull-rebase
- No budget cap — watch Anthropic usage dashboard if you're credit-conscious
- `--permission-mode bypassPermissions` means the instances can do anything — `rm -rf` included. If an instance goes off-rails, kill it and revert

Start with one or two instances (Coral alone is lowest-blast-radius) for 15–30 min to see behavior before launching all six.
