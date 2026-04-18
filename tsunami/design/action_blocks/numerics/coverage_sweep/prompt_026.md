# Prompt 026 — MMO RPG (EverQuest / WoW-style)

**Pitch:** persistent shared world; many players on one server; character classes with skills; quests from NPCs; leveling via combat XP; guilds; auction house; raids.

**Verdict:** **impossible (violates note_005 #2 single-protagonist AND persistence-scale)**

**Proposed design (sketch):** N/A — MMOs require:
- Server authority + client rendering split (not a schema concern; architectural)
- Many-concurrent-players with shared state (totally absent)
- Persistent world across months/years (session-scale v0 is the opposite)
- Economy between strangers (auction house)
- Raid coordination (20+ player synchronization)

**Missing from v0:** everything. MMOs are a different category of software — they're distributed systems first, game mechanic second.

**Forced workarounds:** none. Even the single-player client for an MMO (what the player sees) depends on a server the schema doesn't describe.

**v1 candidates raised:** none reasonable. An MMO extension would be v5+.

**Stall note:** MMO joins RTS, IF, Team Sports, TBS, Deckbuilder as fundamentally out-of-v1-scope. Document: **v0 targets single-player local games.** Multiplayer networking is architecture, not mechanic. Flag in note_005 as an additional implicit assumption (#4 single-session local).

**For the design track:** bump note_005 to add assumption #4 explicitly. I'll draft an addendum.
