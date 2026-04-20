# Action-RPG ATB — Cross-Genre Canary #4

> **Role**: fourth architecture-correctness gate for the gamedev framework. **First canary with TWO scenes** (Field + Battle) — tests scene-boundary state persistence, an invariant no prior canary covers.
>
> If this scaffold compiles + tests clean **without adding any new mechanic types**, the framework's Layer 1/2 abstractions handle cross-scene state marshalling correctly.

## Concept

Legend of Zelda × Final Fantasy IV:
- Zelda-style real-time top-down dungeon traversal (RoomGraph + LockAndKey + ItemUse)
- FF4-style ATB battle on enemy contact (ATBCombat + PartyComposition + EquipmentLoadout + BossPhases)
- **Party HP/MP/equipment persist across Field ↔ Battle** — this is what the canary proves

## What this proves

Every mechanic wired already exists in `@engine/mechanics`:

| Heritage | Mechanics |
|---|---|
| Action-adventure (Zelda) | `RoomGraph`, `LockAndKey`, `ItemUse` |
| JRPG (FF4) | `ATBCombat`, `PartyComposition`, `EquipmentLoadout`, `BossPhases` |
| Universal glue | `CameraFollow`, `HUD` |

**Zero new mechanic types needed.**

## Architectural invariants this canary tests that prior canaries don't

1. **Scene-boundary state persistence** — the same `PartyComposition` state (active_party, HP, MP, status effects) must survive when Field hands off to Battle and back. Prior canaries have one scene; this has two.
2. **Dual-camera-mode** — `CameraFollow` operates top-down/player-anchored in Field but orthographic/anchor-based in Battle. Tests the mechanic's param-flexibility per-scene.
3. **Mechanic-activation gating** — field-mode mechanics (`RoomGraph`, `LockAndKey`, `ItemUse`) freeze during battle; battle-mode mechanics (`ATBCombat`) freeze during field. Framework's scene-manager must pause/resume without state loss.
4. **Equipment carry-over** — swaps made in Field's equip menu must apply to Battle's damage calculations.

## Concept → scene wiring

Two scenes (`Field` + `Battle`) exchange state via public-API handoffs:
- `field.handoffToBattle()` returns the party-state snapshot.
- `battle.startEncounter(groupId, partyIds)` seeds combat from it.
- `battle.snapshotForField()` returns the post-battle state.
- `field.restoreFromBattle(snapshot)` reapplies KO state / equipment changes.

## Directory layout

```
action_rpg_atb/
├── package.json, tsconfig.json (@engine alias three levels up), vite.config.ts (port 5184)
├── index.html
├── src/
│   ├── main.ts           # boots Field scene; render loop pulses field↔battle indicator
│   └── scenes/
│       ├── Field.ts      # 6 mechanics (Zelda-flavored)
│       └── Battle.ts     # 6 mechanics (FF4-flavored)
└── data/
    ├── config.json             # starting_room, starting_party, transition triggers
    ├── player.json             # party leader with field-tools inventory
    ├── party.json              # 4-6 party members + formations + battle_command_menu
    ├── rooms.json              # dungeon graph with LockAndKey gates
    ├── enemies.json            # field sprites that trigger encounters on contact
    ├── battles.json            # encounter_groups + battle_actors with HP/MP/speed
    ├── equipment.json          # slot catalog for EquipmentLoadout
    ├── mechanics.json          # 9-mechanic wiring exactly per JOB-V composition target
    └── rules.json              # scene-transition rules + persistence whitelist
```

## Essence attribution

- `1986_legend_of_zelda` — RoomGraph + LockAndKey canonical.
- `1991_final_fantasy_iv` — ATBCombat + PartyComposition + EquipmentLoadout canonical.
- `1995_chrono_trigger` — seamless field-to-battle transition (no black-screen transition).
- `1995_secret_of_mana` — hybrid real-time + menu-pause RPG precedent.

## Running

```bash
npm install
npm run dev  # localhost:5184
```

## Architecture canary result

See `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycle 27 for the verdict — whether the scaffold compiled + tested clean on first try determines whether scene-boundary state persistence is correctly factored.

If this needs NEW Layer 1 components or Layer 2 mechanics to compose, go fix those abstractions — not this scaffold.
