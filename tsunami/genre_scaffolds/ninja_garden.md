---
name: ninja_garden
kind: cross_genre_canary
applies_to: [gamedev]
mood: hybrid, stealth-cultivation, patient-tempo
corpus_share: 1
anchors: [cross_canary, stealth_heritage, farming_heritage]
default_mechanics: [StateMachineMechanic, VisionCone, TimedStateModifier, PickupLoop]
recommended_mechanics: [HUD, WinOnCount, GatedTrigger, SfxLibrary]
would_falsify: if a ninja_garden delivery ships without StateMachineMechanic + VisionCone (the stealth substrate), OR without TimedStateModifier + PickupLoop (the cultivation substrate — plant growth timing + harvest pickup), OR without scene-level conditional coupling (harvest pickup gated by stealth state), the cross-genre premise is decorative — measured via mechanic adoption probe requiring mechanics from BOTH heritages AND a stealth→harvest GatedTrigger in a scene file
---

# ninja_garden (cross-genre canary)

This is a cross-genre canary — it composes mechanics from multiple
heritages to stress-test the framework's Layer 1/2 abstractions.

The scaffold at `scaffolds/gamedev/cross/ninja_garden/` is
already provisioned by `project_init_gamedev`. Your job is to
customize `data/*.json` files with the task's content (names,
counts, stats). Do NOT rewrite scenes — they're already wired
into `@engine/mechanics`.

See `scaffolds/gamedev/cross/ninja_garden/README.md` for the
scaffold's specific architecture + customization paths.
