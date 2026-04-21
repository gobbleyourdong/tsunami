---
name: rhythm_fighter
kind: cross_genre_canary
applies_to: [gamedev]
mood: hybrid, beat-driven combat, timing-gated specials
corpus_share: 1
anchors: [cross_canary, rhythm_heritage, fighting_heritage]
default_mechanics: [AttackFrames, ComboAttacks, RhythmTrack, StateMachineMechanic]
recommended_mechanics: [WaveSpawner, HUD, LoseOnZero, StatusStack]
would_falsify: if a rhythm_fighter delivery ships without a RhythmTrack-gated timing window on special moves, OR without AttackFrames hit-stun, OR without ComboAttacks → RhythmTrack alignment that defines the canary's cross-genre premise, the directive was ignored — measured via mechanic adoption probe for RhythmTrack + ComboAttacks + AttackFrames co-occurrence in scene files
---

# rhythm_fighter (cross-genre canary)

This is a cross-genre canary — it composes mechanics from multiple
heritages to stress-test the framework's Layer 1/2 abstractions.

The scaffold at `scaffolds/gamedev/cross/rhythm_fighter/` is
already provisioned by `project_init_gamedev`. Your job is to
customize `data/*.json` files with the task's content (names,
counts, stats). Do NOT rewrite scenes — they're already wired
into `@engine/mechanics`.

See `scaffolds/gamedev/cross/rhythm_fighter/README.md` for the
scaffold's specific architecture + customization paths.
