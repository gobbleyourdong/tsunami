---
name: metroid_runs
kind: cross_genre_canary
applies_to: [gamedev]
mood: hybrid, ability-gated exploration, death-restart cadence
corpus_share: 1
anchors: [cross_canary, metroidvania_heritage, roguelite_heritage]
default_mechanics: [PhysicsModifier, LockAndKey, RoomGraph, CheckpointProgression]
recommended_mechanics: [PickupLoop, LevelUpProgression, HUD, ProceduralRoomChain]
would_falsify: if a metroid_runs delivery ships without LockAndKey + RoomGraph (the metroidvania substrate), OR without ProceduralRoomChain + CheckpointProgression (the roguelite substrate — randomized layouts + run-boundary resets), OR without scene-level coupling (ability gates persist across runs while map resets), the cross-genre premise collapses — measured via mechanic adoption probe for LockAndKey + ProceduralRoomChain co-occurrence plus CheckpointProgression in save-related data
---

# metroid_runs (cross-genre canary)

This is a cross-genre canary — it composes mechanics from multiple
heritages to stress-test the framework's Layer 1/2 abstractions.

The scaffold at `scaffolds/gamedev/cross/metroid_runs/` is
already provisioned by `project_init_gamedev`. Your job is to
customize `data/*.json` files with the task's content (names,
counts, stats). Do NOT rewrite scenes — they're already wired
into `@engine/mechanics`.

See `scaffolds/gamedev/cross/metroid_runs/README.md` for the
scaffold's specific architecture + customization paths.
