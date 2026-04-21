---
name: action_rpg_atb
kind: cross_genre_canary
applies_to: [gamedev]
mood: hybrid, real-time-with-pauses, meter-driven tempo
corpus_share: 1
anchors: [cross_canary, action_rpg_heritage, atb_jrpg_heritage]
default_mechanics: [AttackFrames, ATBCombat, LevelUpProgression, StatusStack]
recommended_mechanics: [HUD, ComboAttacks, EquipmentLoadout, CheckpointProgression]
would_falsify: if an action_rpg_atb delivery ships without AttackFrames (the action substrate), OR without ATBCombat + LevelUpProgression (the atb-jrpg substrate), OR without scene-level coupling (attacks deplete and refill the ATB meter on real-time tempo), the hybrid collapses to one parent genre — measured via mechanic adoption probe requiring AttackFrames + ATBCombat in the same scene
---

# action_rpg_atb (cross-genre canary)

This is a cross-genre canary — it composes mechanics from multiple
heritages to stress-test the framework's Layer 1/2 abstractions.

The scaffold at `scaffolds/gamedev/cross/action_rpg_atb/` is
already provisioned by `project_init_gamedev`. Your job is to
customize `data/*.json` files with the task's content (names,
counts, stats). Do NOT rewrite scenes — they're already wired
into `@engine/mechanics`.

See `scaffolds/gamedev/cross/action_rpg_atb/README.md` for the
scaffold's specific architecture + customization paths.
