# Prompt 039 — Match-3 puzzle (Bejeweled / Candy Crush-style)

**Pitch:** grid of gems; swap adjacent to make lines of 3+ same color; matched gems disappear; gems above fall down; new gems spawn at top; score by matches; special gems (line-clear, bomb, rainbow) on 4+ or T-shape matches.

**Verdict:** **awkward → expressible with grid + match-rule extension**

**Proposed design (sketch):**
- archetypes: `gem_red/blue/green/yellow/purple/orange`, `special_gem_*`, `grid_cell`
- mechanics: `GridPlayfield` (v1), `GridController` (v1, cursor-style), `MatchRule` (not in v0; similar to TileRewriteMechanic but more specific), `GravityDrop` (gems fall when cells empty), `RandomSpawn` (fill cells at top), `ScoreCombos` ✓, `Difficulty` ✓

**Missing from v0:**
- **`MatchRule`** — find 3+ contiguous same-tag tiles; remove them; grant reward. Specialized pattern detector; simpler than full `TileRewriteMechanic` rewrite rules. A subset.
- **`GravityDrop`** — gems above empty cells fall down by 1 cell until floor or non-empty. Grid-specific post-match action.
- **Special gem spawning rules** — 4-in-a-row → line-clear gem; T-shape → bomb; 5-in-a-row → rainbow. Pattern-triggered archetype spawn.
- **Cascade scoring** — a match triggers gravity, which may form new matches → chain bonus. Event-cascade with depth-tracking.
- **Swap legality check** — swap only if it produces a match (classic rule) OR swap is free (variant).

**Forced workarounds:**
- `TileRewriteMechanic` rules can express Match-3 if rule DSL supports same-tag-across-contiguous-run. Needs the DSL. Once DSL concrete, match-3 is expressible via rule list.
- Cascade via repeated rule application until fixpoint — standard TileRewrite semantics.

**v1 candidates raised:**
- `MatchRule` — as subset of TileRewriteMechanic; may be separate for ergonomics (LLM authorability)
- `GravityDrop` — grid-specific post-rule action
- `CascadeScore` — chain-depth multiplier

**Stall note:** match-3 is ONE of the canonical "emergent cascade"
puzzle genres. Expressible with TileRewriteMechanic if that mechanic
gets a concrete DSL. If the DSL lands as part of grid-mode (v1 top
bundle), match-3 is in.

**Content-multiplier note:** match-3 is a huge commercial genre
(Candy Crush revenue: billions). One match-3 mechanic × N tile sets
× N special-gem rules × N level layouts = infinite games. Another
content-multiplier per note_009.
