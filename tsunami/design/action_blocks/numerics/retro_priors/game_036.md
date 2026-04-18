# Game 036 — Shenmue (1999, Dreamcast)

**Mechanics present:**
- 3D over-shoulder exploration (topdown/3rd person) — partial
- Real-time clock (game world runs on real hours; events happen at specific clock times) — DayNightClock ✓ (exercised!) + Calendar variant
- NPCs with daily schedules (work, lunch, go home) — UtilityAI ✓ (Sims-adjacent) with scheduled behavior
- Dialogue with most NPCs (flavor + occasional clue) — DialogTree (v1)
- QTE combat (quick-time events during action sequences) — **`QuickTimeEvent`** — specific-timed-button-prompt mechanic
- Open-world investigation (ask around to progress story) — WorldFlags (v1) + Hub (RoomGraph)
- Side activities (arcade machines, capsule toys, job, forklift racing) — EmbeddedMinigame ✓ (many — confirms note_006)
- Collectible capsule toys — PickupLoop variant
- Playable classic Sega arcade games — **literal EmbeddedMinigame** containing a different game wholesale
- Currency (yen) + shops — Resource + Shop ✓ (v1)
- Save at specific points — CheckpointProgression ✓
- Progression gated on date-in-game-time — Calendar-gated flow
- Fighting system (kung fu moves via ComboAttacks) — ComboAttacks ✓

**Coverage by v0 catalog:** ~3/14

**v1 candidates from this game:**
- **`QuickTimeEvent`** — not previously noted; specific to cinematic action sequences. Timed button prompt with success/fail branches. Also seen in: God of War, Heavy Rain, Shenmue-descendants.
- Strong DayNightClock exercise — Shenmue and Animal Crossing are the two canonical real-time-clock games.
- Strong EmbeddedMinigame exercise — arcade games inside Shenmue are literal separate games. Confirms note_006 as high-value.

**Signature move:** **world that runs whether you're watching or not.**
Shenmue's real-time clock + NPCs with schedules creates the feeling
that Yokosuka exists outside the player's attention. Mechanical
primitive is simple (DayNightClock + UtilityAI with schedules); the
genre-defining effect emerges from combination. 6th emergence-thesis
confirmation.
