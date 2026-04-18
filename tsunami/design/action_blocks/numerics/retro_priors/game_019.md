# Game 019 — Beatmania (1997, arcade)

**Mechanics present:**
- Notes scrolling from top to hit line — ✅ `RhythmTrack` (v0 — finally exercised from corpus!)
- 5-key + turntable input — specific controller (archetype's input binding extension)
- Scoring by hit-accuracy (Perfect / Great / Good / Bad / Miss) — timing-window grading; `HitGrade` spec on RhythmTrack
- Combo counter (unbroken streak) — event-commit Streak noted in prompt_009
- Visual feedback per hit (color/effect flash) — `OnHitVFX` on RhythmTrack params
- Life bar depletes on misses, regen on hits — standard Health + custom damage/heal hooks
- Song selection screen — menu/scene variant
- Difficulty variants per song (Normal/Hyper/Another) — asset variant + metadata; `SongDifficultyVariant` spec
- Clear threshold (life bar above X% at song end → pass) — `WinOnThreshold` — condition on a field not reaching zero
- Score-based unlocks — PostRunUnlock (noted in RE)

**Coverage by v0 catalog:** ~1–2/10 (RhythmTrack exercised, needs fleshing per prompt_009)

**v1 candidates from this game:**
- Flesh out `RhythmTrack` params: `hit_grades: [perfect: 30ms, great: 60ms, good: 120ms, miss: >120ms]`, `on_hit` / `on_miss` ActionRef hooks, `scroll_speed`
- `HitCombo` — event-commit Streak distinct from `ScoreCombos` (time-window)
- `SongLibrary` — indexed audio+beatmap pairs; menu selection
- `WinOnThreshold` — generalized win condition on a field value

**Signature move:** the beatmap as content. A single RhythmTrack mechanic plays arbitrarily many songs by varying beatmap data. The game's content volume scales with song count, not mechanic count. Directly validates the design-script premise: small mechanic catalog × content = large game space.

**Method validation:** Beatmania is one of the cleanest fits for "define the mechanic once, generate N games with different data." This is the kind of game the Tsunami agent can author profitably — prompt "make a rhythm game for this song" → emit RhythmTrack with beatmap → compile → play. The loop closes tightly.
