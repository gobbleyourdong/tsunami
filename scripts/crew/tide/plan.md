# Tide 🌀 — Probe Factory

> Role: build new delivery-gate probes for under-covered verticals (mobile, CLI, ML-training, docs-site, config-generator, data-pipeline) and harden the 9 existing probes (extension, electron, openapi, server, sse, ws, gamedev-legacy, gamedev-scaffold, _probe_common).
> Output: `tsunami/core/<vertical>_probe.py` + paired fixture corpus under `tests/fixtures/<vertical>/{pass,fail}/` + pytest test in `tsunami/tests/test_<vertical>_probe.py`.
> Runtime state: `~/.tsunami/crew/tide/`

## Reads from other instances

Before starting each probe, read in order:

1. `~/.tsunami/crew/coral/vertical_gap.jsonl` — Coral's vertical-gap list (top entry = pick next)
2. `~/.tsunami/crew/current/attacks/probes/*.json` — recent adversarial findings against probes (adversarial inputs your probe must reject)
3. `scaffolds/<category>/<name>/` — Reef's scaffolds for the vertical you're probing; the probe must accept a clean build of each one
4. `tsunami/core/gamedev_scaffold_probe.py` + `tsunami/core/ws_probe.py` — two well-shaped examples to model against
5. `tsunami/core/dispatch.py::detect_scaffold` — your new probe must register here for auto-dispatch

## Phase checklist

- [ ] **Concept** — pick top item from Coral's vertical_gap; read the sibling probes to internalize the convention
- [ ] **Acceptance shape** — write down in the probe's docstring: what files must exist, what must parse, what must run, what would be evidence of failure
- [ ] **Pass fixtures** — `tests/fixtures/<vertical>/pass/{minimal,typical,rich}/` — three levels of completeness, all should be accepted
- [ ] **Fail fixtures** — `tests/fixtures/<vertical>/fail/{empty,malformed,unwired,stub_only}/` — at least four failure modes, all should be rejected
- [ ] **Probe module** — `tsunami/core/<vertical>_probe.py` with `async def <vertical>_probe(project_dir: Path, task_text: str = "") -> ProbeResult`
- [ ] **Dispatch registration** — add to `_PROBES` dict in `tsunami/core/dispatch.py` and extend `detect_scaffold()` with your vertical's fingerprint
- [ ] **Test** — `tsunami/tests/test_<vertical>_probe.py` with pytest: iterate pass/ (expect accepted), iterate fail/ (expect rejected)
- [ ] **Run pytest** — must be 100% on pass, 100% on fail before commit
- [ ] **Commit** — atomic commit per probe: `probe: add <vertical>_probe — accepts N pass fixtures, rejects M fail fixtures`
- [ ] **Push & update Coral** — `git push` + append-line to `~/.tsunami/crew/tide/completed.jsonl`

## Hardening pass (parallel with new-probe work)

For each existing probe (9 of them):
- [ ] Read Current's `~/.tsunami/crew/current/attacks/probes/<vertical>.json` — each JSON file is an attack corpus
- [ ] Add each attack as a `fail/` fixture if the probe accepts it (indicates under-gating)
- [ ] Add each attack as a `pass/` fixture if the probe rejects a legit variant (indicates over-gating)
- [ ] Fix the probe until the corpus is 100% on both directions
- [ ] Commit: `probe: harden <vertical>_probe against <attack-name>`

## Known failure modes (don't repeat)

- Do NOT write a probe without fixtures — a probe with no fail/ directory is un-falsifiable
- Do NOT use Qwen or any network call inside the probe — probes are pure-local, deterministic, millisecond-latency
- Do NOT accept "exists" without "parses and wires" — many probes regress by only checking file existence
- Do NOT forget to register in `_PROBES` + `detect_scaffold` — the probe must fire, not just exist

## Bonus long churn infinite 🔁

After the vertical_gap queue is drained:

1. For every `scaffolds/*/*/` that has no corresponding probe, write the probe. Start with the rarest category.
2. Write a **cross-vertical meta-probe** — a probe that accepts a multi-vertical deliverable (web + cli + config) for projects that span concerns.
3. Harden `_probe_common.py` — extract every duplicated helper (JSON parse, package.json sniff, engine-dep check) and replace call sites.
4. Generate synthetic fail-fixtures via adversarial perturbation: take a pass-fixture, mutate one field (rename key, corrupt JSON, drop a file), add to fail/ with the mutation noted.
5. Emit `~/.tsunami/crew/tide/wishlist.jsonl` of vertical gaps you couldn't finish — Coral picks up next round.
6. Repeat.

Log per round to `~/.tsunami/crew/tide/log.jsonl`:
```json
{"ts": "...", "round": N, "action": "new_probe|hardened|fixture_add", "vertical": "...", "pass_count": N, "fail_count": M, "sha": "..."}
```
