# Game 023 — Silent Hill (1999, PS1)

**Mechanics present:**
- 3D over-the-shoulder exploration — partial (topdown close, orbit close; no dedicated 3rd-person controller)
- Radio that statics when monsters near — `ProximityTrigger` (noted, shmup graze) + audio event
- Fog and darkness limiting sight range — engine-level rendering (fog-of-view) + gameplay implication (awareness)
- Psychological horror (sanity-coded environment, no jump-scares primary) — atmosphere-driven, not mechanic
- Puzzle solving (combination safes, riddles, musical puzzles) — PuzzleObject (v1) + musical variant
- Combat with unreliable aim (intentional clumsy controls) — controller design choice, not a mechanic
- Multiple endings (4+) based on actions across playthrough — EndingBranches (noted)
- Otherworld shifts (same layout, corrupted visuals + tougher enemies) — `ParallelWorldLayer` (noted, Zelda LTTP)
- Inventory with health items + weapons — standard Inventory
- Save points (floppy disc / record) — CheckpointProgression with restrictive placement
- Maps found in world — `MapItem` usable in inventory to reveal HUD overlay
- Note/document collection — LoreEntry (noted)
- Radio callers / monster callers — scripted audio stimuli tied to AlertState
- Character mental state representing through world — unclear mechanical layer; deeply evocative but hard to formalize
- Pyramid Head (iconic static boss) — BossPhases variant with scripted appearance
- Protect/rescue NPC (take Cybil home) — Escort AI (ally archetype with fragility)

**Coverage by v0 catalog:** ~3/16

**v1 candidates from this game:**
- `ProximityTrigger` (noted shmup; re-confirmed)
- `MapItem` / item-unlocks-HUD-overlay
- Escort AI — protect-the-NPC ally archetype with loss condition if they die
- `FogOfView` engine-level (renderer, not mechanic)
- `PsychoScope` / atmosphere-driven mechanic — open question whether formalizable

**Signature move:** **mechanical scarcity + psychological pressure combine to create horror.** Ammo is rare (Resource + PickupOnce), aim is clumsy (controller), maps are hand-drawn cues (MapItem), radio is always on edge (ProximityTrigger), enemies are unexplained (narrative ambiguity). NO SINGLE MECHANIC creates horror — it's the *combination*. Validates the emergence thesis a 3rd time. But also shows horror authoring would require hand-tuning atmosphere (audio, lighting, pacing) which the design script schema doesn't touch.

**Flag for design track:** `vibe: ["horror"]` in meta is currently free-form. Consider whether vibe tags drive an atmospheric preset (lighting/audio/pace defaults) that authors can tune.
