# Action Blocks + Mechanics — v1.0.3 + catalog freeze (attempt 010)

> Three moves: absorb note_009 (content-multiplier mechanics — big
> reframe), absorb note_005_addendum (4th assumption: single-session-
> local), declare **catalog frozen** pending retest. After v1.0.3, no
> more catalog additions without specific expressibility gap signal
> from the 30-prompt retest.

## note_009 — the content-multiplier insight

Numerics found a subset of mechanics where the content-to-mechanic
ratio is much greater than 1. The mechanic is authored **once**; games
come from **data**. This is a fundamental reframe for the authoring
loop.

The seven content-multiplier mechanics numerics identified:

| Mechanic | Content = | Example games |
|---|---|---|
| RhythmTrack (concretize) | beatmap JSON + audio | Beatmania, DDR, Parappa |
| DialogScript (flesh from DialogTree) | speaker/pose/line/choices | Phoenix Wright, Clannad |
| TileRewriteMechanic (concretize) | tile set + rules + layouts | PuzzleScript, Baba Is You |
| **ProceduralRoomChain** (new v1) | room pool + connection rules | Hades, Isaac, Dead Cells |
| PuzzleObject (grid variant) | per-object state + solve | Myst, The Witness, escape rooms |
| **BulletPattern** (new v1) | pattern parameters | Touhou (thousands of patterns) |
| **RouteMap** (new v1) | node graph + choice weights | Slay the Spire, Monster Train |

Three bolded are **missing from v1.0.2** and should land.

### Why this reframes the method

The LLM's strength is **emitting typed data against a clear schema.**
For content-multiplier mechanics, that's *literally the game.* Tsunami
emitting a rhythm game = emitting a beatmap JSON, with RhythmTrack as
the mechanical shell. The "game" is 90% data, 10% mechanic.

Generative side of emergence: note_007 named composition-of-mechanics
as one emergence source. note_009 names *content-within-mechanic* as
another. Two emergence sources, both valid, both LLM-friendly:

- **Composition emergence**: v1's 33 mechanics × composition rules = N
  genres at low per-game cost.
- **Content emergence**: per-content-multiplier mechanic × K data
  instances = K genre-aligned games at near-zero per-game cost
  *after* the mechanic lands.

Implementing instance should lead with content-multiplier mechanics
where possible — they produce the broadest per-implementation-week
game count.

### Implications for Visual QA

Content-multiplier games need **different fun-metrics** than
combinatorial games:

- **RhythmTrack game** — fun ≈ "does the beatmap match the song?"
  + "is difficulty curve correct?" + "are patterns interesting?"
  QA measures beatmap quality, not mechanic composition.
- **DialogScript game (VN)** — fun ≈ "does the dialogue branching
  produce interesting choices?" + "does the writing land?" QA
  measures narrative coherence.
- **ProceduralRoomChain (roguelite)** — fun ≈ "do runs feel
  distinct?" + "does the difficulty arc over a run work?" QA
  measures run-to-run variance, not single-run play.

When the QA instance spawns, its critique vocabulary should include
**content-critique** operators alongside the mechanical ones from
attempt_008:

```ts
type ContentMutationOp =
  | { op: 'regenerate_content'; mechanic: MechanicId; reason: string }
  | { op: 'tune_content_param'; path: string; delta: ParamDelta }
  | { op: 'swap_content_sample'; mechanic: MechanicId; from: string; to: string }
```

For v1.0.3: flag this; spec formally in the QA-loop attempt when
that instance exists.

## note_005_addendum — 4th assumption

Numerics found v0 has a 4th implicit assumption I missed:

> **Single-session local** — one process, one device, one user.
> No network, no server authority, no multi-device state sync.

Violated by MMOs, online multiplayer, cloud-save, social mobile. This
closes the MMO prompt (026) and any networked-multiplayer out-of-scope
case cleanly.

The v1 domain statement updates to:

> v1 targets **real-time single-protagonist spatial single-session
> games**. Four assumptions; each extension relaxes one.

Decline path for networked multiplayer:

> Networked / online multiplayer is out of v1 scope — requires server
> architecture. For local multiplayer (split-screen, same-device),
> v2 has `local_multiplayer: true` flag. For competitive online,
> use a dedicated engine with server authority.

Add to `OUT_OF_SCOPE_V1` in catalog.ts.

## Three v1 additions (final before freeze)

### `ProceduralRoomChain`

```ts
export interface ProceduralRoomChainParams {
  room_pool: Array<{
    id: string
    layout_source?: string
    weight?: number                          // sampling probability
    min_depth?: number                       // can't appear before run-depth N
    max_depth?: number
    exclusive_with?: string[]                // can't co-appear with these rooms
  }>
  connection_rules: {
    min_rooms_per_run: number
    max_rooms_per_run: number
    branch_factor?: number                   // avg rooms-per-choice-point
    reward_rooms_per_chain?: number
    elite_room_after?: number                // first elite at depth N
  }
  run_lifecycle: {
    on_run_start?: ActionRef
    on_room_complete?: ActionRef
    on_run_complete?: ActionRef
    on_run_fail?: ActionRef
  }
}
```

Covers Hades / Binding of Isaac / Dead Cells / Slay the Spire map
layer. Content-multiplier: one mechanic, N playable runs per room
pool. Pairs with `LoseOnZero` for permadeath.

### `BulletPattern`

```ts
export interface BulletPatternParams {
  emitter_archetype: ArchetypeId            // the boss / enemy that emits
  patterns: Array<{
    name: string
    bullet_archetype: ArchetypeId
    layout: 'line' | 'ring' | 'spiral' | 'spread' | 'aimed' | 'custom'
    layout_params: Record<string, number>   // count, spread_deg, spiral_rate, speed
    duration_ms?: number                    // if omitted, until next pattern
    trigger_condition?: string              // 'boss.health_pct < 0.5'
  }>
  sequence: 'round_robin' | 'weighted' | 'scripted'
  scripted_order?: string[]                 // pattern names in scripted order
}
```

Touhou / Ikaruga / Gradius bullet-hell. Content-multiplier: one
mechanic, hundreds of pattern JSON entries. LLM-ideal.

### `RouteMap`

```ts
export interface RouteMapParams {
  nodes: Array<{
    id: string
    kind: 'battle' | 'elite' | 'event' | 'shop' | 'rest' | 'boss' | 'treasure'
    depth: number                           // column in StS-style map
    scene: SceneName | { ref_mechanic: MechanicId }  // what happens if selected
    reward?: ActionRef
  }>
  edges: Array<{ from: string; to: string }>
  start_nodes: string[]                     // player picks one at depth 0
  boss_node: string                         // forced endpoint
  layout: 'layered_dag' | 'tree' | 'graph'  // visualization hint
}
```

StS / Monster Train / Inscryption meta-progression map. Content-
multiplier: one mechanic, N maps by varying node graph.

Note: RouteMap supports the map-layer of deckbuilders even though
deckbuilding-card-combat remains v2 (that's a BattleSystem variant).
Authors can use RouteMap for any "pick-your-path-through-encounters"
structure — it's not card-specific.

## v1.0.3 catalog count

- v1.0.2: 33 mechanics + 4 v2 placeholders
- v1.0.3: **36 mechanics** (+ ProceduralRoomChain, BulletPattern, RouteMap)
  + 4 v2 placeholders (unchanged)

## Catalog freeze

As of v1.0.3, **no further catalog additions until retest data
provides a specific expressibility gap with a named missing
mechanic**. Rationale:

- Schema has been stable since v1.0 (five iterations of catalog-only
  additions, no structural changes).
- Numerics reports triangulation stable for 3 batches at n=25–30.
- Content-multiplier insight is the last substantive reframe; all
  subsequent observations can land as implementation choices, not
  schema changes.
- Continued iteration without ground-truth data is speculation;
  Sigma "Data Ceiling Before Hparam Sweep" says stop and measure.

What would UN-freeze the catalog: (a) a retest showing a genre fails
with a specific named mechanic missing, (b) the implementing instance
hits a genuine blocker during port, (c) the QA instance surfaces a
content-critique pattern we haven't planned for.

Nothing else adds. No speculative v1.1 additions. Port first.

## Ping #2 — ready for retest

v1.0.3 is the freeze point. 36 mechanics. Schema stable.
Reference stubs (`reference/schema.ts` + `reference/catalog.ts`)
updated this iteration.

Numerics: please re-sweep the 30 existing prompts against v1.0.3
when convenient. The reading order (per your status.md):
1. note_005 + addendum (domain frame, 4 assumptions)
2. note_007 (composability reframe)
3. note_009 (content-multiplier reframe — new)
4. attempt_009 + attempt_010 (my responses)
5. `reference/schema.ts` + `reference/catalog.ts` (canonical spec)

Expected outcomes unchanged from attempt_009 predictions — plus:
- Roguelite/Hades (if prompt fires) → `expressible` with
  ProceduralRoomChain + LoseOnZero-permadeath + Shop
- Shmup/Touhou (if prompt fires) → `expressible` with BulletPattern
  + WaveSpawner + BossPhases + StatusStack
- Deckbuilder-map (if prompt fires, map layer only) → `expressible`
  with RouteMap; card-combat layer → `out_of_scope:v2`

## Implications for the implementing instance

When the retest clears, the recommended port order shifts per
note_009:

1. **Content-multiplier mechanics FIRST** (RhythmTrack concretization,
   DialogTree→DialogScript sequence support, TileRewriteMechanic
   DSL, ProceduralRoomChain, BulletPattern, PuzzleObject) —
   highest game-count payoff per implementation week.
2. **Composability mechanics** (EmbeddedMinigame, Resource, WorldFlags,
   Grid-bundle, DirectionalContact) — multiplier on all other
   mechanics' utility.
3. **Action-core** (WaveSpawner, ScoreCombos, LoseOnZero, etc.) —
   load-bearing for the most-frequent-prompted game shape.
4. **Extensions** (everything else) — per the priority table in
   attempt_009.

This differs from attempt_009's "narrative-subset first" ordering.
note_009's data-first insight outranks the sub-genre-composition
insight from note_008 — content-multiplier is the bigger lever.

Updated roll-out:
- Phase 1 (fastest games-per-week): content-multiplier stack
- Phase 2 (composability multipliers): core schema primitives
- Phase 3 (genre completeness): action + puzzle + adventure cores

## Open questions

- (9) **Ether pass** — still flagged. Highest-value targets: PuzzleScript
  DSL for TileRewriteMechanic; Touhou-style bullet pattern scripts
  (BulletML?) for BulletPattern; StS map format for RouteMap;
  established VN engine script format for DialogScript. Implementing
  instance will naturally pull these in when writing the mechanics.
- (10) Runtime debuggability — attempt_011.
- (11) Dev-loop round-trip from built game → design edit (locked
  generated files; edit-through-design-only discipline) — attempt_011.

## Signal to stop iterating in design

One honest read: if the retest shows v1.0.3 clears the 60% gate AND
numerics has stable triangulation AND no new structural gaps surface,
my job as the design instance is mostly done. The remaining
attempts (011+) are polish and Ether-pass content that doesn't
block the engine port. The numerics instance has earned a similar
honest read: triangulation stable for 3 batches; signal is high.

If JB wants to promote v1.0.3 → v1.0 final and start the engine port,
that's a valid call on the current data. Both instances should read
the retest output and decide together. Sigma Coupled Observation at
the stop moment.
