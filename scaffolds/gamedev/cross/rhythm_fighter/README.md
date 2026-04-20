# Rhythm Fighter — Cross-Genre Canary #3

> **Role**: third architecture-correctness gate for the gamedev framework. Paralleling `magic_hoops/` (sports+fighting+RPG) and `ninja_garden/` (sandbox+action+stealth), this scaffold proves the abstractions also handle **fighting + rhythm** — specifically the timing-coupling axis where two mechanics (RhythmTrack + AttackFrames) must coordinate on a shared beat clock.
>
> If this scaffold compiles + tests clean **without adding any new mechanic types**, the framework has passed its third cross-genre composition test (and the first one that tests mechanic-to-mechanic time-coordination).

## Concept

Street Fighter II × PaRappa the Rapper × Gitaroo Man:
- 1v1 fighting on a 2D arena (like SF2) — HP bars, combo strings, best-of-3 rounds
- Move timing expressed in **beat-fractions** instead of game-frames (like PaRappa's rhythm lane)
- On-beat hits deal **1.5× damage**, off-beat hits deal **0.5×** — the BGM drives gameplay
- Rhythm-bonus status stacks on consecutive on-beat hits (cap 3)

## What this proves

Every mechanic wired in `src/scenes/Match.ts` already exists in `@engine/mechanics`:

| Heritage | Mechanics |
|---|---|
| Fighting (SF2) | `ComboAttacks`, `AttackFrames`, `WinOnCount` |
| Rhythm (PaRappa / Gitaroo Man) | `RhythmTrack`, `ChipMusic` |
| Universal glue | `StatusStack`, `SfxLibrary`, `HUD` |

**Zero new mechanic types needed.** Same assertion shape as magic_hoops + ninja_garden, different axis.

## Architectural invariants this canary tests that prior canaries don't

1. **RhythmTrack × AttackFrames coupling** — AttackFrames reads `current_beat_phase` from RhythmTrack via `beat_source_ref` and applies `on_beat_damage_multiplier` / `off_beat_damage_multiplier` at hit-resolve. magic_hoops and ninja_garden have no mechanic-to-mechanic state dependencies of this kind.
2. **Beat-fraction time units** — `data/moves.json` expresses `startup_beats: 0.25` instead of `startup_frames: 15`. Tests that AttackFrames can accept alternate time-units at runtime without new code (`timing_unit: 'beats'` param).
3. **Deterministic mechanic execution order** — RhythmTrack must tick before AttackFrames (otherwise AttackFrames reads stale beat state). Mounting order encodes this invariant; the canary test asserts the order is preserved.
4. **BGM-driven gameplay state** — ChipMusic's BGM is not just flavor; it drives `drives_beat_clock: true` → RhythmTrack → damage modifiers. Tests that audio mechanics can be first-class game-state drivers.

## Directory layout

```
rhythm_fighter/
├── package.json
├── tsconfig.json           # @engine alias three levels up (cross/ nesting)
├── vite.config.ts          # port 5183
├── index.html
├── src/
│   ├── main.ts             # boots Match + on-beat pulse canvas indicator
│   └── scenes/
│       └── Match.ts        # 8 mechanics across 3 heritages + mount-order getter for canary test
└── data/
    ├── config.json             # match_rules with on_beat/off_beat multipliers + starting_matchup
    ├── characters.json         # 3 fighters (Ryu-Beat / Ken-Beat / P-Beat) with rhythm_bonus Resource
    ├── moves.json              # movesets keyed by beat-fractions (startup_beats / active_beats / recovery_beats)
    ├── stages.json             # 3 stages with BPM + time_signature
    ├── beatmaps.json           # per-stage beat grid + accent_beats + note_events
    └── mechanics.json          # 8-mechanic wiring exactly per JOB-Q Proposition 3
```

## Essence attribution

- `1991_street_fighter_ii` — AttackFrames + ComboAttacks canonical (SF2's combo system).
- `1996_parappa_the_rapper` — beat-lane canonical (on-beat input-window mechanic).
- `1999_gitaroo_man` — rhythm-combat hybrid canonical precedent (music-driven-combat fusion).
- `2005_guitar_hero` (cross-ref) — accent-beat hit detection model.

## Running

```bash
npm install
npm run dev  # localhost:5183
```

## Architecture canary result

See `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycle 25 for the verdict:
- If scaffold-smoke test passes on first try, the framework handles
  time-coupled cross-mechanic choreography correctly.
- Canary asserts `RhythmTrack` mount index < `AttackFrames` mount index
  (deterministic execution order), every `tryMount` name registered, and
  8 mechanics live.

If this needs NEW Layer 1 components or Layer 2 mechanics to compose,
go fix those abstractions — not this scaffold.
