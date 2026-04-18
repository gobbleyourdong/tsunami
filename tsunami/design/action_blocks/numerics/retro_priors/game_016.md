# Game 016 — Myst (1993, PC/Mac)

**Mechanics present:**
- Pre-rendered static scenes with click navigation — **not in v0** (hotspot + scene-graph navigation)
- No character; player is a disembodied eye — no player archetype
- Environmental puzzles (gears, levers, dials, patterns) — **not in v0** (`PuzzleObject` — interactable with mutable state)
- Discover-and-operate mechanical machines — state-machine variations on puzzles
- Linking books (teleport to other age) — partial (scene transition, but narrative-scripted)
- No inventory in the conventional sense — state-tracked discoveries
- Journals / found documents — **not in v0** (LoreEntry — noted in RE)
- Ambient sound + music cues — partial (`AudioEngine` exists; spatial trigger gap)
- No combat, no death, no timer — fully sandbox
- Multiple endings — **not in v0** (EndingBranches)
- Age-to-age narrative progression gated on puzzle solutions — `WorldFlags` gated scene transitions

**Coverage by v0 catalog:** ~0/10

**v1 candidates from this game:**
- `PuzzleObject` — interactable world object with mutable state + solve condition (gear angle, lever position)
- `HotspotMechanic` (already noted from Monkey Island)
- `LoreEntry` (already noted from RE)
- `EndingBranches` (already noted)
- `ClickNavigation` — scene-to-scene via click zones, not via player-walking (overlap with adventure)

**Signature move:** puzzles as environmental objects. The genre predates the point-and-click adventure verb system — Myst puzzles are all direct manipulation of scene geometry. This is closer to "VR mechanics puzzles" than LucasArts adventure. The `PuzzleObject` primitive is the right shape and would also serve escape rooms, mystery games, and VR titles.

**Signature absence:** almost no narrative agency. The game is "solve puzzles to progress." This is achievable in v0 with hotspot + worldflags + scene transitions — Myst is easier to express than Monkey Island despite feeling more "premium."
