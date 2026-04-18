# Observation 012 — Multiplayer correction; note_005_addendum was overscoped

**Source:** operator input 2026-04-17 — *"re:mario party, remember the
system provides. their system provides."*

**Claim:** note_005_addendum ("v0 assumes single-session local — no
network play") is too broad. **The engine/runtime provides multiplayer
wiring as a system-level concern.** The design-script schema doesn't
need to author player-count / input-routing / split-screen — the
engine already handles it.

**Implication:**
- **Local multiplayer (Mario Party, Smash, split-screen racers, couch
  co-op) moves back into v0-scope.** The design script just declares
  N players; engine routes inputs per player and renders accordingly.
- **Networked / online multiplayer (MMO, Counter-Strike) remains likely
  out-of-scope** — that requires server-side infrastructure beyond a
  web-first WebGPU client. Unconfirmed; operator may clarify further.
- **Mario Party (prompt_036) verdict revised:** from "impossible
  (multiplayer out-of-scope)" → "awkward → expressible with
  `BoardMovement` + `MinigamePool` v1 candidates, multiplayer handled
  by engine."

**Revision to note_005_addendum:**

The 4th assumption should NOT be "single-session local." That was my
over-extrapolation from one prompt (MMO). The correct framing is:

> **4. Client-local runtime.** The design script describes *what* the
> game does; the engine handles *who* plays (single or multi). Local
> multiplayer is a runtime feature; the schema is player-count-
> agnostic unless a mechanic explicitly targets per-player state.
>
> Networked multiplayer (MMO, server-authoritative) is still out-of-
> scope in v0–v2 because it requires server infrastructure beyond the
> WebGPU client runtime. But this is about *where the game runs*, not
> about *what the schema describes*.

**Updated impossible-set (v0):**
- Zork (IF schema mismatch — #2 single-protagonist + #3 spatial violated)
- StarCraft (RTS — multi-unit control + selection)
- FE Tactics (turn-based + grid, violates #1 real-time)
- Deckbuilder (turn-based + card-mode)
- Madden sports sim (multi-unit + persistence depth)
- MMO (server-side multiplayer authority, #4 client-local)
- Western CRPG (real-time-with-pause + RPG stack depth)

**Removed from impossible-set:**
- Mario Party (multiplayer alone isn't the blocker; BoardMovement +
  MinigamePool v1 primitives are)
- **Possibly Smash** (platform fighter, prompt_035) — already was
  "expressible but incomplete"; multiplayer concern was partial. Now
  purely a primitive-completeness question.

**Impact on gap_map rankings:** limited. Multiplayer wasn't blocking
the top-5 v1 candidates. The correction upgrades one prompt from
impossible to expressible-with-v1 and revises one assumption. Ranks
unchanged; impossible-set shrinks from 8 → 7.

**Method lesson:** Sigma "Priors Don't Beat Source" applies to me too.
I inferred "MMO impossible → single-session-local assumption" without
confirming the engine's runtime capabilities. The engine provides more
than I assumed. The fix is to check the source (or the operator) before
codifying an assumption. Noted for future over-generalization
tendencies.
