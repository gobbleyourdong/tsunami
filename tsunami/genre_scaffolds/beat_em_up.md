---
applies_to: [gamedev]
mood: aggressive, side-scrolling, crowd-combat, arcade-pacing
corpus_share: 5
default_mode: dark
anchors: final_fight, streets_of_rage_2, turtles_in_time, simpsons_arcade
default_mechanics: [ComboAttacks, AttackFrames, WaveSpawner, CameraFollow, PickupLoop, HUD]
recommended_mechanics: [LoseOnZero, WinOnCount, SfxLibrary, ChipMusic, StatusStack]
would_falsify: if a beat-em-up delivery tagged with this genre ships without position-gated wave spawns (WaveSpawner with trigger_x list) OR lacks locked-forward scroll (CameraFollow forward_only=true) OR fights are 1v1 instead of 1-vs-many, the genre directive was ignored — measured via mechanic adoption probe for WaveSpawner + scene's camera forward_only flag AND enemy-count-per-wave ≥ 2
---

## Pitch

Three brawlers, one street, many thugs. Walk-right-hit-crowd-repeat.
The core verb is BRAWL — mash punch into a 3-hit combo, grab-throw to
crowd-control, special-to-clear-encirclement. Screen scrolls forward
when the current wave is cleared, never back. Pickups on the ground
(weapons, food, score items). Final Fight 1989 defines the arcade
template; Streets of Rage 2 1992 refines with 4-character roster and
grab-specials; TMNT Arcade 1991 pushes to 4-player local co-op.

## Mechanic set (anchor examples)

1. `ComboAttacks` — per-character 3-hit chains + grab-into-throw +
   special (meter-spending or self-damaging desperation).
2. `AttackFrames` — startup/active/recovery windows per swing. Matters
   for grab vs. strike timing.
3. `WaveSpawner` — position-gated enemy waves. When scroll crosses
   `trigger_x`, next wave spawns. Canonical beat-em-up pacing primitive.
4. `CameraFollow` — locked-forward scroll (no backtrack); ring-arena-
   lock on boss gate (camera freezes until mid-boss dies).
5. `PickupLoop` — ground items: weapons (knife/pipe/katana, 1-use or
   throwable), food (chicken/hamburger = HP refill), score items.
6. `HUD` — per-player HP bar (2-4 players), lives, score, stage name.
7. `LoseOnZero` — party KO → GameOver (unless continues available).
8. `WinOnCount` — stage-clear counter; beat all stages = campaign win.
9. `SfxLibrary` — hit/grab/throw/pickup/boss-sting preset bank.
10. `ChipMusic` — per-stage theme + boss sting (the genre's signature).

## Common shape

- **Playable brawlers**: 3-4 archetypes (grappler-heavy / speed /
  balanced). Haggar (grappler) + Cody (balanced) + Guy (speed) is the
  Final Fight canonical triangle.
- **Enemy archetypes**: 6-8 per-stage mix (grunt / knife-grunt /
  fatboy / runner-thief / andore-heavy / mid-boss). Each wave 3-5
  enemies, 5-8 waves per stage.
- **Stage count**: 4-6 stages with unique scroll_length + mid-boss
  gate + final boss arena. Boss-gate locks camera into ring-arena
  until boss dies.
- **Round structure**: single life per credit; continue = insert coin
  → 10s countdown → resume at last wave.
- **Fail state**: all brawlers HP=0 and no continues = GameOver.
- **Progression curve**: fixed-order stage-to-stage; no branching.
- **Control**: 3-button arcade (Punch / Kick / Jump); grab = walk-into-
  enemy; special = P+K (costs HP in Final Fight, meter in SOR2).

## Non-goals

- NOT a fighter (use `fighter` — 1v1 round-based vs. 1-vs-many
  side-scrolling crowd combat).
- NOT a platformer (use `platformer` — vertical-jumping vs. lateral-
  brawling; beat-em-ups have jump but it's a tactical dodge, not
  traversal).
- NOT an action-adventure (use `action_adventure` — the world is
  non-linear vs. the beat-em-up's strictly-linear side-scroll).
- 2D beat-em-up (Final Fight / SOR) vs. 2.5D (Bouncer / Yakuza combat
  loops) vs. 3D arena-brawler (Power Stone) are all variants of the
  same verb; the top-level `beat_em_up` directive applies to all.

## Anchor essences

`scaffolds/.claude/game_essence/1989_final_fight.md` —
**genre-definer canonical**. Haggar/Cody/Guy roster. Belger boss.
Metro City stage lineage. CPS-1 hardware template.

`scaffolds/.claude/game_essence/1992_streets_of_rage_2.md` —
**refinement canonical**. 4-character roster (Axel/Blaze/Max/Skate),
grab-specials, 2P co-op, Yuzo Koshiro soundtrack.

`scaffolds/.claude/game_essence/1991_turtles_in_time.md` —
**4P co-op canonical**. Licensed-property Konami template,
4-player local arcade cabinet, shared-screen 4-way combat.

`scaffolds/.claude/game_essence/1991_the_simpsons_arcade_game.md` —
**4P co-op alt**. Konami's other 4-player reference; same shape as
TMNT but with Simpsons licensed sprites + per-character uniqueness.

## Pitfalls the directive is trying to prevent

- Wave treats enemies as "all spawn on stage start" — beat-em-ups
  REQUIRE position-gated spawning. When the brawler walks right,
  the next wave appears. `WaveSpawner.mode="position_gated"` with
  per-wave `trigger_x` on the stage scroll is the discriminator.
- Wave implements freely-scrolling camera with backtracking —
  beat-em-ups lock camera to forward-only. `CameraFollow.forward_only=true`
  is non-negotiable. Backtrack-style = metroidvania, not beat-em-up.
- Wave builds 1v1 or 1v-one-at-a-time combat — beat-em-ups are 1-vs-
  many-simultaneously. Each wave is 3-5 enemies on-screen at once,
  and the brawler must crowd-control via grabs/throws/specials.
- Wave skips pickups — ground items (weapons, food, score) are a
  pacing primitive. Without them, the loop reduces to HP-grind.
- Wave doesn't model boss-gate ring-arena — every stage ends with a
  mid-boss or final-boss arena that LOCKS the camera until the boss
  dies. `CameraFollow.lock_on_boss_gate=true` models this.
- Wave invents per-character movesets without frame data — like
  fighters, beat-em-ups have startup/active/recovery per swing.
  Use `AttackFrames` alongside `ComboAttacks`.
