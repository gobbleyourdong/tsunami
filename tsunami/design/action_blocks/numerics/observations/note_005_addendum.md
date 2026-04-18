# Addendum to note_005 — 4th implicit assumption (**REVISED** per note_012)

**Source:** prompt_026 MMO is impossible; also violates an assumption
that note_005 didn't name.

> **REVISION 2026-04-17:** operator clarified the engine provides
> multiplayer wiring at system level. Local multiplayer is NOT
> out-of-scope. See `note_012` for the full correction. The assumption
> below is RETAINED but narrowed: it applies to *networked* multiplayer
> (server-authority), not *local* (couch co-op / split-screen).

**Claim (narrowed):** v0 makes a 4th implicit assumption:

> **4. Client-local runtime.** The design script is agnostic about
> player count; the engine handles input routing for N local players.
> Networked / server-authoritative multiplayer (MMO, matchmaking,
> cloud saves) remains out-of-scope — that requires infrastructure
> beyond the WebGPU browser client.

This is violated by: MMOs (prompt_026), most online multiplayer,
cloud-save-dependent games, games with web leaderboards. Single-
session-local is cheaper to define than the runtime it implies — a
design script doesn't need to care about it, but a *networked* game
adds massive authoring surface (server tick, anti-cheat, latency
compensation, persistence authority).

**Recommended addition to note_005's table:**

```
| 4 | Single-session local     | one device, no network, no server authority |
```

Violating games:
- MMOs — needs server + shared world (v5+)
- Online multiplayer (Counter-Strike, Quake) — server-auth FPS (v3+)
- Asynchronous multiplayer (Words With Friends) — cloud state sync
- Social mobile (FarmVille, clash games) — continuous server polling

**Relaxation path for v1/v2:**
- `local_multiplayer: true` flag (split-screen, same-device) — v2
- Full networked multiplayer — v3+, requires server architecture

**Cost framing:** adding local multiplayer is a schema flag + input-
routing layer (~200 lines). Adding networked multiplayer is a
greenfield architecture task (~thousands of lines + protocol design).
Note the difference so future scoping is honest.

**Doesn't change v1 top-5.** Just documents the limit cleanly so the
agentic authoring doesn't try to emit design scripts for Counter-
Strike.
