---
applies_to: [gamedev]
mood: reactive, execution-heavy, frame-data-aware, spectator-legible
corpus_share: 6
default_mode: dark
anchors: street_fighter_ii, mortal_kombat, tekken_3, super_smash_bros_melee
default_mechanics: [AttackFrames, ComboAttacks, HUD, StateMachineMechanic, StatusStack]
recommended_mechanics: [BossPhases, DialogTree, PickupLoop, WinOnCount, LoseOnZero, ChipMusic]
would_falsify: if a fighter delivery tagged with this genre ships without per-move frame data (AttackFrames with startup/active/recovery) OR lacks a health bar (HUD with HP visualization), OR the two combatants don't occupy a single shared stage, the genre directive was ignored — measured via mechanic adoption probe for AttackFrames + ComboAttacks AND shared-stage topology in scene definition
---

## Pitch

Two combatants, one stage, best-of-three. The core verb is HIT — with
the right frame timing and the right follow-up. Inputs map to moves;
moves have windup → active → recovery windows; mid-move cancels create
combos; block is a dedicated state; the round ends when HP hits zero.
SF2 1991 defines the 2D template; Mortal Kombat 1992 adds fatalities
and digitized actors; Tekken 3 1997 moves to full 3D with FightingStance3D;
SSBM 2001 reframes as platform-fighter with knockback %.

## Mechanic set (anchor examples)

1. `AttackFrames` — per-move startup/active/recovery windows, damage,
   hitbox, hurtbox, cancel rules.
2. `ComboAttacks` — input sequences that trigger cancel/chain moves;
   JuggleCombo as a sub-mechanic.
3. `HUD` — health bars (top-screen), super meter, round counter, timer.
4. `StateMachineMechanic` — per-fighter states: idle / walking /
   jumping / attacking / blocking / hitstun / KO.
5. `StatusStack` — effects like stun, knockdown, counter-hit, chip-
   damage tracking.
6. `WinOnCount` — best-of-N rounds (usually 3).
7. `LoseOnZero` — HP=0 ends round.
8. `ChipMusic` — stage music (fighter soundtracks are a selling point).
9. `DialogTree` — arcade-mode narrative between fights (pre/post
   match win quotes, story endings).
10. `PickupLoop` — items in platform-fighters (Smash) — genre variant.

## Common shape

- **Fighter count**: 8-20 unique characters with per-character moveset
  (`CharacterMoveset`).
- **Stage count**: 4-12 stages, each with a shared-playfield shape.
- **Round structure**: best-of-3 rounds, each ~30-90s; sudden death on
  time-out.
- **Fail state**: HP=0 (round), 2 rounds lost (match).
- **Progression curve**: Arcade mode through 8-10 opponents ending in
  boss; unlock characters; vs. mode for local multiplayer (`LocalVersus`).
- **Control**: 4 face buttons (light/medium/heavy punch or kick; or
  weak/strong attack + block + special in some); d-pad/stick for
  movement; motion inputs (QCF+P for fireball).

## Non-goals

- NOT a beat-em-up (use `beat_em_up` — side-scrolling, crowd combat
  rather than 1v1).
- NOT an action game (use `action_adventure` or `hack_and_slash` —
  single-player progression vs. PvP round-based).
- NOT a shooter (use genre-specific shooter — projectiles as primary
  vs. melee primary).
- 2D-fighter vs. 3D-fighter vs. platform-fighter are sub-variants;
  the top-level `fighter` directive applies to all three.

## Anchor essences

`scaffolds/.claude/game_essence/1991_street_fighter_ii.md` —
**modern fighter canonical**. `FightingStance2D`, `MultiButtonStrike`,
motion inputs, character moveset idiom.

`scaffolds/.claude/game_essence/1992_mortal_kombat.md` —
digitized sprites, `FinisherMechanic` (Fatality), `SecretUnlock`
(Reptile). Defines the gore/spectacle axis.

`scaffolds/.claude/game_essence/1997_tekken_3.md` —
3D fighter canonical. `FightingStance3D`, `MatchupPreScene`,
`ChipDamage` on block. `BrawlerCombat3D`.

`scaffolds/.claude/game_essence/2001_super_smash_bros_melee.md` —
platform-fighter variant. `PercentKnockback` instead of HP bars.
`PlatformFighterStage`, `StageSpawnItems`.

## Pitfalls the directive is trying to prevent

- Wave treats combat as "click enemy to attack" — fighters REQUIRE
  per-move frame data. A punch with no startup/active/recovery
  windows is an RPG attack, not a fighter attack.
- Wave skips block as a dedicated state — blocking in fighters is a
  held-back-direction state that converts hits to chip damage. Without
  it, the game reduces to DPS race.
- Wave doesn't model two shared-stage combatants — a fighter is
  ALWAYS 1v1 on one shared playfield. If entities are on separate
  screens, it's a different genre.
- Wave omits round structure — best-of-3 (or best-of-5) rounds is
  the genre's pacing primitive. Single-life fights are skip-the-loop.
- Wave invents motion inputs without ComboAttacks — QCF+P, DP+K, etc.
  are table-driven cancels; use `ComboAttacks` with input-sequence
  params, don't hardcode in switch statements.
