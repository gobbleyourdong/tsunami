# Game 032 — Gradius (1985, arcade/MSX/NES)

**Mechanics present:**
- Horizontal scrolling shmup — AutoScroll (v1)
- Power capsules drop from killed enemies — PickupLoop ✓
- Power bar: each pickup advances cursor; player chooses WHEN to activate the current slot (speed/missile/double/laser/option/shield) — **`PowerSelectBar`** — unique power-up UI where the player chooses the upgrade step
- Options (up to 4 orbiting satellites) — `OrbitSatellite` (noted R-Type)
- Boss-at-end-of-stage — BossPhases ✓
- Stage sequence (volcano, nebula, moai, …) — LevelSequence (v1)
- 1-hit death — standard
- Death drops all upgrades — lose-on-death with component-reset
- Secret areas (destructible walls) — DestructibleTerrain (noted Lemmings)
- Moai heads that shoot spreads — boss/enemy variety
- Hard mode via the Konami Code — meta cheat (noted)

**Coverage by v0 catalog:** ~3/10

**v1 candidates from this game:**
- `PowerSelectBar` — unique compared to R-Type's auto-upgrade. Player-chosen progress cursor over a discrete tier ladder. A variant of PowerUpTier (noted R-Type) where choice is explicit.
- OrbitSatellite (confirmed R-Type note)

**Signature move:** the **power select bar** is an unusual control
mechanism — you earn upgrade "points" but choose when to spend them on
which slot. Player-driven build curve inside a real-time shooter. Small
primitive (~50 lines) that produces a very different feel from
automatic-upgrade shmups. Another content-multiplier-adjacent pattern:
one PowerSelectBar mechanic × N upgrade slot lists = N different
shmups.

**Coverage confirmation:** 3 shmups in corpus now (Galaga, Gradius,
Ikaruga). Shmup genre is saturated enough that v1's shmup bundle can
target: AutoScroll + WaveSpawner + BossPhases + BulletPattern +
OrbitSatellite + PowerUpTier + PowerSelectBar. ~7 primitives unlocks
the genre.
