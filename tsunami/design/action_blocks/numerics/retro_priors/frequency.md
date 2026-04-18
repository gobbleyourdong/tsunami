# Retro priors — mechanic frequency

> Aggregate over `game_NNN.md`. Rebuilt every ~10 games.
> Last rebuild: after game_030. Source count: **30 games**.

## Corpus (n=30)

Batch 1: 01 SMB, 02 Tetris, 03 Pac-Man, 04 SF2, 05 Zelda LTTP.
Batch 2: 06 Galaga, 07 Ms.Pac-Man, 08 SimCity 2000, 09 Metroid, 10 Chrono.
Batch 3: 11 Monkey Island, 12 StarCraft, 13 MGS, 14 RE, 15 Sims.
Batch 4: 16 Myst, 17 Civ II, 18 Gran Turismo, 19 Beatmania, 20 FF6.
Batch 5: 21 NetHack, 22 GTA III, 23 Silent Hill, 24 Lemmings, 25 MK64.
Batch 6: 26 NBA Jam, 27 Phoenix Wright, 28 DDR, 29 Oregon Trail, 30 Ikaruga.

## v0 coverage (n=30)

**Mean: 16.5%** (stable asymptote, mild uptick from 15.3% at n=25 as
batch 6 added action/rhythm games that score higher).

By cluster:
- Arcade + shmup + rhythm + kart + skater: 30% ± 8
- Action-platformer + metroidvania: 28% ± 2
- Action-adventure: 31%
- Fighting: 27%
- Block / rhythm puzzle: 20% ± 10
- Real-time continuous puzzle (Lemmings): 9%
- Graphic/point-click puzzle: 0–19%
- JRPG: 10.5% ± 3
- Stealth / survival horror / psych horror: 7–13%
- Sim (city/life/journey): 0–25% (Oregon Trail bumps it)
- RTS / TBS / racing-sim / deep-roguelike / CRPG / MMO / team-sports: 0–8%

Hard separation persists: action ≥ 25%, narrative/sim/strategy < 20%.

## Mechanic frequency at n=30 (top 20)

| Freq | Mechanic |
|---|---|
| 30 | HUD |
| 26 | Lose-condition |
| 21 | **LevelSequence** (NEW) |
| 18 | Pickup |
| 17 | **DialogTree** (NEW) — up from 14 |
| 16 | **RoomGraph** (NEW) |
| 15 | **GridPlayfield** (NEW) |
| 14 | **DirectionalContact** (NEW) |
| 13 | **CameraPresets / CameraFollow** (NEW) |
| 13 | **InventoryCombine / slot-limit** (NEW) |
| 12 | Difficulty |
| 12 | **Resource (generic)** (NEW) |
| 11 | **TimedStateModifier** (NEW) |
| 10 | **WorldFlags** (NEW) |
| 10 | WaveSpawner |
| 10 | **ItemUse + GatedTrigger** (NEW) |
| 9 | **Shop** (NEW) |
| 9 | ComboAttacks |
| 9 | **PlatformerController** (NEW) |
| 8 | **TurnManager + PhaseScheduler** (NEW) |

## Mechanics in 3+ games absent from v0

**Tier-1 (≥ 8 sources — confident v1):**
LevelSequence (21), DialogTree (17), RoomGraph (16), GridPlayfield (15),
DirectionalContact (14), CameraPresets (13), InventoryCombine (13),
Resource (12), TimedStateModifier (11), WorldFlags (10), ItemUse+Gated (10),
Shop (9), PlatformerController (9).

**Tier-2 (5–7 sources — strong v1):**
TurnManager (8), EndingBranches (7), EmbeddedMinigame (7),
NarrativeChapter (6), HotspotMechanic (6), PathFollower (6),
SandboxMode (6), ArchetypeControllerSwap (6).

**Tier-3 (3–4 sources — v1/v2 candidate):**
VisionCone/AlertState (5), PuzzleObject (5), BattleSystem (5),
RandomEvent (5), NewGamePlus (5), StatusStack (4), RelationshipGraph (4),
ParallelWorldLayer (4), MissionGraph (4), FastTravel (4), TechGraph (3),
Calendar (3), AuthorRunMode (3).

## v0 mechanics corpus-validated

HUD (30/30), Difficulty (12), WaveSpawner (10), ComboAttacks (9),
ScoreCombos/CheckpointProgression/LockAndKey/BossPhases (6 each),
StateMachineMechanic (6), PickupLoop (18 as generalized).

## v0 mechanics thin but retained

DayNightClock (2 — Oregon Trail calendar close), RhythmTrack (3 — Beatmania,
DDR, Phoenix Wright cross-examination partial), TileRewriteMechanic (1 —
Tetris implicit; flagged for concretization).

## Sampling bias audit (n=30)

Distribution now much healthier:
- Arcade/action cluster: 10/30 (33%) — arcade + shmup + platformer + adventure + fighter + skater + kart + NBA Jam
- Action-adventure + metroidvania: 2/30 (7%)
- Puzzle cluster (block/graphic/real-time/sim/adventure): 5/30 (17%)
- JRPG + CRPG: 2/30 (7%) — Chrono + FF6
- Stealth + horror: 2/30 (7%)
- Sim (city/life/journey): 3/30 (10%) — SimCity + Sims + Oregon Trail
- RTS + TBS + racing sim + deep roguelike: 4/30 (13%)
- Narrative (adventure/VN): 2/30 (7%) — Monkey Island + Phoenix Wright

Remaining under-represented:
- Edutainment beyond Oregon Trail (Math Blaster, Carmen Sandiego)
- Competitive fighting beyond SF2 (Smash, Tekken, VF)
- Shmup depth beyond Galaga/Ikaruga (Gradius, R-Type)
- Puzzle-platformer (Braid wasn't in corpus; only prompt)
- Classic CRPG beyond BG-prompt (Ultima, Wizardry)
- Horror beyond RE/SH (Fatal Frame, Clock Tower)
- Flight sim (X-Wing, Wing Commander)
- Dungeon keeper / god game (Dungeon Keeper, Black & White)
- Arcade racing beyond MK64 (Sega Rally, Daytona)
- Classic adventure beyond Monkey Island (King's Quest, Space Quest, Grim Fandango)

Many still to hit, but the SIGNAL quality is already high: top-20
candidates all have ≥ 5 sources across both tracks, frequency ranks
stable across last 3 batches.

**Next batch plan:** Braid, Gradius, Black & White, Daytona, Grim
Fandango, plus prompts on flight sim, arcade racing-beyond-MK64,
shmup-R-Type, god game, competitive fighter beyond-SF2.
