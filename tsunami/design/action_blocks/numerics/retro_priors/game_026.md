# Game 026 — NBA Jam (1993, arcade)

**Mechanics present:**
- 2v2 arcade basketball — **not in v0** as team-sport, but simpler than Madden (2 player-characters + 2 AI, not 22)
- Exaggerated arcade physics (players leap 30 feet) — tuning of existing physics, not a new mechanic
- Fire mode (hit 3 consecutive shots → "on fire", next shots are molten) — **not in v0** (`StreakMode` / scoring-dependent state buff — like TimedStateModifier but conditional on chained events)
- Turbo button (spend stamina for speed burst) — ✅ Resource (noted, v1)
- Goaltending / rim-shaking dunks — physics-tuning + animation state, mostly non-mechanic
- 4-player split-screen cabinet — local multiplayer (noted, v2+)
- Character select with stat cards — `CharacterSelect` (noted)
- Hidden codes to unlock characters — `PostRunUnlock` / cheat code (noted)
- Quarters / time limit per half — `LoseOnZero` with Timer resource
- Announcer voice lines tied to events — scripted audio event bank

**Coverage by v0 catalog:** ~2/10

**v1 candidates from this game:**
- `StreakMode` — conditional state buff after N-in-a-row (distinct from TimedStateModifier; event-condition-triggered)
- Scripted audio event bank — contextual voice clips tied to state changes
- 2v2 as narrow team-sport case — 4 controlled archetypes instead of 22. Maybe expressible as `ArchetypeControllerSwap` between teammates rapidly.

**Signature move:** fire mode. 3 made shots → next shots are untouchable + rim shakes. One mechanic converts a comfortable lead into a runaway blowout, giving each quarter a "can I get back in the fire?" subplot. A tight composition: WaveSpawner-style accumulator (shot counter) + TimedStateModifier (fire window) + ScoreCombos (multiplier). The three existing primitives almost express it; the catch is the *event-condition trigger* (3 shots made → activate) versus time-window trigger. `StreakMode` as primitive is 30 lines of code but produces a signature mechanic. Another emergence-thesis confirmation.

**Genre note:** 2v2 is narrower than Madden's 11v11 and much closer to v1 reach. Arcade sports (NBA Jam, NFL Blitz, Arch Rivals) are not the same category as sim sports (Madden, FIFA). Worth flagging — v1 can target ARCADE sports; sim sports stay out-of-scope.
