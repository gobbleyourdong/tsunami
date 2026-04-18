# Game 020 — Final Fantasy VI (1994, SNES)

**Mechanics present:**
- Overworld exploration (topdown) — partial (topdown)
- Turn-based ATB combat — **not in v0** (same as Chrono; `BattleSystem` + `ATBGauge`)
- Party management (up to 14 characters, 4 in combat) — **not in v0** (Party mechanic, noted)
- Character classes + unique abilities (Magitek, Runic, SwdTech, Rage) — **not in v0** (AbilitySlot per-character catalog)
- Esper system (equippable summons that teach spells) — **not in v0** (equipment slot with learning/XP)
- Stat growth via esper bonuses — equipment-driven stat progression
- Magic points / MP — **not in v0** (Resource — noted multiple times)
- Status effects (Poison, Sleep, Confuse, Zombie, etc.) — **not in v0** (StatusStack — noted in deckbuilder)
- Weapon/armor/accessory equipment — **not in v0** (Equipment — noted)
- Shops + treasure chests — Shop (noted)
- Dungeons with puzzles + switches — partial (`PuzzleObject` + `LockAndKey`)
- Branching plot with multiple character viewpoints — `NarrativeChapter` + protagonist swap
- Optional sidequests — flow-branching
- World Map Airship (fast-travel) — `FastTravel` mechanic
- Opera House scene (rhythm-adjacent minigame) — mini-game inserts — generic "embedded-mechanic" pattern
- Colosseum (bet items for reward) — `GambleShop` — niche
- Game Over on all party KO — LoseOnZero on party-alive-count (not a single archetype)

**Coverage by v0 catalog:** ~2/16

**v1 candidates from this game:**
- Full RPG stack: `BattleSystem`, `ATBGauge`, `Party`, `AbilitySlot`, `Stats`, `XPLeveling`, `Equipment`, `StatusStack`, `Shop`
- `FastTravel` — non-adjacent scene transition unlocked by flag
- `EmbeddedMinigame` — one mechanic suspends for a different mechanic, then resumes (Opera House, Chrono Robo dance)
- `PartyKOLose` — LoseOnZero with aggregated-field condition (all party Health == 0)

**Signature move:** branching protagonists. The game has ~14 playable characters, some missable, some optional. Each has a unique ability and backstory. The game's emergent narrative depth comes from party-composition × ability × scenario — combinatorics over a finite set. Validates the method's emergence thesis again: small primitive count × composition = large design space.

**Structural finding:** FF6 joins Chrono as a canonical JRPG. Coverage gap is identical. The `BattleSystem` mechanic, if added, would probably unlock 40+% of the JRPG genre at once. Likely single highest-leverage mechanic for the genre. Worth flagging as bundle target for v2.
