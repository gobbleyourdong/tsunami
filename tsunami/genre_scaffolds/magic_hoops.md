---
name: magic_hoops
kind: cross_genre_canary
applies_to: [gamedev]
mood: hybrid, spell-sports, arena-tempo
corpus_share: 1
anchors: [cross_canary, sports_heritage, magic_system_heritage]
default_mechanics: [PhysicsModifier, WinOnCount, ItemUse, StatusStack]
recommended_mechanics: [HUD, CameraFollow, SfxLibrary, RoleAssignment]
would_falsify: if a magic_hoops delivery ships without PhysicsModifier + WinOnCount co-occurrence (the sports-scoring substrate), OR without ItemUse + StatusStack (the spell-effect substrate), OR without scene-level wiring joining the two (scoring condition triggered by status effect from ItemUse), the cross-genre premise was lost — measured via mechanic adoption probe requiring mechanics from BOTH heritages in the same scene
---

# magic_hoops (cross-genre canary)

This is a cross-genre canary — it composes mechanics from multiple
heritages to stress-test the framework's Layer 1/2 abstractions.

The scaffold at `scaffolds/gamedev/cross/magic_hoops/` is
already provisioned by `project_init_gamedev`. Your job is to
customize `data/*.json` files with the task's content (names,
counts, stats). Do NOT rewrite scenes — they're already wired
into `@engine/mechanics`.

See `scaffolds/gamedev/cross/magic_hoops/README.md` for the
scaffold's specific architecture + customization paths.
