# Prompt 005 — Street Fighter-style 2D fighter

**Pitch:** two fighters face off; health bars; rounds (best of 3); special moves via input combos; blocks reduce damage.

**Verdict:** **expressible but incomplete**

**Proposed design (sketch):**
- archetypes: `fighter_A`, `fighter_B` — both with Health, distinct move lists
- mechanics: `ComboAttacks` (wraps engine's ComboSystem — already present), `HUD` (dual health bars), `LoseOnZero` (round loss), `WinOnCount` (best-of-3), `StateMachineMechanic` (animation states: idle/walk/block/attack/stunned/ko)

**Missing from v0:**
- **Round-based flow** — best-of-3 with inter-round reset. v0 flow is single-pass. Need `RoundManager` mechanic: reset state, preserve round tally, advance on round-loss condition.
- **Frame data** — attacks have startup/active/recovery frames. Hit during recovery → punish. This is fighting-game-specific but *without* it the genre evaporates. Needs `AttackFrames` spec on Action Block definitions.
- **Hitbox/hurtbox separation** — collision geometry distinct from physics body. v0 has one body per entity.
- **Super-meter / resource buildup** — landing hits → meter fills → spend on specials. No `Resource` component beyond Health/Score/Lives.
- **Block stun vs. hit stun** — two distinct stunned-states with different recovery semantics.

**Forced workarounds:**
- Encode frame data as component strings `"Attack(8,4,12)"` — hack but readable.
- Dual health bars via HUD with two archetype refs — works, trivial.

**v1 candidates raised:**
- `RoundManager` — preserves state across scene-like sub-rounds; wins_needed param
- `AttackFrames` (Action Block metadata) — startup/active/recovery + damage + on-block + on-hit
- `Hitbox` / `Hurtbox` components — geometry independent of physics body
- `Resource` generic component — parameterized name, max, regen rate, events on change
- `StunState` as part of StateMachineMechanic vocabulary — hit/block/grab/ko distinct

**Stall note:** fighting is frame-data territory. Without frame-accurate attack definitions, the output won't feel like a fighter. This is the hardest genre in this batch to express at design-script level without domain-specific primitives.
