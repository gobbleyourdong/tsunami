# Prompt 036 — Party game (Mario Party-style)

**Pitch:** 4 players on a board-game map rolling dice + moving spaces; after each turn, all 4 play a randomly-selected mini-game from a pool; winners of mini-game get coins; coins buy stars; most stars after N turns wins.

**Verdict:** **awkward → expressible with v1 candidates** (revised per note_012 — multiplayer is engine-level, not schema-level)

**Proposed design (sketch):**
- archetypes: `player_1..4`, `board_space_*`, `star_vendor`, `minigame_trigger` (per minigame instance)
- mechanics: `TurnManager` (v1), `BoardMovement` (dice roll + space traversal), `MinigamePool` (random select from N), `EmbeddedMinigame` (v1, note_006 — but different here), `Shop` (star vendor), `WinOnCount` (most stars), `Resource` (v1, coins)

**Missing from v0:**
- **`BoardMovement`** — dice roll + stepwise traversal along a graph of spaces with space-effects (gain/lose coins, +star, mini-event). A specialized turn-based movement mechanic.
- **`MinigamePool`** — pool of N mini-games, randomly select 1 per turn. Different from note_006 `EmbeddedMinigame`: note_006 is triggered-suspend-resume within a single game; MinigamePool is *sequence-of-disjoint-minigames as the primary gameplay*.
- **Multi-player turn ordering** — 4 players take turns; at the mini-game, all 4 play simultaneously (local multiplayer; v2+ per note_005_addendum).

**New pattern surfaced:** **"anthology" games** (Mario Party, WarioWare)
have a fundamentally different shape from games with *one* gameplay
loop. They are a *container* of mini-games + a meta-scoring layer.

This is distinct from note_006 `EmbeddedMinigame`:
- **note_006 `EmbeddedMinigame`:** temporary suspension of main loop for a set-piece; player returns to the main loop.
- **anthology / `MinigamePool`:** the main loop IS "pick a minigame, play it." No underlying loop to return to.

**v1 candidates raised:**
- `BoardMovement` — graph-based stepwise piece movement (niche)
- `MinigamePool` — rotating-selection container for N mini-games (anthology pattern)
- `MultiPlayerTurnOrder` — tied to multiplayer (out-of-v1 per addendum)

**Stall note:** party games are multiplayer-by-nature. Single-player
variant would be a rarity. Out-of-v1 scope for the multiplayer
requirement. The `MinigamePool` concept, however, is single-player-
useable (WarioWare is single-player anthology) and could be worth
flagging. Going to add to observations as note_011.
