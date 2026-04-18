# Action Blocks + Mechanics — stop-signal + handoff package (attempt 011)

> Not more design. This attempt acknowledges the diminishing-returns
> signal from both tracks, packages the implementation handoff, and
> flags the decision point to JB.

## Mirror the numerics stop-signal

`observations/note_010` names it plainly: the numerics sweep has
reached the Data Ceiling. v1 top-5 stable since n=20, top-13 stable
since n=25, impossible-set stable since batch 6. Each batch adds <1
structural observation.

**My own read of diminishing returns on the design side:**

| Attempt | Structural movement | Additions |
|---|---|---|
| 001 | Initial method shape | full new |
| 002 | Confirmation-bias audit + 15 mechanics | major |
| 003 | WaveSpawner end-to-end trace | major |
| 004 | 6 structural schema changes (grid, tree-flow, directional, singleton, exposes, shape) | **major** |
| 005 | 2 adds (Resource, TurnManager) + flagged v0.3 items | minor |
| 006 | Directional contact + 7 mechanics (Shop, UtilityAI, DialogTree...) | moderate |
| 007 | 3-assumption frame (note_005 adoption) + 2 adds (CameraFollow, StatusStack) + v1.0 declaration | moderate |
| 008 | Mutation operators + arbitration rules + 3 adds | moderate |
| 009 | PuzzleObject + 4 v2 placeholders + prompt scaffold | moderate |
| 010 | 3 content-multiplier mechanics + 4th assumption + **freeze** | moderate |

Last 6 attempts have been catalog-only additions. Schema has been
stable since v1.0 (attempt_007). No structural changes in 5
iterations. By the same Data Ceiling logic numerics applied to
itself, **the design track has also pinned.**

## Decision point for JB

Three options, mirroring numerics note_010:

**(A) Stop both instances. Start engine port.**
- Design at v1.0.3 frozen. 36 mechanics + 4 v2 placeholders.
- Reference stubs (`reference/schema.ts`, `reference/catalog.ts`)
  and prompt scaffold (`tsunami/context/design_script.md`) canonical.
- Spawn an implementing instance with the handoff package below.
- Numerics pivots to: support, retest when compiler lands, edge-case
  coverage continues at reduced cadence.

**(B) Continue both instances with narrower scope.**
- Numerics: option B — compositional depth on already-covered genres
  (cross-mechanic audits per Sigma Three-Source Triangulation).
- Me: Ether pass (PuzzleScript DSL grammar, Godot signals, Bevy
  plugin ordering, Inform 7 decline phrasing), three example design
  scripts for the prompt scaffold, runtime-debuggability spec.
- Useful but not critical. Polish layer.

**(C) Stop numerics, keep me in support mode for the implementer.**
- Numerics: pause the 10-min cron after the final retest delta data.
- Me: no more attempts_NNN. Spec individual mechanics as the
  implementing instance requests, validate their compiler output,
  cross-audit their tests.

**My recommendation:** (A) or (C). (A) lets JB run implementation
through Tsunami-itself or spawn a dedicated implementer instance;
(C) keeps me on call. Either way, stop generating design attempts.

## Why stopping is the right move

- **Sigma "Struggle as Signal"**: the design track hasn't struggled
  for 3+ iterations. Continuing produces catalog additions that
  aren't load-bearing.
- **Sigma "Data Ceiling Before Hparam Sweep"**: we're tuning
  parameter-level design before the substrate (actual compiled
  games) has produced any data. Build it, then iterate.
- **Falsifier not yet testable**: attempt_002's falsifier — "does
  Tsunami-with-schema produce more runnable builds than Tsunami-
  with-freehand-TS?" — cannot fire until the engine port lands. No
  more design refinement validates that question.

## Handoff package — self-contained for implementing instance

Everything an implementing instance needs to take v1.0.3 to code:

### Files they inherit

1. `reference/schema.ts` (~500 lines, v1.0.3) — port to
   `ark/scaffolds/engine/src/design/schema.ts`.
2. `reference/catalog.ts` (~550 lines, v1.0.3) — port to
   `ark/scaffolds/engine/src/design/catalog.ts`.
3. `tsunami/context/design_script.md` (already in place) — the
   Tsunami-facing prompt scaffold. Will be loaded by `agent.py`
   replacing the prose dump at `agent.py:2696-2716`.
4. `tsunami/context/examples/*.json` (to-be-written this iteration)
   — three example design scripts for the prompt's nearest-match
   priming.

### Implementation order (per attempt_010 revision)

**Phase 1 — content-multiplier mechanics** (highest games-per-week
payoff per note_009):

```
engine/src/design/mechanics/
├── rhythm_track.ts           (concretize, content = beatmap JSON)
├── dialog_tree.ts            (support DialogScript sequence pattern)
├── tile_rewrite.ts           (concretize rule DSL — see Ether pass below)
├── procedural_room_chain.ts  (run-based room sequencing)
├── bullet_pattern.ts         (parametric emitter)
├── puzzle_object.ts          (mutable state transitions)
└── route_map.ts              (StS meta-progression)
```

**Phase 2 — composability multipliers** (note_007 top-5 minus already-
covered): `EmbeddedMinigame`, `WorldFlags` (singleton kind), Grid
bundle (`GridPlayfield`, `GridController`, `FallingPieceMechanic`,
`LineClearMechanic`, `TurnManager`).

**Phase 3 — action core** (load-bearing for most prompts):
`WaveSpawner`, `Difficulty`, `HUD`, `LoseOnZero`, `WinOnCount`,
`PickupLoop`, `ScoreCombos`, `CheckpointProgression`, `LockAndKey`,
`CameraFollow`, `TimedStateModifier`, `LevelSequence`, `RoomGraph`.

**Phase 4 — extensions**: `BossPhases`, `ComboAttacks`, `AttackFrames`,
`Shop`, `ItemUse`, `GatedTrigger`, `StatusStack`, `StateMachineMechanic`,
`UtilityAI`, `VisionCone`, `HotspotMechanic`, `InventoryCombine`,
`PointerController`, `EndingBranches`.

### Test strategy

From attempts 002, 003, 008:

1. **Schema validation** — 5 known-good scripts parse, 5 adversarial
   malformed produce expected error classes (the 8 error kinds in
   `schema.ts` ValidationError).
2. **One end-to-end game per shape** — arena shooter (action), sokoban
   (grid-puzzle), monkey-island-lite (narrative-adjacent). All three
   have example scripts landing this iteration.
3. **Mechanic arbitration** — damage vs invuln test (attempt_008):
   `TimedStateModifier('invuln')` in `state_modifiers` class fires
   before damage in `effects` class regardless of declaration order.
4. **Cycle detection** — construct a cycle through `exposes` fields;
   compiler should reject with CycleError.
5. **Content-multiplier** — emit N beatmaps for one RhythmTrack
   mechanic, verify N distinct games build from one mechanic
   instantiation.

### Tsunami integration checklist

1. In `ark/tsunami/agent.py`, replace the prose dump at lines 2696–2716
   with a loader for `tsunami/context/design_script.md` when
   `_is_engine_project` returns true.
2. Add `tools/emit_design.py` wrapping the compiler; signature matches
   the scaffolded tool contract in the design-script doc.
3. Update `error_fixer.py` with patterns for the 8 validator error
   kinds from schema.ts `ValidationError`.
4. Route game-project detection through `isOutOfScopeV1(prompt)` in
   catalog.ts before scaffolding — declined prompts get the redirect
   message, not a broken game attempt.

### Promotion gate (from attempt_007, refined)

- Schema + validator port: 5/5 known-good scripts validate, 5/5
  malformed error with correct kind.
- Three end-to-end games build + autoplay for 60s without crash.
- Numerics re-sweep: ≥ 60% expressible-or-caveated on in-scope
  prompts.
- Tsunami one-shot arena-shooter emission: ≥ 50% valid design over
  N=20.

All four = v1.0 shipped. Fewer = v1.1 needed before ship.

## Light Ether pass — references only

Deferred from attempts 007/008/009. Not doing deep web fetches this
iteration, but listing concrete sources the implementing instance
should pull:

- **PuzzleScript rule syntax** for `TileRewriteMechanic` — the rule-
  rewrite grammar `pattern → result` needs the real syntax. Source:
  `https://www.puzzlescript.net/Documentation/documentation.html`
  (section: "Rules"). Our current placeholder `[player][box][empty] →
  [empty][player][box]` is close but not exact. Implementing instance
  should read + port.
- **BulletML** for `BulletPattern` — a real XML-ish DSL for Touhou-
  style bullet scripting exists. `http://www.asahi-net.or.jp/~cs8k-cyu/bulletml/`
  (ABA Games). Compare our `patterns[].layout` enum against their
  `<action>` + `<fire>` + `<direction>` primitives; our minimal enum
  covers the common cases but BulletML is the superset they should
  know about.
- **Godot scene/signal model** for mechanic `exposes` / consume
  patterns — Godot's `signal` + `connect(...)` is the canonical
  reference for cross-node messaging. My `exposes` → HUD consumer
  pattern is a loose Godot-signal echo; implementing instance should
  check whether Godot's patterns suggest any gotchas I missed.
- **Bevy plugin `.add_systems(...)`** for priority-class arbitration —
  Bevy's system-set ordering labels are more expressive than
  `priority_class`. Implementing instance should evaluate whether to
  adopt Bevy's terminology before shipping the naming publicly.
- **Inform 7** for decline-message calibration — if authors prompt
  with "text adventure," we redirect them to Inform. Implementing
  instance should confirm Inform is still the best redirect vs Twine
  (Twine is more popular but less IF-shaped).

None block the port. All useful during polish.

## Open questions — final state

| # | Question | Status |
|---|---|---|
| 1 | Parameter curves as first-class blocks | closed (Difficulty handles) |
| 2 | Procedural layout mechanics | closed (TileRewrite + tilemap_gen) |
| 3 | Asset references | deferred v1.1 |
| 4 | Mutation operators for QA | closed (attempt_008) |
| 5 | Cross-mechanic dependencies | closed (requires + topo sort) |
| 6 | Higher-order mechanic composition | closed (EmbeddedMinigame) |
| 7 | Mechanic arbitration | closed (priority_class) |
| 8 | Cross-schema refs (BattleSystem) | flagged v2 |
| 9 | Ether pass | references noted; deep read deferred to implementer |
| 10 | Runtime debuggability | flagged for attempt_012 if B is chosen |
| 11 | Dev-loop round-trip (edit-through-design) | implementer's concern |

## Asking JB directly

Pick one:
- **(A)** Stop both instances. Start engine port. Ready now.
- **(B)** Continue both narrower scope (my Ether + runtime debuggability;
  numerics compositional audit).
- **(C)** Stop numerics, keep me in support mode for the implementer.

If no answer, the loop fires again in 10 min and I'll default to (B) —
writing the three example design scripts inline and beginning a light
Ether pass. But (A) is the honest "we're done" call.
