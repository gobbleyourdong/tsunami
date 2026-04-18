# Game 021 — NetHack (1987, PC/Unix)

**Mechanics present:**
- ASCII rendering on a tile grid — **not in v0** (GridPlayfield)
- Turn-based movement and action — **not in v0** (TurnManager)
- Procedural dungeon with branches (Gnomish Mines, Mine Town, Sokoban, Gehennom) — **not in v0** (ProceduralDungeon + branching RoomGraph)
- Identification system (potions/scrolls/wands unknown until tested) — **not in v0** (`IdentificationFlags` — per-item-type known/unknown)
- Character classes (Valkyrie, Wizard, Samurai, etc.) — `CharacterSelect` (noted)
- Alignment (lawful/chaotic/neutral) + pantheon — gameplay modifier system
- Deep inventory with item types (armor/weapon/scroll/potion/ring/amulet/tool/food) — specialized Inventory
- Polymorph (become another creature) — **not in v0** (temporary archetype swap)
- Pet system (companion animal) — AI-friendly archetype with leveling
- Hunger / nutrition — Resource (v1)
- Status effects (confusion, stun, blind, hallucination, etc.) — StatusStack (noted)
- Combat with weapons / monster-type resistances — partial (Health resistances exist)
- Trap system (floor tiles with effects) — **not in v0** (trigger-tile mechanic, generalizable)
- Shops with shopkeeper AI (hostile if you steal) — Shop + AI-reaction-on-state
- Altars (sacrifice items for boons) — `PuzzleObject` variant
- Wish (limited major reward) — rare event mechanic
- Amulet endgame quest (elemental planes) — LevelSequence with late branching
- YASD (Yet Another Stupid Death) culture — permadeath
- Thousand hours of learning curve — not a mechanic, but evidence of mechanical depth

**Coverage by v0 catalog:** ~1/18

**v1 candidates from this game:**
- Full grid + turn mode (noted across prompts)
- `IdentificationFlags` — per-item-type known/unknown across inventory instances
- `Polymorph` / temporary archetype swap
- `TrapTile` — grid-tile trigger with hidden-until-stepped-on
- `Altar` / sacrifice ritual — PuzzleObject with component exchange
- Rich permadeath + save-on-exit (no save-scumming) — `PersistenceScope: 'meta'` with death-invalidation

**Signature move:** **mechanical depth from systemic interactions**. NetHack's cultural reputation is that every object interacts with every other in some way (you can dip a wand in a fountain; you can pray on an altar; you can throw a cockatrice egg; you can quaff from a potion of polymorph to become a dragon). This is the EXTREME end of the method's emergence thesis — small catalog × full composition = thousands of interactions. The design-script method is conceptually aligned; executing at this depth is a 10+ year project. v0 targets arcade; NetHack is v10+.
