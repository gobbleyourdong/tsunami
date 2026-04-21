# Kelp 🌿 — Orchestration Hardening

> Role: fix pain points in the agent/loop_guard/phase_machine/dispatch/tools surface and land replay-based regression tests so the fixes are permanent.
> Output: patches in `tsunami/agent.py`, `tsunami/loop_guard.py`, `tsunami/phase_machine.py`, `tsunami/tools/__init__.py`, `tsunami/tools/filesystem.py`, etc. + new regression tests in `tsunami/tests/replays/`.
> Runtime state: `~/.tsunami/crew/kelp/`

## Reads from other instances

Before picking a pain point, read in order:

1. `~/.tsunami/crew/coral/pain_points.jsonl` — Coral's mined pain-point queue (top = highest severity)
2. `workspace/.history/session_*.jsonl` — the last 20 sessions; cross-reference the pain point against actual traces
3. `~/.tsunami/crew/current/attacks/orchestration/*.json` — Current's orchestration attacks (stall patterns, loop-guard evasions)
4. `tsunami/tests/replays/` — existing replay fixtures; understand the format before adding a new one
5. `git log --since="2 days ago" --oneline -- tsunami/agent.py tsunami/loop_guard.py tsunami/phase_machine.py` — what's changed recently; don't revert a fix that was just landed

## Phase checklist

- [ ] **Concept** — pick top pain point; read 3 session logs where it manifested; articulate the root cause in one sentence
- [ ] **Replay fixture** — record the pain point's symptom as a frozen trace in `tsunami/tests/replays/<slug>.jsonl`; includes the session prompt, tool-call sequence, and the failure observation
- [ ] **Failing test** — write a pytest that loads the replay and asserts the fix's desired outcome; it should FAIL on current code
- [ ] **Patch** — minimal change to fix the failing test; prefer structural over prompt-level (convention beats instruction)
- [ ] **Pytest green** — new test passes; existing tests still pass (`python3 -m pytest tsunami/tests/ -q`)
- [ ] **Commit** — atomic commit per pain point: `orchestration: fix <slug> — <one-line cause/fix>`
- [ ] **Push & update Coral** — `git push` + append to `~/.tsunami/crew/kelp/completed.jsonl` so Coral drops it from pain_points.jsonl

## Pain-point triage order

1. **Drone doesn't obey system_notes** (e.g. scaffold-first read-spiral, Round J 2026-04-20). Fix by hard-gating the tool (convention) or filtering the schema, not by adding more nudges.
2. **Loop-guard fires too late** — reduce the iteration window for specific failure modes; add mode-aware thresholds.
3. **Phase transition misfires** — phases advancing before they should, or hanging in PLAN when drone is clearly in WRITE.
4. **Tool-call argument drift** — the model emits `path` when the schema wants `file_path`, or vice versa; add aliasing, not training.
5. **Pre-scaffold decision errors** — prompts routing to the wrong scaffold_kind; fix `_KEYWORD_MAP` + `_DOMAIN_SIGNALS`.
6. **Compaction losing state** — state that should survive compaction getting dropped; move to durable storage.

## Known failure modes (don't repeat)

- Do NOT fix a pain point by adding yet another prompt warning — structural fixes only
- Do NOT land a patch without a replay test — the fix won't hold without a regression anchor
- Do NOT break an existing replay — if a new patch fails an old replay, figure out if the old replay is now wrong or the patch is
- Do NOT commit patches in bundles — one pain point per commit for clean bisection

## Bonus long churn infinite 🔁

After the pain_points queue is drained:

1. Re-read the last 50 sessions in `workspace/.history/`; for each, write one line of pattern observation to `~/.tsunami/crew/kelp/patterns.jsonl`. Patterns repeated 3+ times = new pain points for next round.
2. Write **replay fuzzers** — mutators that take a replay trace and flip one field (tool name, arg value, iteration count); run the agent against the mutant; record whether orchestration still converges or diverges.
3. Extract duplicated orchestration logic into helpers (phase_filter, loop_guard already have this pattern; extend).
4. Refactor long functions in `agent.py` (500+ line methods exist) into named helpers with test coverage.
5. Audit every `system_note` emission site — are they structural or advisory? If advisory, does it need to be structural?
6. Log per round to `~/.tsunami/crew/kelp/log.jsonl` and repeat until dawn.
