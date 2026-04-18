# Game 028 — Dance Dance Revolution (1998, arcade)

**Mechanics present:**
- Arrows scroll up/down the lanes (4 lanes: up/down/left/right) — ✅ RhythmTrack (v0, concretize)
- Step on arrow pads in time with music — physical input → `action_pattern` mapping
- Hit grades (Perfect/Great/Good/Boo/Miss) — confirmed RhythmTrack hit_grades (prompt_009)
- Combo counter (unbroken streak) — ✅ HitCombo (noted)
- Life bar (too many misses = fail) — Health + LoseOnZero variant ✓
- Clear threshold (life bar ≥ X% at end = pass) — `WinOnThreshold` (noted)
- Song select screen with difficulty variants — SongLibrary + SongDifficultyVariant (noted)
- Freeze arrows (hold step) — `HoldNote` variant on RhythmTrack
- Jump arrows (two arrows at once) — `MultiNote` variant
- Score board + ranking — leaderboard (server/local save gap)
- Dance camera (video BG synced to beat) — audio/video sync

**Coverage by v0 catalog:** ~2/11

**v1 candidates from this game:**
- RhythmTrack concretization (from prompt_009): `hit_grades`, `on_hit` / `on_miss` hooks, `scroll_speed`, `lane_count`, `note_variants: ['tap', 'hold', 'multi']`
- HitCombo (event-commit streak, distinct from ScoreCombos)
- SongLibrary (indexed audio + beatmap pairs)
- WinOnThreshold — generalize win condition to "field ≥ threshold" at flow moment

**Signature move:** physical-input mapping on a simple rule. DDR is one rule ("step on arrow when it's at the top") applied to thousands of songs. The game's longevity comes from content (song library + difficulty variants), not mechanic depth. Confirms for the 2nd time (after Beatmania) that RhythmTrack is a *content-multiplier* primitive — one mechanic, infinite games.

**Method implication:** for the design-script method, content-multiplier mechanics are gold. They're the cleanest "Tsunami writes once, plays forever" primitives. v1 should:
1. Concretize RhythmTrack (it's been flagged twice from the corpus)
2. Identify other content-multiplier candidates: VisualNovel (one DialogScript × N lines), TileRewriteMechanic (one rule-DSL × N puzzles), RoguelitechainedRooms (one generator × N seeds).

Content-multiplier mechanics are disproportionately valuable for the agentic authoring loop — one good emission covers many playable games.
