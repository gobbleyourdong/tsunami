# Magic Hoops — Cross-Genre Canary

> **Role**: architecture-correctness test for the gamedev framework's Layer 1/2 abstractions.
>
> If this scaffold compiles + tests clean **without adding any new mechanic types or component kinds**, the framework has passed its cross-genre composition test.

## Concept

1v1 magical basketball:
- Two wizards (Gandalf, Merlin) on a court
- Each has HP + mana + a spellbook (fireball / heal / shield / push / blink / ice-bolt)
- Goals at each end of the court
- Spells damage the opponent AND interact with the ball (push-knockback on ball, freeze opponent with ice-bolt)
- Match ends when clock hits 0 or one team hits 5 goals

Cross-genre because it inherits from **three genres simultaneously**:
- **Sports** (goals, scoreboard, clock-driven match end)
- **Fighting** (HP, combat, respawn-on-KO, spell-inputs)
- **RPG** (mana, spellbook, status effects)

## What this proves

Every mechanic wired in `src/scenes/Match.ts` already exists in `@engine/mechanics`:
- `ComboAttacks` (spell inputs — from **fighting** scaffold heritage)
- `CameraFollow`, `HUD`, `CheckpointProgression` (from **action** heritage)
- `WinOnCount`, `LoseOnZero`, `Difficulty` (universal)
- *(Would also use `ItemUse` + `StatusStack` + `AttackFrames` — all in the catalog)*

**Zero new mechanic types needed.** This is the assertion the scaffold proves.

## Directory layout

```
magic_hoops/
├── package.json            # engine dep (../../../engine/)
├── tsconfig.json           # @engine alias (three levels up, not two)
├── vite.config.ts          # port 5180
├── index.html              # boot banner labeled "cross-genre canary"
├── src/
│   ├── main.ts             # boots Match scene
│   └── scenes/
│       └── Match.ts        # ONE scene. Mounts 7 mechanics from the catalog.
└── data/
    ├── config.json         # viewport + starting scene
    ├── rules.json          # score_vs_clock cross-genre match format
    ├── arena.json          # court boundary + goals + ball config
    ├── characters.json     # 2 wizards with Health + Mana + Spellbook
    └── spells.json         # 6 spells using fighting-notation inputs (236+A etc.)
```

## Running

```bash
npm install
npm run dev  # localhost:5180
```

## Architecture canary result

See `scaffolds/.claude/GAMEDEV_PHASE_TRACKER.md` cycle 8 for the verdict:
whether this scaffold built clean on first try determines whether the
abstractions are correctly factored.

If this needs NEW Layer 1 components or Layer 2 mechanics to compose, go
fix those abstractions — not this scaffold.
