---
applies_to: [gamedev]
mood: melodramatic, grind-tolerant, turn-patient, story-driven
corpus_share: 11
default_mode: dark
anchors: final_fantasy_iv, chrono_trigger, final_fantasy_vii, dragon_quest
default_mechanics: [DialogTree, HUD, ItemUse, LevelSequence, InventoryCombine, Shop]
recommended_mechanics: [BossPhases, CheckpointProgression, RouteMap, GatedTrigger, StateMachineMechanic, EndingBranches]
would_falsify: if a JRPG delivery tagged with this genre ships without turn-based combat (combat resolves in real-time instead of discrete turn queues) OR omits a party system (single-character only), the genre directive was ignored — measured via mechanic adoption probe on DialogTree + a post-delivery check for turn-queue state machines in the emitted engine mechanics
---

## Pitch

Character-driven narrative RPG with turn-based combat, party composition,
and world-map navigation. The core verb is PROGRESS — level up via
battle grind, advance the story via dialog, acquire gear from shops
and dungeons. Final Fantasy IV 1991 defines the ATB lineage;
Chrono Trigger 1995 adds visible-encounter combat; FF VII 1997 brings
3D field + pre-rendered backdrops; Dragon Quest 1986 is the primordial
ancestor.

## Mechanic set (anchor examples)

1. `DialogTree` — NPC conversation, branching dialog, flag-driven
   event text.
2. `HUD` — party HP/MP/Limit, turn order indicator, battle menu.
3. `ItemUse` — consumables (potions, ethers, phoenix downs).
4. `LevelSequence` — world-map regions + towns + dungeons in ordered
   unlock sequence.
5. `InventoryCombine` — crafting (FF7 materia socketing, Chrono Cross
   element grid).
6. `Shop` — buy/sell/upgrade interface in every town.
7. `BossPhases` — multi-phase boss encounters with HP-threshold triggers.
8. `CheckpointProgression` — save points (usually fixed locations).
9. `RouteMap` — world-map travel between scenes + vehicle unlocks
   (ship, chocobo, airship).
10. `EndingBranches` — chapter finales or whole-game branches driven
    by relationship flags or story choices.

## Common shape

- **Party size**: 3-8 characters; 3-4 active in combat.
- **Combat model**: turn-based (pure) or ATB (hybrid tick) — see the
  `ATBCombat` + `TurnBasedCombat` mechanics once promoted from essence.
- **Playtime**: 20-60 hours; grind + exploration + story.
- **Progression curve**: level-up → stat growth + ability unlock; gear
  gates region difficulty.
- **Fail state**: party wipe → last save; game-over screen common.

## Non-goals

- NOT an action-RPG (use `action_rpg` when it lands — real-time combat).
- NOT a CRPG / Western RPG (use `wrpg` — different combat / dialog
  conventions, stat-checked skill challenges).
- NOT a tactics RPG (use `tactics_rpg` — grid-based combat).
- NOT an MMO (use `mmo` if it lands — shared world, real-time).

## Anchor essences

`scaffolds/.claude/game_essence/1991_final_fantasy_iv.md` —
**ATB combat canonical ancestor**, party-composition archetype slots
with story-scripted join/leave.

`scaffolds/.claude/game_essence/1995_chrono_trigger.md` —
visible overworld encounters (no random), triple-character combo
techs, time travel worldmap structure.

`scaffolds/.claude/game_essence/1997_final_fantasy_vii.md` —
materia socket system, 3D field + pre-rendered backdrops, limit-break
damage meter. The "modern JRPG" template.

`scaffolds/.claude/game_essence/1986_dragon_quest.md` —
primordial JRPG. Simplest possible turn queue; everything else is
additive from here.

`scaffolds/.claude/game_essence/1994_final_fantasy_vi.md` — opera
cutscene, Espers (slot-based ability grant), midgame world-shift.

## Pitfalls the directive is trying to prevent

- Wave defaults to real-time combat because that's Qwen's priors —
  JRPG REQUIRES discrete turn queues. `StateMachineMechanic` with
  turn-state transitions is the right shape.
- Wave ignores party composition and builds a single-character hero
  — JRPG identity is multi-character roster (3-8) with per-character
  role specialization.
- Wave implements dialog as modal popups — real JRPG dialog is
  dialog-box-with-advance-on-input. `DialogTree` handles this; the
  wave shouldn't re-invent.
- Wave omits shops — shops are how JRPG economy gates region
  difficulty. `Shop` mechanic is non-negotiable.
