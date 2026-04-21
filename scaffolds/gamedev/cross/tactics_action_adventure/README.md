# Tactics Action Adventure — cross-genre scaffold

**Pitch:** Octopath Traveler's ATB combat × Zelda overworld exploration ×
Chrono Trigger / Fire Emblem branching endings. The overworld is
real-time action; enemy contact drops into an ATB combat encounter;
dialogue and hotspots gate progression and drive the ending. All from
`@engine/mechanics` — no new primitives.

## Heritage mix (16 mechanics across 4 buckets)

| Heritage  | Mechanics                                                              |
|-----------|------------------------------------------------------------------------|
| tactics   | `ATBCombat`, `TurnBasedCombat` (mounted inert, proves both fit), `PartyComposition`, `RoleAssignment`, `UtilityAI` |
| action    | `CameraFollow`, `AttackFrames` (overworld swing), `CheckpointProgression` |
| adventure | `DialogTree` × per dialog, `HotspotMechanic` × per hotspot, `WorldMapTravel`, `Shop`, `EndingBranches` |
| universal | `HUD`, `LoseOnZero`, `ItemUse`                                         |

Four heritages, all composed. The scaffold's role is proving the
framework's vocabulary is complete enough that a genre-dense combo
(three clearly different pacing models) doesn't need a special case.

## Quick start

```bash
npm install
npm run dev        # localhost:5185
npm run check      # tsc typecheck
```

## Design calls

- **Mode transitions** — `config.json::mode_transitions` declares when
  action→combat and combat→action fire. The scaffold doesn't implement
  the switcher; it mounts both mode stacks and leaves the transition
  to a hand-written StateMachineMechanic (plan for a future scaffold
  pass).
- **Two combat systems mounted** — `ATBCombat` is active; `TurnBasedCombat`
  is mounted with `enabled: false` to prove the scaffold can swap to
  strict turn-based without touching the rest of the tree.
- **Dialog drives endings** — each dialog node can `set_flag`; the
  `EndingBranches` mechanic reads those flags against
  `dialog.json::endings.*.requires_flags` at endgame and picks an
  epilogue. Tested in canary via `Adventure.activeEnding()`.
- **Four party members, three active slots** — tactical choice baked
  into `party.json`. Swap a member in town; their ATB rate follows
  from their role via `RoleAssignment`.

## Customize

- **Add a node to the world map** → append to `world.json::world_map.nodes`
  with `links` to neighbors. Add hotspots that sit at that node under
  `world.json::hotspots`.
- **Add an enemy archetype** → `combat.json::enemy_archetypes`; include
  `ai_utility_weights` so UtilityAI has a signal.
- **Add an ending** → new flag dispatch in `dialog.json`, new entry in
  `dialog.json::endings` with `requires_flags`. EndingBranches handles
  the rest.

## Don't

- Don't mount both combat systems with `enabled: true` — they will
  race on the same actor stream. Pick one per encounter via the
  StateMachineMechanic switch.
- Don't put dungeon progression in the dialog tree. Dialogs set flags;
  flags gate hotspots. Keep "what happens when X happens" separate
  from "what the NPC said."
- Don't add a 5th party slot without bumping `max_active`. The HUD
  layout assumes `max_active == 3`; adding a 4th visible slot reflows
  the corners.

## Anchors

`Octopath Traveler`, `Chrono Trigger`, `Final Fantasy VI`,
`Zelda: A Link to the Past` (overworld), `Fire Emblem` (turn-based
combat encounters), `Undertale` (branching endings).

## Canary

`scaffolds/engine/tests/tactics_action_adventure_canary.test.ts` —
validates tree, data shape, scene imports `@engine/mechanics` only,
every `tryMount()` resolves in the registry, ≥ 3 heritages represented,
flag→ending logic works.
