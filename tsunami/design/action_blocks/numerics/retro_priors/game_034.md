# Game 034 — Daytona USA (1994, arcade/Saturn)

**Mechanics present:**
- 3D arcade racing — VehicleController (v1)
- Oval track with checkpoints + lap count — TrackSpline + LapCounter (v1)
- 7 AI opponents — WaypointAI (noted)
- Power-sliding / drift boost mechanic — DriftBoost (noted Mario Kart)
- Stage branches by track (Beginner/Advanced/Expert) — LevelSequence variant with per-stage difficulty tag
- Time limit: extend per checkpoint — CheckpointRace (noted prompt_032)
- 4-player networked arcade — local multiplayer (v2+)
- "DAYTONAAAAA" announcer — scripted audio event bank (noted NBA Jam)
- Car selection — CharacterSelect (noted)

**Coverage by v0 catalog:** ~1/9

**v1 candidates from this game:** all already noted. No new primitives.

**Signature move:** **accessible 3D racing**. Daytona proved that 3D
racing could be arcade-fun with simplified physics. Confirms:
- Arcade racing (prompt_032 + MK64 + Daytona) is coherent genre bundle.
- Necessary v1 primitives all named: VehicleController (arcade tune), TrackSpline, LapCounter / CheckpointRace, WaypointAI + RubberBanding + DriftBoost.
- Sim racing (Gran Turismo) remains distinct + out-of-v1.

**Dedupe signal:** 3 racing games in corpus (GT, MK64, Daytona).
Genre's v1 primitive set is stable. Further racing entries in future
batches unlikely to raise new primitives — can deprioritize more
racing samples.
