# Observation 006 — Embedded mini-games as a meta-pattern

**Sources:** game_020 (FF6 Opera House rhythm-minigame, Colosseum gamble),
game_019 (Beatmania — but isolated), prompt_019 (VN cross-examination),
game_010 (Chrono Trigger Robo dance minigame). Also classic DDR-in-other-
games pattern, Zelda fishing/cooking/sidequests in general.

**Claim:** many shipped games temporarily **suspend their primary
mechanics and enter a different mechanic entirely** for a sidequest, a
set-piece, or a cutscene-interactive moment. The player is still the
player, the world is paused, and a contained mini-mechanic runs to
completion before returning to the main loop.

**Current v0 has no first-class concept for this.** You could:
- (A) Make each mini-game a separate scene; `flow.goto('minigame_1')`
  then back. Works mechanically but suggests a story-level scene-change
  where narratively there isn't one.
- (B) Author the mini-game mechanic as always-enabled but gated by a
  state flag. Clunky and leaves the mini-game's mechanics polluting the
  main scope.

**Proposed primitive:** `EmbeddedMinigame` mechanic wrapper.

```ts
interface EmbeddedMinigameParams {
  trigger: ConditionKey        // fires to enter
  mechanics: MechanicInstance[] // the sub-game's own mechanic list
  suspend_mechanics?: MechanicId[]  // ids from outer scope to pause
  exit_condition: ConditionKey
  on_exit?: ActionRef          // resume hook (award item, advance flag)
}
```

The compiler treats it like a nested design script whose lifecycle is
gated by outer flow. When `trigger` fires, suspend the named outer
mechanics and enter the inner set. On `exit_condition`, reverse. This
preserves composition — mini-games use the same mechanic catalog.

**Why it's valuable:** the method's emergence claim is "small catalog ×
composition = large game space." Embedded mini-games are *horizontal
composition*, and the data shows they're pervasive — sidequests,
set-pieces, tutorial moments all exhibit this shape. Without the
primitive, every authored game that wants a rhythm-break or a card-game-
shop has to hack scene transitions.

**Cost:** low. It's a lifecycle wrapper over existing mechanic
instances — nothing novel runtime-wise. The design-track's compiler
already knows how to instantiate and tear down mechanics.

**Recommendation:** v1. Single mechanic that unlocks a wide design
pattern. Composes with sandbox mode (note_004) cleanly and makes the
"make me a JRPG where the save shrine is a rhythm game" kind of
authoring request trivial.

**Cross-reference:** the visual-novel prompt (019) can use this for
Phoenix Wright cross-examination — the evidence-presenting phase is an
EmbeddedMinigame inside the main dialogue flow.
