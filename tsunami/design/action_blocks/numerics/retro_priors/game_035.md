# Game 035 — Grim Fandango (1998, PC)

**Mechanics present:**
- 3D character-controlled adventure (tank controls over pre-rendered backgrounds) — partial (no tank-controls in v0, RE-style)
- Dialogue trees with character-specific responses — DialogTree (v1)
- Inventory with contextual use ("use X on Y") — Inventory + InventoryCombine (v1)
- Puzzle-gated progression across 4 years — WorldFlags (v1) + NarrativeChapter (v1)
- Multiple locations per year (hub-and-spoke) — RoomGraph (v1)
- Item discovery via conversation (characters give items) — DialogTree action effect
- No combat (one or two action sequences, mostly adventure) — awkward fit; narrative-driven
- Stylized noir art direction — content, not mechanic
- Atmospheric music + voice acting — content
- Act structure (4 years = 4 acts) — NarrativeChapter (v1)
- Unique puzzles per locale (balloon animal, race track betting, etc.) — PuzzleObject (v1) variant per area

**Coverage by v0 catalog:** ~2/11

**v1 candidates from this game:** all already noted (DialogTree,
Inventory, WorldFlags, NarrativeChapter, RoomGraph, PuzzleObject,
InventoryCombine).

**Signature move:** **3D adventure with character movement (as opposed
to cursor-driven P&C).** Grim Fandango modernized LucasArts adventure
by using keyboard to move the character across scenes. Same mechanics
as Monkey Island — only the input surface is different. Confirms:
- Cursor-mode (MonkeyIsland/Myst) and character-mode (GrimFandango/RE)
  are two delivery styles for the SAME narrative/puzzle mechanic set.
- v1's `topdown`/`platformer` controller + DialogTree + HotspotMechanic
  + PuzzleObject covers both.

**Dedupe signal:** 3 narrative/adventure games in corpus now (Monkey
Island, Phoenix Wright, Grim Fandango) + Myst + VN prompt.
Narrative-genre primitive set is stable. Further adventure-genre
samples unlikely to add primitives — deprioritize.
