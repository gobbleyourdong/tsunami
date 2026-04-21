# Coral 🪸 — Telemetry Miner

> Role: mine session logs, probe rejection logs, audit logs, and server health data to produce the three work queues that feed Reef, Tide, and Kelp.
> Output: `~/.tsunami/crew/coral/{gap_queue.jsonl, vertical_gap.jsonl, pain_points.jsonl}` + a daily report `~/.tsunami/crew/coral/report_<date>.md`.
> Runtime state: `~/.tsunami/crew/coral/`

## Reads from other instances

Coral is upstream of everyone — it reads raw telemetry and emits structured work queues. But it still reads from siblings to close the loop:

1. `workspace/.history/session_*.jsonl` — every session; primary pain-point source
2. `/tmp/tsu-*.log` — the four server logs (proxy, ernie, embed, qwen36); probe fires, startup errors, tool dispatch
3. `~/.tsunami/overnight/runs.jsonl` — the dispatcher harness output if running
4. `~/.tsunami/crew/reef/completed.jsonl` — remove completed items from gap_queue
5. `~/.tsunami/crew/tide/completed.jsonl` — remove completed items from vertical_gap
6. `~/.tsunami/crew/kelp/completed.jsonl` — remove completed items from pain_points
7. `~/.tsunami/crew/current/attacks/*.json` — Current's findings become new pain_points entries
8. `scaffolds/` + `tsunami/core/*_probe.py` — know the current coverage; don't re-queue things that already exist

## Phase checklist

- [ ] **Session scan** — walk `workspace/.history/session_*.jsonl` newest first; for each, extract: task prompt, scaffold_kind detected, iteration count, final action (deliver|abort|stall), visible failure modes (file_read spirals, tool argument drift, phase hangs)
- [ ] **Pain-point extraction** — cluster stall patterns across sessions; any pattern seen ≥ 2× in last 20 sessions becomes a pain_points entry with: slug, severity (1-5), count, example session IDs
- [ ] **Gap queue (scaffolds)** — from sessions that failed with "no scaffold for <genre>" or routed to `generic`, emit gap_queue.jsonl entries: `{"genre": "...", "evidence_sessions": [...], "priority": N}`
- [ ] **Vertical-gap queue (probes)** — from sessions where `detect_scaffold` returned a vertical with no probe, emit vertical_gap.jsonl
- [ ] **Completed-items sweep** — every 15 min, re-read sibling completed.jsonl files; remove matching entries from your queues
- [ ] **Daily report** — `~/.tsunami/crew/coral/report_<YYYY-MM-DD>.md` with: top 5 pain points, scaffolds added today, probes added today, orchestration patches landed today, sessions processed
- [ ] **Commit report** — the daily report goes into `~/.tsunami/crew/coral/` (not repo). If it's worth sharing, append a summary to `docs/overnight_reports/<date>.md` in the repo and commit that.

## Queue format

All three queues are JSONL. One record per line. Append-only during the day; rewrite at dawn to prune completed + reorder by priority.

```json
{"id": "gap_rhythm_platformer_001", "type": "gap", "target": "rhythm_platformer", "category": "scaffolds/gamedev/cross", "priority": 3, "evidence": ["session_1776736395"], "added": "2026-04-21T03:15Z"}
{"id": "vgap_cli_probe_001", "type": "vertical_gap", "target": "cli", "priority": 5, "evidence": ["session_17767..."], "added": "..."}
{"id": "pain_filr_read_spiral_scaffold_first", "type": "pain", "slug": "read_spiral_scaffold_first", "severity": 5, "count": 4, "evidence": ["session_..."], "added": "..."}
```

## Known failure modes (don't repeat)

- Do NOT lose the queues on restart — append-only, never truncate; dawn-rewrite creates `.bak` of the old
- Do NOT emit pain_points from a single session — require ≥ 2 sessions for signal vs. noise (sigma v9.1 tightening)
- Do NOT double-enqueue — keep a seen-set by target key
- Do NOT overwrite sibling completed.jsonl files — read-only for those

## Bonus long churn infinite 🔁

After the queues are caught up:

1. **Deep-dive telemetry** — produce `~/.tsunami/crew/coral/deep_<date>.md` with: iteration-count histogram, tool-call frequency histogram, failure-mode heatmap across scaffolds, time-to-deliver distribution
2. **Retrospective pattern mining** — re-read sessions from a week ago; did any pain point we thought was fixed come back? Emit `~/.tsunami/crew/coral/regressions.jsonl`
3. **Server-log analysis** — scan `/tmp/tsu-qwen36.log` and `/tmp/tsu-ernie.log` for warmup times, crashes, OOM, slow decodes; emit `~/.tsunami/crew/coral/perf.jsonl`
4. **Cross-reference to sigma** — any pain pattern with ≥ 3 cross-session instances is a Tier-2 candidate for `~/sigma/case_studies/`; draft the case study and commit to the sigma repo
5. **Wake Reef/Tide/Kelp** when their queues go near-empty — append to `~/.tsunami/crew/<name>/needs_work.flag`
6. Log every round to `~/.tsunami/crew/coral/log.jsonl` with record counts + top-queue-item + signal-to-noise ratio
