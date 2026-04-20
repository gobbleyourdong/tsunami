---
applies_to: [gamedev]
mood: systemic, choice-rich, non-linear, mechanics-interact, anti-linearity
corpus_share: 5
default_mode: dark
anchors: system_shock_2, deus_ex, thief_the_dark_project, ultima_underworld
default_mechanics: [RoomGraph, ItemUse, UtilityAI, VisionCone, DialogTree, HUD]
recommended_mechanics: [StatusStack, InventoryCombine, ComboAttacks, GatedTrigger, Shop, BossPhases]
would_falsify: if an immersive-sim delivery tagged with this genre ships with only one solution to key problems (no alt-routes via hacking / stealth / combat / persuasion) OR lacks interactable environmental systems (light, sound, flammable, conductive), the genre directive was ignored — measured via delivery having ≥2 tagged solution paths per mission + mechanic adoption probe for StatusStack interactions
---

## Pitch

The "0451 genre" — simulated mini-worlds where systems interact,
player has MULTIPLE SOLUTIONS to every problem (hack, stealth, combat,
dialog, environmental manipulation), and the game remembers what you
did. The core verb is SOLVE-YOUR-WAY. Ultima Underworld 1992 seeds
the first-person-3D-with-simulation idea; System Shock 1994 canonizes
it; Thief 1998 extracts the stealth pillar; System Shock 2 / Deus Ex
define the modern immersive-sim template.

## Mechanic set (anchor examples)

1. `RoomGraph` — interconnected non-linear map with multiple paths
   to most destinations (vents, keyed doors, hackable terminals).
2. `ItemUse` — deep inventory: weapons, tools (lockpicks, multitools,
   EMP grenades, biomods).
3. `UtilityAI` — per-NPC state: patrol / alert / alarmed / dead; also
   global faction-wide alarm state.
4. `VisionCone` — stealth option is always available.
5. `DialogTree` — NPCs respond to player choices + faction standing +
   stat checks (hack X, persuade Y).
6. `StatusStack` — persistent buffs/debuffs (biomods, augmentations,
   radiation, stun, poison) that compose.
7. `InventoryCombine` — crafting (SS2 research, DX aug upgrades).
8. `Shop` — vendors exchange resources (credits, nanites, tech).
9. `GatedTrigger` — key-card progression + faction-reputation gates.
10. `BossPhases` — major enemies with multiple phase/weakness options
    (psi-shield then HP; specific-weapon-damage requirements).

## Common shape

- **Mission count**: 6-15 hub-and-spoke; or one big interconnected world
  (UU, SS2). Player returns to hubs for progression.
- **Character customization**: skill points or biomods assigned by the
  player — dictates viable solutions. `ClassBuilder`-like (`CurrencyBasedSkillTree`).
- **Fail state**: HP=0 → reload; but also "wrong choice" consequences
  carry forward (NPC dead = their quest-line gone; alarm raised =
  world reacts).
- **Progression curve**: stats + gear + KNOWLEDGE (audio logs, keycard
  codes, lore → player skill substitute).
- **Control**: WASD movement, mouse aim, quick-slot items (1-0),
  interact key, alt-fire / biomod activation.
- **Playtime**: 20-50 hours per title.

## Non-goals

- NOT an action-RPG (use `action_rpg` — RPG numbers dominant, less
  systemic interaction between mechanics).
- NOT a shooter (use `fps` — guns primary, alternatives incidental;
  immersive-sim guns are ONE solution among many).
- NOT a CRPG (use `wrpg` — party-based, grid-tactics in some, less
  simulation).
- NOT a stealth game (use `stealth` — stealth is ONE PILLAR of
  immersive-sim; stealth is the stealth genre's whole identity).

## Anchor essences

`scaffolds/.claude/game_essence/1992_ultima_underworld.md` —
**immersive-sim-progenitor**. First-person 3D with simulation layers
(physics, conversation, magic, crafting). Defines multi-path problem
solving.

`scaffolds/.claude/game_essence/1994_system_shock.md` —
**Looking-Glass-immersive-sim-canonical**. Cyber-modules
(`CurrencyBasedSkillTree`), audio logs (`AudioLog`), research
(`ResearchProgression`), skill-check gating (`SkillCheckGating`). The
direct BioShock ancestor.

`scaffolds/.claude/game_essence/1999_system_shock_2.md` —
modern SS lineage. Class-driven build (`ClassBuilder`), weapon
degradation (`WeaponDegradation`), co-op campaign (`CoopCampaign`).

`scaffolds/.claude/game_essence/2000_deus_ex.md` —
multi-path mission structure (`MultiPathMissionStructure`), faction
reputation (`FactionReputation`), aug upgrades (`ExclusiveChoiceSlot`).
Genre-defining modern immersive-sim.

`scaffolds/.claude/game_essence/1998_thief_dark_project.md` —
stealth-pillar canonical (see `stealth` genre for the stealth-exclusive
variant). Included here because Thief's light+sound simulation layers
are the immersive-sim systemic-approach exemplar.

## Pitfalls the directive is trying to prevent

- Wave ships ONE solution per problem (just shoot your way through).
  Immersive-sim REQUIRES ≥2 viable paths per key obstacle: combat +
  stealth, or hacking + keycard, or dialog + bypass. Mechanic
  composition enforces this — `VisionCone` (stealth) + `DialogTree`
  (persuade) + direct combat should each resolve the same mission.
- Wave treats skill points as stat modifiers — they should GATE SOLUTIONS.
  "Hack 3" unlocks the terminal-solution; "Persuade 2" unlocks the
  dialog-solution. `GatedTrigger` with skill-level predicate is the
  right pattern.
- Wave omits environmental simulation — immersive-sim GENRE identity
  includes interacting layers (light affects stealth, sound propagates,
  flammable materials ignite). `StatusStack` + typed damage + room
  properties do this.
- Wave creates a non-reactive world — immersive-sim REQUIRES NPC
  memory of player actions. Killed NPC stays dead; alarm-raised-mission
  is different mission. `GatedTrigger` with persistent flags.
- Wave makes "0451" a keycode without explanation — that IS a direct
  Looking-Glass cultural reference. Including it as the default first-
  door-code is a chef's kiss, not a bug.
