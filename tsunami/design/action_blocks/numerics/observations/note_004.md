# Observation 004 — Sandbox mode (no-fail games)

**Sources:** prompt_007 (Farming sim: soft-fail), game_008 (SimCity 2000),
game_011 (Monkey Island — cannot die by design), game_015 (The Sims —
open-ended). 2 prompts + 3 retro = 5/30 sources where v0's implicit
requirement for `LoseOnZero`/`WinOnCount` flow completion breaks the game.

**Claim:** v0's flow assumes a lose path and a win path. Sandbox / open-
ended games (The Sims, Minecraft, Animal Crossing) and puzzle-adventures
(Monkey Island) have neither. Forcing them through v0 requires either
dummy mechanics or a lose condition that's never wired — both ugly.

**Proposed schema update:**

```ts
// GameRuntimeConfig addition:
interface GameRuntimeConfig {
  ...
  sandbox?: boolean   // if true, WinOnCount/LoseOnZero become optional
}
```

The validator currently (or will) enforce "every script must have ≥ 1
lose path emitted". With `sandbox: true`, that requirement relaxes;
flow is optional; the game runs forever until user quits.

**Alternative considered:** separate sandbox schema entirely. Rejected —
the only difference is the flow requirement. Sandbox games still use
all the other primitives (archetypes, mechanics, HUD, components). A
flag is cheaper.

**Secondary consideration:** "soft-fail" games (farming sim: your crops
die but you don't). Neither sandbox nor lose-required. Probably:
sandbox=true + explicit LoseOnZero mechanics wired at archetype level
(crop health), but flow doesn't terminate on crop-death. The flag
unblocks the authoring, mechanic composition handles the semantic.

**Estimated coverage gain:** 3 genres (sandbox sim, open-ended
adventure, life sim). Small additional implementation cost (one flag,
one validator branch). High payoff per cost ratio.

**Recommendation:** include in v1. Low-risk.
