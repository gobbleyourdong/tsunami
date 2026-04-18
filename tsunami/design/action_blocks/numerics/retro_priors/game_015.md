# Game 015 — The Sims (2000, PC)

**Mechanics present:**
- Individual NPC needs (hunger, bladder, comfort, hygiene, social, fun, energy, room) — **not in v0** (`NeedsBars` multi-resource per NPC)
- Autonomous behavior when not directed (sim chooses action to satisfy lowest need) — **not in v0** (`UtilityAI`)
- Player issues queued commands to sims — same selection problem as RTS (prompt_012), narrower scope
- Build mode (place walls, doors, floors) — **not in v0** (`GridPlayfield` editor + placement rules)
- Buy mode (purchase furniture with money) — **not in v0** (Budget + catalog)
- Object-provided interactions (fridge has "grab snack", TV has "watch") — **not in v0** (`InteractableObject` with action menu)
- Time-of-day simulation (work hours, school, sleep) — partial (DayNightClock close; multi-person schedules missing)
- Career progression — partial (XPLeveling-close, but with job levels and promotion conditions)
- Relationship graph between sims — **not in v0** (`RelationshipGraph` — mentioned in farming sim)
- Mood modifiers from environmental quality — **not in v0** (`AmbientModifier`)
- Open-ended (no win condition) — same as SimCity 2000 structural gap
- Save/load multi-session persistence — persistent save gap confirmed again
- Expansion packs adding mechanics via patching — meta-mechanic (modularity)

**Coverage by v0 catalog:** ~0/13

**v1 candidates from this game:**
- `NeedsBars` — multi-dimensional resource per archetype (generalizes Resource)
- `UtilityAI` — action selection via utility score over needs (distinct from BT / FSM)
- `InteractableObject` — archetype-attached action menu ("what can I do with this?")
- `RelationshipGraph` — per-pair NPC state
- `BuildMode` editor — player-authored archetype placement in-game
- `CareerLadder` — XP + level with step-gated promotion conditions

**Signature move:** autonomous utility-AI sims. You can put them in a house, walk away, watch them live. The game plays itself if you let it. Distinct from every other game in the corpus — no win, no explicit goal, player engagement from watching emergence. `UtilityAI` is the mechanical key; it's the same shape idea as Pac-Man's "4 AIs over 1 maze" (heterogeneous agents produce emergence) but with the player as observer, not protagonist.

**Structural gap confirmed:** v0 assumes player-as-protagonist + win-or-lose flow. Sims/sandbox games have neither. A `SandboxMode` flag (like `GridMode`) that disables `LoseOnZero`/`WinOnCount` requirements might be needed; flow becomes optional.
