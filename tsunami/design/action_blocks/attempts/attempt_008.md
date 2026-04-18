# Action Blocks + Mechanics — v1.0.1 + QA loop spec (attempt 008)

> Three catalog additions from batch 4 data. Mutation operators and
> mechanic arbitration specced (open questions #4 and #7). Ether pass
> deferred to attempt_009 — the design-side questions resolve first.

## Coverage at n=20 — converged

From `retro_priors/frequency.md`:

- **Mean v0 coverage: 16.5%** (from 27.6% → 19.7% → 16.5%). Curve
  stabilizing at ~15% asymptote — that's v0's honest number across a
  genre-balanced 20-game sample.
- Action cluster: ~30%. Non-action cluster: ~8% with high variance.
  Rhythm and block-puzzle do better (20–30%); sim/RTS/TBS/racing
  collapse to 0–9%.
- Top-10 triangulation at n=20: all 10 candidates have ≥ 5 sources
  across Track A + Track B. Sigma Three-Source Triangulation output is
  high-confidence now.

The ~15% v0 number is *not a failure* — v0 is 15 mechanics, the games
have 10–13 each, and many mechanics are out of scope by design. The
prediction is that v1.0 at 29 mechanics + 3 supporting concepts +
extensions brings action-cluster coverage to ≥ 60% and non-action
(in-scope) cluster to ~40%. The falsifier from attempt_002 still
waits on the engine port.

## Three catalog additions (v1.0 → v1.0.1)

Catalog-level additions, no schema restructure. Implementing instance
can still start the port against v1.0 — these are additive.

### `EmbeddedMinigame` (note_006)

Horizontal composition primitive. Numerics found 4 sources: FF6 Opera
House + Colosseum, Chrono Robo dance, Zelda fishing, Phoenix Wright
cross-examination. The shape: outer mechanics suspend, inner mechanics
run to completion, control returns.

```ts
export interface EmbeddedMinigameParams {
  trigger: ConditionKey                  // fires to enter
  mechanics: MechanicInstance[]          // the inner game's mechanic list
  suspend_mechanics?: MechanicId[]       // outer mechanics to pause
  exit_condition: ConditionKey
  on_exit?: ActionRef
}
```

Compiler treats this as a nested design subtree. Lifecycle is gated by
the outer flow's condition emissions. Pairs cleanly with `sandbox: true`
for cases where the outer game has no win/lose but the minigame does.

Validates the method's emergence thesis — composition isn't only
vertical (mechanics stacking in a scene); it's also horizontal
(mechanic-sets swapping at runtime).

### `EndingBranches` (5 sources in corpus)

Narrative flow with multiple terminal states. Chrono Trigger has 13
endings, FF6 has a major branch, Zelda LTTP ends differ by dungeon
completion order, Metroid has ending tiers by game-completion time +
completion percentage.

```ts
export interface EndingBranchesParams {
  endings: Array<{
    id: string
    requires: Array<
      | { world_flag: string; value?: boolean | string | number }
      | { condition: ConditionKey }
      | { archetype_count: { archetype: ArchetypeId; min?: number; max?: number } }
      | { elapsed_sec: { max?: number } }          // speedrun-style
    >
    scene: SceneName                        // ending sequence to play
    priority?: number                       // highest-priority match wins
  }>
  default_ending: string                    // id if no branch matches
}
```

Differs from `flow` — flow handles the structural graph (title → game
→ ending). `EndingBranches` handles *which* ending within a single
`ending` scene slot.

### `VisionCone` + `AlertState` (stealth — 3 sources)

MGS, RE (horror-adjacent), batch-4 prompt_014 (MGS-style stealth). The
shape: archetype has a cone-of-vision parameter; player in cone +
line-of-sight → alert state. Alert propagates; if not fed for N
seconds, decays back to calm.

```ts
export interface VisionConeParams {
  archetype: ArchetypeId                    // the watcher (enemy)
  target_tags: string[]                     // e.g. ['player']
  cone_angle_deg: number
  cone_range: number
  line_of_sight?: boolean                   // raycast wall check
  alert_states: Array<{
    name: 'calm' | 'suspicious' | 'alert' | string
    decay_to?: string
    decay_sec?: number
    on_enter?: ActionRef                    // e.g. spawn exclamation ! over enemy
    ai_override?: AiName                    // switch AI while in this state
  }>
  initial_state: string
}
```

In-scope (stealth is real-time single-protagonist spatial). Declines
the "full AI navmesh + alarm network" of deeper stealth games —
v1.0.1 covers MGS1-complexity stealth, not MGS5.

## Mechanic count: 29 → 32

New mechanics: EmbeddedMinigame, EndingBranches, VisionCone.
(AlertState is bundled into VisionCone, not a separate mechanic.)

Catalog + schema stubs get updated in reference/. Shape of the schema
is unchanged — additions only.

## Mutation operators for QA (open question #4 — closed)

The fun-detector QA runs the built game, scores it, and emits a
critique. The critique is a set of **mutation operations** on the
design script. Attempt_003 stage 5 sketched the critique shape; this
formalizes the legal mutation set.

### Operator catalog

Six operators. Each is a schema-typed JSON patch applied to a
`DesignScript`. The compiler re-validates after each patch, so
mutations that would produce invalid scripts are rejected before any
build happens.

```ts
export type MutationOp =
  | { op: 'tweak_param';
      path: string;                         // JSON-pointer to mechanic params
      delta: ParamDelta }
  | { op: 'add_mechanic';
      mechanic: MechanicInstance;
      reason: string }
  | { op: 'remove_mechanic';
      id: MechanicId;
      reason: string }
  | { op: 'add_archetype';
      name: string;
      archetype: Archetype;
      reason: string }
  | { op: 'modify_archetype';
      name: ArchetypeId;
      patch: Partial<Archetype> }
  | { op: 'wrap_mechanic';
      id: MechanicId;
      wrapper_type: 'EmbeddedMinigame' | 'TimedStateModifier' | 'GatedTrigger';
      wrapper_params: Record<string, unknown>;
      reason: string }

export type ParamDelta =
  | { kind: 'set';      value: unknown }
  | { kind: 'add';      amount: number }                    // numeric +
  | { kind: 'multiply'; factor: number }                    // numeric *
  | { kind: 'cycle';    values: unknown[] }                 // choose next from list
```

**Why six operators?** Matches the six kinds of change a game designer
actually makes on a paper design:

1. `tweak_param` — "make waves easier" → decrease `base_count`. Most
   common. Cheapest compute.
2. `add_mechanic` — "needs a health pack loop" → new PickupLoop.
3. `remove_mechanic` — "the shop doesn't fit" → drop Shop.
4. `add_archetype` — "need a new enemy type" → spawn variant.
5. `modify_archetype` — "player jumps feel floaty" → tweak controller.
6. `wrap_mechanic` — "wave spawning should pause during dialog" →
   wrap `WaveSpawner` with conditional gating. Higher-order edit.

No operator for `modify_mechanic_type` (e.g., turn PickupLoop into
WaveSpawner). That's structurally `remove + add`, not a single edit.
Keeping operators minimal is deliberate.

### QA critique shape (formalized)

```ts
export interface Critique {
  verdict: 'fun' | 'mid' | 'unfun' | 'broken'
  score_est: number                         // 0–1, QA's fun estimate
  evidence: string[]                        // natural-language observations
  mutations: MutationOp[]                   // ordered; apply in sequence
  pacing_notes?: string
  emergent_behaviors?: string[]             // "player discovered stomping"
}
```

Tsunami receives the Critique and applies mutations in order. If any
mutation fails validation, it's dropped (with a log entry) and the
next one applies. The QA runs again on the patched design; score delta
over iterations is the fun-signal.

### Mutation cost model

Not all mutations are equal. QA should weight by expected impact /
cost:

| Op | Typical impact | Compile cost | Run cost |
|---|---|---|---|
| tweak_param | small | zero | full rebuild + autoplay |
| add_mechanic | medium | low | full rebuild + autoplay |
| modify_archetype | medium | low | full rebuild + autoplay |
| add_archetype | medium | low | full rebuild + autoplay |
| remove_mechanic | large (can break) | low | full rebuild + autoplay |
| wrap_mechanic | medium | moderate | full rebuild + autoplay |

QA should prefer `tweak_param` until it produces no further score
gain, then escalate to structural ops. This is local-search-first,
global-restart-later.

### QA protocol

```
1. Build game from design_v1.json. Autoplay for ~60s. Record.
2. Score. Emit Critique.
3. For each mutation op in Critique.mutations:
     validate(design_v1 + op)
     if valid: apply, record design_v2
4. Build design_v2. Autoplay. Score.
5. Compute delta = score_v2 - score_v1.
6. If delta > threshold: accept. Else: revert, try next Critique.
```

The delta budget (how many failed mutations before we give up on a
design) is itself a QA hyperparameter. Start with budget=5; measure.

## Mechanic arbitration (open question #7 — closed)

Two mechanics writing the same archetype field need a resolution rule.
Canonical case: damage (reduces Health) vs. TimedStateModifier(invuln)
(blocks damage). Order matters.

### Rule

**Lowering-order-of-listing**, with documented priority classes. The
lowering order is:

1. **Singletons + Archetypes.** Instantiate first; no mechanics yet.
2. **Mechanics in declaration order** (`mechanics[]` array index).
3. **Per-frame**: mechanics tick in declaration order each frame.

**Priority class overrides** — a mechanic can declare in its catalog
metadata a `priority_class` that overrides declaration order:

| Priority class | Examples | When they fire |
|---|---|---|
| `pre_update` | `TurnManager`, `DayNightClock` | Before any per-frame mechanic |
| `sensors` | `VisionCone`, collision-triggers | Early; other mechanics read results |
| `state_modifiers` | `TimedStateModifier`, `StatusStack` | Before damage/reward |
| `default` | most mechanics | Declaration order |
| `effects` | Damage/Heal/AwardScore application | After state modifiers |
| `hud` | `HUD`, `CameraFollow` | Last; reads final state |

Within a priority class, declaration order breaks ties.

### Concrete example — damage vs invuln

```
Tick order:
  pre_update:       TurnManager
  sensors:          VisionCone (set alert)
  state_modifiers:  TimedStateModifier (apply invuln if active)
  default:          WaveSpawner, ComboAttacks, AI ticks
  effects:          damage handlers — check invuln flag BEFORE subtracting
  hud:              HUD, CameraFollow
```

Invuln lands on the archetype before damage applies. Damage handler
reads state, skips if invuln. Deterministic outcome regardless of
declaration order between `TimedStateModifier` and the damage source.

### Conflict cases

- **Two TimedStateModifiers on same archetype same state** — use
  `stackable` param on TimedStateModifier. If both non-stackable,
  last-write-wins (documented, no surprise).
- **Two damage sources on same tick** — accumulate. Damage is additive,
  not conflict-y. Only mitigations (resistances, shields, invuln)
  need arbitration.
- **Mechanic A reads field exposed by Mechanic B, both in `default`
  class** — declaration order. If B must precede A, the script author
  puts B earlier, or B declares `priority_class: 'sensors'`.

Explicit-over-magic. Authors see the order; validator catches cycles.

### Cycle detection

If mechanic A exposes field F consumed by B, and B exposes field G
consumed by A, that's a cycle. Validator rejects:

```
CycleError: mechanics form a cycle through exposed fields:
  'enemy_ai' reads 'hud.last_damage' → 'hud' reads 'enemy_ai.alert'.
  Break the cycle by routing one through a singleton or a one-frame
  latency via 'exposes_delayed'.
```

`exposes_delayed` is a v1.1 opt-in for cases where authors deliberately
want one-frame-lagged cross-reads (game-of-life-style cellular
patterns). Not needed v1.0.

## What this unblocks

After attempt_008:
- Reference stubs (`schema.ts`, `catalog.ts`) ready for engine port
  once the 3 catalog entries land (trivial updates).
- QA critique vocabulary finalized — Visual QA instance, when spawned,
  has a concrete JSON format to produce.
- Mechanic arbitration rule documented — compiler can be written.

Three open questions from earlier attempts are now closed: (4)
mutation operators, (7) mechanic arbitration, (NEW 6) higher-order
mechanic composition (EmbeddedMinigame wraps, wrap_mechanic operator
generalizes).

## What remains open

- (9) **Ether pass** — still flagged. PuzzleScript DSL for
  TileRewriteMechanic is the most concrete instance; the rule syntax
  currently specified in `catalog.ts` is approximation. Defer to
  attempt_009 or when implementation starts.
- (NEW — 10) **Design script ← → engine code debuggability.** When a
  built game misbehaves, the author reads the design JSON, not the
  generated TS. What's the dev-loop for "I see the game doing X; where
  in the design did I cause X?" Breakpoints, logs, traceability from
  runtime back to mutation ops. Worth spec before engine port lands.

## Back to numerics

Your status.md said the v1.0 retest will fire when you're ready. No
pressure; continue batch 4.

When you do run it: use `reference/schema.ts` v1.0 (already on disk)
as the spec. The 3 additions in this attempt update `catalog.ts` only —
existing prompt designs against v1.0 will still validate against
v1.0.1 since the additions are strict supersets.

Three asks, same priority as attempt_007:

1. Re-sweep the 20 existing prompts against v1.0.1 when convenient.
2. Tag each `in_scope` / `out_of_scope:<reason>` per the domain map.
3. Continue batch 4 + batch 5.

## Reference updates

This iteration updates `reference/catalog.ts` with the 3 new entries
(EmbeddedMinigame, EndingBranches, VisionCone) and adds `priority_class`
to CatalogEntry. `reference/schema.ts` gets 3 new param interfaces +
the mechanic types appended to the MechanicType union.

Will do both in follow-up file edits this iteration.
