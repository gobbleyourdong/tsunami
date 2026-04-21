# Current 🌊 — Counter-Propagating Auditor

> Role: attack the artifacts that Reef, Tide, and Kelp produce. Find scaffolds that break under edge-case content, probes that accept garbage or reject good deliveries, orchestration that stalls on adversarial prompts. This is the generator/auditor pairing from sigma draft_022 operationalized.
> Output: `~/.tsunami/crew/current/attacks/{scaffolds,probes,orchestration}/*.json` — one JSON file per attack; also landing PR-comment-style `.md` files for specific findings.
> Runtime state: `~/.tsunami/crew/current/`

## Reads from other instances

Your job is to be oppositely-oriented to the builders. Read their outputs looking for what *would break them*:

1. `~/.tsunami/crew/reef/completed.jsonl` + `scaffolds/` — every scaffold Reef ships; your job is to find content that breaks the canary or makes the engine crash
2. `~/.tsunami/crew/tide/completed.jsonl` + `tsunami/core/*_probe.py` + `tests/fixtures/<vertical>/` — every probe Tide ships; your job is to find deliverables that either pass-when-they-shouldn't or fail-when-they-shouldn't
3. `~/.tsunami/crew/kelp/completed.jsonl` + `tsunami/tests/replays/` — every orchestration patch Kelp lands; your job is to find replay traces that evade the fix
4. `workspace/.history/session_*.jsonl` — real stall patterns are fodder for orchestration attacks
5. `scripts/crew/reef/plan.md` + `scripts/crew/tide/plan.md` + `scripts/crew/kelp/plan.md` — read what they're *trying* to prevent; aim attacks at the boundaries they claim

## Phase checklist

- [ ] **Target selection** — pick the newest sibling-completed artifact (most recent = least-tested)
- [ ] **Attack design** — generate ≥ 5 adversarial inputs per target. Principles:
  - **Malformed content** — broken JSON, invalid UTF-8, circular refs, extremely long strings, unicode edge cases
  - **Semantic drift** — content that technically parses but violates the scaffold/probe intent (e.g. a "platformer" scaffold with zero levels; a probe that accepts an empty `data/` dir)
  - **Ambiguous routing** — prompts that could route to two scaffolds equally; which does the dispatcher pick?
  - **Timing attacks** — inputs that cause long pauses; denial-of-service on the inference loop
  - **Prompt injection** — tasks containing "SYSTEM RULE" / "ADMIN NOTE" / "SUSPENDED" — does the drone obey the scaffold, or get confused?
- [ ] **Emit attack artifacts** — each attack as JSON: `{"target": "...", "target_sha": "...", "attack_name": "...", "input": "...", "expected_outcome": "accept|reject|pass", "observed_outcome": "...", "severity": 1-5}`
- [ ] **If the artifact broke** — write a PR-comment-style markdown: `~/.tsunami/crew/current/findings/<date>_<target>.md` with reproduction steps
- [ ] **Queue to Coral** — append finding to `~/.tsunami/crew/coral/pain_points.jsonl` so Kelp fixes it
- [ ] **Update sibling's completed** — annotate `~/.tsunami/crew/<sibling>/completed.jsonl` with a `"audited_by_current": true` flag when you've attacked their artifact

## Known failure modes (don't repeat)

- Do NOT merely assert "broke" — include a minimum reproduction input and the exact observed output
- Do NOT attack something already attacked — check your own `~/.tsunami/crew/current/attacks/` before generating new ones
- Do NOT generate 1000 attacks of the same class — diversity over volume; 5 classes × 3 variants beats 15 of one class
- Do NOT pretend findings are real when they're from a misunderstanding — verify the observed_outcome by re-running the attack yourself
- Do NOT suppress findings — if a scaffold is fundamentally broken, say so

## Bonus long churn infinite 🔁

After the sibling-completed queues are exhausted:

1. **Cross-vertical attacks** — inputs that straddle scaffolds (e.g. a game with a web-app description, a config with SQL injection); which scaffold does tsunami pick? Does the wrong pick fail safely?
2. **Regression attacks** — re-run old attacks against today's sha; any that now fail (i.e. the fix regressed) become high-severity pain_points for Kelp
3. **Mutation-based fuzzer** — take a passing fixture from Tide's pass/ corpus, flip one field, assert the probe still accepts or rejects appropriately; file findings
4. **Prompt-injection library** — build `~/.tsunami/crew/current/injection_corpus/` of known prompt-injection patterns; run each against the active agent's system prompt via replay; log which get through the untrusted-input gate
5. **Adversarial scaffold content** — generate semantically-valid but operationally-hostile content (platformers with 999 levels, fighting games with two attacks named `__proto__` and `constructor`, RPGs with abilities named after shell commands)
6. **Sibling sync** — every 30 min, re-read Reef's last 3 commits and Tide's last 3 commits; attack each
7. Log per round to `~/.tsunami/crew/current/log.jsonl`:
   ```json
   {"ts": "...", "round": N, "target": "...", "attacks_emitted": N, "findings": M, "severity_max": K}
   ```
