# Game 029 — Oregon Trail (1971 mainframe / 1985 Apple II re-release, etc.)

**Mechanics present:**
- Text-and-simple-graphic narrative of 2,000-mile journey — adventure-narrative shell
- Daily game-time advance (miles traveled per day) — `Calendar` / DayNightClock with day ticks
- Resource management (food, ammo, wagon parts, money, health) — **Resource (v1)**, multi-track
- Random events (snake bite, broken wheel, fording river) — RandomEvent (noted)
- Decision points with consequences (ford/caulk/ferry a river) — DialogTree / choice points (v1)
- Hunting mini-game (move cursor, shoot deer/buffalo) — EmbeddedMinigame (v1)
- Death mechanic (ANY party member can die; named gravestones) — LoseOnZero per-party-member with narrative consequence
- Pace / rations tradeoff (steady/strenuous × filling/meager) — `GameplayDial` control: player-tuned per-tick modifiers
- Multiple player "party" members (family) — narrow Party (noted)
- Educational framing (western history) — not mechanical, content
- Game over at arrival (win) or all-dead (lose) — WinOnCount + LoseOnZero
- Score tabulation on win (rewards efficient travel) — score-on-finish

**Coverage by v0 catalog:** ~3/12

**v1 candidates from this game:**
- All v1 already noted: Resource (multi-track), RandomEvent, DialogTree, EmbeddedMinigame, Party, Calendar
- `GameplayDial` — player-tuned tradeoff slider (pace × rations, attack × defense, risk × reward). Small primitive; enables strategy-layer choices in otherwise-linear gameplay. Seen in: driving sim pace, war games stance, Oregon Trail rations. Worth flagging.

**Signature move:** **tradeoff dials as strategic layer**. No direct combat, no avatar control — just daily decisions that compound. A game that's almost entirely resource management and random events, but engaging because the dials have clear cost/benefit that players must tune against their specific run state. Confirms that "sim" doesn't need 3D physics — a menu-driven sim with good tradeoff dials + random events is fun (see also: classic text-based sims, survival games).

**Genre note:** Oregon Trail is the origin of "edutainment" but mechanically is a *journey sim with random events + tradeoff dials*. Same shape as: FTL (modernized OregonTrail in space), Reigns (swipe-based tradeoffs). Niche but robust genre family. Expressible with Calendar + RandomEvent + Resource + EmbeddedMinigame — all v1.
