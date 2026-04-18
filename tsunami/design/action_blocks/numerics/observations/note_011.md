# Observation 011 — Anthology pattern (distinct from EmbeddedMinigame)

**Sources:** prompt_036 Mario Party, prompt_038 WarioWare, game_036
Shenmue (arcade machines as full mini-games). 3 sources — promotion
threshold met.

**Claim:** some games are **collections of disjoint mini-games**
rather than a single gameplay loop. The player's progression IS the
sequence of mini-games. Distinct from note_006 `EmbeddedMinigame`:

| Aspect | `EmbeddedMinigame` (note_006) | Anthology (this note) |
|---|---|---|
| Outer game | primary game loop exists | no primary loop — anthology IS the loop |
| Player path | plays outer → enters inner → returns | plays item 1 → item 2 → item N |
| Frequency | occasional (set-pieces) | constant (every turn / every N seconds) |
| Meta-layer | story/narrative progress | score / lives / unlocks |
| Example | Phoenix Wright cross-ex; FF6 opera | Mario Party, WarioWare, Rhythm Tengoku, Mario 64 DS mini-game collection |

**Proposed primitive:** `MinigamePool`

```ts
interface MinigamePoolParams {
  pool: MinigameDef[]       // array of inline mini-game definitions
  select: 'random' | 'sequential' | 'weighted'
  auto_advance: boolean     // WarioWare: true; Mario Party: false (turn-based)
  advance_on: 'complete' | 'timeout' | 'player_choice'
  timeout_sec?: number      // for timed anthology (WarioWare: ~5)
  on_pool_exhausted: ActionRef  // loop / grant reward / end
  meta_state: ComponentSpec[]   // score/lives preserved across mini-games
}

interface MinigameDef {
  id: string
  archetypes: Record<string, Archetype>
  mechanics: MechanicInstance[]
  win_condition: ConditionKey
  lose_condition: ConditionKey
}
```

**Why this matters:** the anthology pattern is disproportionately
valuable for the **agentic authoring loop**:

- Tsunami can emit 20 small mini-games more reliably than 1 large
  coherent game — each mini-game fits in ~10–20 lines of design
  script.
- Mini-games test a single mechanic idea in isolation — perfect for
  QA feedback (does this one mini-game feel fun?).
- A single MinigamePool emission = 20 games worth of content.

**Cost:** implementation is nested design-script support. The schema
allows `mechanics: MechanicInstance[]` inside `MinigameDef` — same
shape as the top-level. Nesting is recursive, but bounded (each
mini-game is self-contained, no further nesting needed for v1).

**v1/v2 placement:** v2 candidate. Cost-benefit is good (small
primitive, broad applicability) but less critical than top-5. If v1
top-5 ships without issue, v1.5 could add MinigamePool + EmbeddedMinigame
as the "nested-mechanic" bundle.

**Composition notes:**
- Anthology × content-multiplier (note_009): WarioWare is
  MinigamePool × 200 mini-games. Each mini-game might itself be a
  content-multiplier mechanic (a RhythmTrack minigame with one
  beatmap).
- Anthology × Difficulty: `select` weighting by difficulty over time.
- Anthology × EmbeddedMinigame: an anthology game can have a
  story-wrapper outer loop (Mario Party's board × minigames).

**Cross-reference:** adds to the list of "meta-patterns" after
EmbeddedMinigame (note_006) and content-multiplier (note_009). The
design-track's compiler will need to handle mechanic composition at
multiple nesting levels.
