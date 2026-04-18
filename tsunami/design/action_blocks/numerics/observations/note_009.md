# Observation 009 — Content-multiplier mechanics

**Sources:** game_019 Beatmania, game_028 DDR, game_027 Phoenix Wright,
game_016 Myst, prompt_028 western CRPG (dialogue-heavy), prompt_009
Rhythm — 6+ games where one well-specified mechanic plays arbitrarily
many games by swapping content.

**Claim:** a subset of mechanics have a **content-to-mechanic ratio** much
greater than 1 — the mechanic is authored once; gameplay comes from
data. These are the highest-leverage picks for the agentic authoring
loop.

**Content-multiplier mechanics identified:**

| Mechanic | Content type | Example games |
|---|---|---|
| `RhythmTrack` (v0, concretize) | beatmap JSON + audio file | Beatmania, DDR, Parappa, Rhythm Tengoku |
| `DialogScript` (v1, fleshed from DialogTree) | sequence of speaker/pose/line/choices | Phoenix Wright, Clannad, Hatoful Boyfriend |
| `TileRewriteMechanic` (v0, concretize) | tile set + rule list + level layouts | PuzzleScript output, Sokoban, Baba Is You |
| `ProceduralRoomChain` (v1, roguelite) | room pool + connection rules | Hades, Binding of Isaac, Dead Cells |
| `PuzzleObject` grid (v1, Myst-style) | per-object puzzle state + solve condition | Myst, The Witness (partial), room-escape |
| `BulletPattern` (v1, shmup) | pattern parameters | Touhou (thousands of bullet patterns) |
| `RouteMap` (v1, deckbuilder) | node graph + choice weights | StS, Monster Train, Inscryption |

**Implication:** Tsunami emitting a design script for a rhythm game
sets `RhythmTrack` + one audio file reference + one beatmap JSON. The
"game" is 90% data, 10% mechanic. The LLM's job reduces to:
1. Pick the content-multiplier mechanic for the genre.
2. Emit valid content data (beatmap / dialogue tree / tile rules).
3. Wire minimal surrounding mechanics (HUD, Difficulty, scoring).

Relative to freehand-TS authoring, content-multiplier mechanics are
where the schema-first approach wins hardest — because generating
typed data against a clear schema is an LLM strength.

**v1 priority adjustment:** mechanics from this table should lead
v1 implementation regardless of raw frequency, because each one
multiplies the per-mechanic game count.

**Composition with existing observations:**
- note_006 (EmbeddedMinigame) × content-multiplier = mini-rhythm-sections
  inside RPGs (FF6 opera, Crypt of the NecroDancer)
- note_007 (emergence thesis) × content-multiplier = the *generative*
  end of emergence: instead of novel compositions of existing
  mechanics, you get novel content within a fixed mechanic.

**Authoring-loop implication:** if Tsunami wants to "make 100 games,"
the cheapest path is 3 content-multiplier mechanics × 100 content
instances each = 300 games. Mechanic-combinatorial games are expensive
per unit; content-multiplier games are near-free per unit after the
mechanic lands.

**Falsifier:** if content-multiplier mechanics don't produce broader
coverage per implementation cost than combinatorial mechanics (measured
by: games-per-v1-week after implementation), the framing is wrong and
v1 priorities should revert to pure frequency ranking.
