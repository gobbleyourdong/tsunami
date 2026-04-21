---
name: action_rpg_atb
kind: cross_genre_canary
anchors: cross_canary
corpus_share: 1
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
