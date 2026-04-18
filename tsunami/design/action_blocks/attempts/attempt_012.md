# Action Blocks + Mechanics — note_012 absorption + TileRewrite DSL (attempt 012)

> Compact iteration. Absorb numerics notes 011 (Anthology → v2) and
> 012 (multiplayer correction via operator input). Ether pass on
> TileRewriteMechanic rule DSL — the one catalog entry still marked
> TODO.

## note_012 — multiplayer correction (operator input)

JB: *"re:mario party, remember the system provides. their system
provides."*

Numerics applied this to themselves cleanly (Priors Don't Beat Source
—v8): their `note_005_addendum` "single-session local" assumption was
over-extrapolated from one prompt. The engine runtime handles local
multiplayer routing (input-per-player, split-screen) — it's not a
schema concern.

### Corrected 4th assumption

Replacing `note_005_addendum`'s "single-session local" with:

> **4. Client-local runtime.** The design script describes *what* the
> game does; the engine handles *who* plays (single or multi). Local
> multiplayer is a runtime feature, not a schema concern. Networked /
> server-authoritative multiplayer is out of scope because the
> WebGPU client has no server — but that's about *where the game
> runs*, not *what the schema describes*.

### Impact on v1 domain statement

Revised: *"v1 targets real-time single-protagonist spatial client-
local games. Networked multiplayer requires server infrastructure
beyond the runtime."*

- **Local multiplayer is IN scope.** Mario Party, Smash, split-screen
  racers, couch co-op all become authorable. Engine handles the
  player-count wiring.
- **Networked/MMO remains OUT of scope.** Server-authoritative
  concerns (latency comp, anti-cheat, persistence authority) sit
  outside the WebGPU client.

### Updated out-of-scope patterns

In `reference/catalog.ts`, revising the MMO redirect + dropping the
over-broad "networked multiplayer" match on local-couch-co-op:

```ts
// before:
{ pattern: 'MMO, online multiplayer, networked, matchmaking, server-auth',
  redirect: 'v3+ — requires server architecture. Local split-screen is v2.' }

// after:
{ pattern: 'MMO, online multiplayer, networked, server-authoritative, matchmaking',
  redirect: 'Networked multiplayer requires server infrastructure beyond the WebGPU client. ' +
            'Local multiplayer (split-screen, couch co-op, party games) IS supported — the ' +
            'engine handles input routing. Try "local multiplayer <genre>" instead.' }
```

Match narrows to "server-authoritative / networked / online / MMO"
patterns. Local patterns are no longer declined.

### Mario Party reclassification

- **Was:** `impossible` — multiplayer assumed out-of-scope.
- **Is:** `expressible-with-v1` once `BoardMovement` (new v1 candidate)
  and `MinigamePool` (note_011) land. The multiplayer dimension
  isn't the blocker; the missing mechanics are.

**`BoardMovement`** is a new candidate mechanic for v1.1 (snakes-and-
ladders / Mario Party / any board-game movement). Hold outside
v1.0.3 freeze since it's single-prompt evidence.

## note_011 — Anthology pattern (`MinigamePool`)

Distinct from EmbeddedMinigame (which suspends an outer loop).
Anthology games have no outer loop — the collection IS the game:
WarioWare, Mario Party minigames, Rhythm Tengoku, Mario 64 DS minigame
collection.

Numerics proposed it as **v2 candidate**, not v1. I agree — single-
genre primitive, 3 corpus sources, passes promotion threshold but
doesn't displace v1's top-5. Freeze stands at 36 mechanics.

Documented in catalog.ts as v2 placeholder entry (adding this
iteration).

### Composition insight

note_011 shows a **nested-mechanic** pattern already latent in the
design: `MinigamePool.pool[]` contains full MechanicInstance arrays.
Same shape as `EmbeddedMinigame.mechanics[]`. Both exercise the
**recursive-design-script** capability.

The schema already supports this via `MechanicInstance[]` being usable
in param positions (EmbeddedMinigame does it; MinigamePool would do it
the same way). No schema restructure needed to ever add anthology; it's
an additive catalog entry when v1.5 arrives.

## Ether pass — TileRewriteMechanic rule DSL

This is the one catalog entry still marked `// rule DSL — TODO Ether
pass` in the reference schema. Landing a concrete spec.

### PuzzleScript as the reference (Stephen Lavelle)

PuzzleScript is the canonical minimal tile-rewrite DSL for puzzle
games (sokobond, heroes of sokoban, stephen's sausage roll, etc.).
Rule syntax is:

```
[ LHS ] -> [ RHS ]
```

Where `LHS` and `RHS` are sequences of cells separated by `|`, each
cell listing the tiles present. Prefixes `> < ^ v` are movement
directions; `...` on the RHS means "unchanged."

### Our rule DSL — v1.0.3 spec

```
rule_string    ::= lhs "->" rhs
lhs            ::= cell_pattern ("|" cell_pattern)*
rhs            ::= cell_pattern ("|" cell_pattern)*
cell_pattern   ::= "[" token ("," token)* "]"
                |  "[]"                 // empty cell
token          ::= direction? tile_id
                |  tile_id "*"          // match any state of tile
                |  "..."                // unchanged (RHS only)
                |  "no" tile_id         // absence (LHS only)
direction      ::= ">" | "<" | "^" | "v"
tile_id        ::= identifier           // from GridPlayfield.tiles[]
```

Modifier prefixes before a rule (on their own line or inline):

```
LATE   rule  // run AFTER primary rule set (used for win-conditions)
RANDOM rule  // rule applies stochastically (tile-shuffle puzzles)
```

Multi-row rules use `\n` between rows; all rows must have the same
width:

```
[ Player | no Wall ] -> [ | Player ]    // single-row: push-into-empty
[ > Player | Crate ] -> [ > Player | > Crate ]  // directional push
```

### Our extensions over PuzzleScript

Two additions needed for game-loop integration:

1. **ActionRef effects.** PuzzleScript's `win condition` + `message`
   are narrow. Our rules can attach an `effect: ActionRef` that fires
   on match (award_score, emit condition, play_sound). This wires the
   TileRewrite mechanic into the rest of the mechanics list via the
   standard effect vocabulary.

2. **Tile-state modifiers.** PuzzleScript uses layered tile objects
   (`Crate` vs `CrateOnTarget` as distinct tokens). Our schema allows
   `Crate*` (any state) — same semantic, less boilerplate on the
   LLM side. Compiler expands `*` to the union of state variants.

### Updated example_params for TileRewriteMechanic

Replace the v1.0.2 placeholder with a PuzzleScript-shaped concrete
example:

```json
{
  "grid_ref": "board",
  "rules": [
    { "pattern": "[ > Player | no Wall ]",
      "result":  "[ | > Player ]" },
    { "pattern": "[ > Player | Crate | no Wall ]",
      "result":  "[ | > Player | > Crate ]" },
    { "pattern": "[ > Player | Crate | Goal ]",
      "result":  "[ | > Player | CrateOnGoal ]",
      "effect":  { "kind": "play_sound", "asset": "tile_lock" } },
    { "pattern": "LATE [ Player | Goal ]",
      "result":  "[ Player | Goal ]" }
  ]
}
```

The implementing instance should verify the exact grammar against
PuzzleScript's docs at `https://www.puzzlescript.net/Documentation/
rules.html` before the parser ships. Key details that may differ:

- PuzzleScript uses `OBJECTS` section to declare tiles; we use
  `GridPlayfield.tiles[]`. Equivalent.
- PuzzleScript has `WIN` section; we use `WinOnCount` + a
  corresponding LATE rule that emits the condition. Slightly more
  verbose but uses our standard condition plumbing.
- PuzzleScript's `AGAIN` (re-run rules until no match) is implicit
  here — the compiler runs rules to fixpoint per tick.

## Runtime debuggability spec (open question #10 light-touch)

Since I'm in (B) mode without operator answer, one small spec for
open question #10 before stopping again.

When a built game misbehaves, the author reads the **design JSON**,
not the generated TS. The compiler must preserve traceability:

### Generated-file header

Every compiler-emitted TS file carries a header comment:

```ts
// GENERATED from src/design/game.design.json
// DO NOT EDIT. Edit the design script and re-run `emit_design`.
// Source mechanic: mechanics[1] (id: waves, type: WaveSpawner)
```

The `Source mechanic:` line points at the design path that produced
this file. Enables: built-game error trace → generated file → design
path → author edits design, not TS.

### Runtime mechanic markers

Each lowered mechanic wraps its per-frame callback in a named scope:

```ts
// In compiler output:
scene.onUpdate(dt => {
  // [mechanic: waves, type: WaveSpawner]
  wavesTick(dt)
})
```

Runtime errors logged from these callbacks include the marker, so a
crash message is legible in design-script terms:

```
Error in mechanic 'waves' (WaveSpawner) at src/main.ts:142
  difficulty_ref 'diff' — exposed field 'spawnRateMul' returned undefined
  Check: mechanics[0] (id: diff, type: Difficulty) — is it declared before 'waves'?
```

### Edit-through-design discipline

Tsunami's agent workflow (open question #11): `emit_design` re-runs on
every fix. The generated TS is NEVER edited by hand. Enforcement:
`agent.py`'s `file_edit` tool checks path against a generated-files
list and refuses edits to generated code. Error message directs back
to the design script.

```python
if is_generated_file(path):
    return ToolResult.error(
        f"{path} is generated from a design script. "
        f"Edit the design and re-run emit_design instead."
    )
```

This locks the invariant structurally (sigma Convention Beats
Instruction — v5).

## Reference stub updates

1. `catalog.ts` — narrow the MMO/networked decline pattern (move
   local-couch-co-op out of scope match).
2. `catalog.ts` — update `TileRewriteMechanic` example_params to the
   PuzzleScript-shaped example above.
3. `catalog.ts` — add `MinigamePool` as v2 placeholder with 1-line
   description referencing note_011.
4. `schema.ts` — update ValidationError kinds (if needed — check).

Applying as edits this iteration.

## Asking JB — same question, unchanged

Still (A) / (B) / (C) from attempt_011. Operator input on note_012
was a correction, not a decision on the stop-signal. Default remains
(B) until explicit answer. Numerics is holding; I'm continuing small
additive work within (B) until told otherwise.

**If asked to stop this iteration: everything since attempt_007 is
additive. v1.0 at attempt_007 (schema frozen) + catalog from v1.0.3
is a valid ship point; the corrections in 010–012 are refinements,
not structural.**
