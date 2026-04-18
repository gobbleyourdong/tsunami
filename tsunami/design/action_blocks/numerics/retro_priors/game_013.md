# Game 013 — Metal Gear Solid (1998, PS1)

**Mechanics present:**
- Stealth-action core (sneak past guards) — **not in v0** (detection cones, perception model)
- Radar showing guard vision cones — **not in v0** (HUD variant tied to VisionCone)
- Alert / Evasion / Caution states (global) — **not in v0** (`AlertState` timed)
- Codec calls (radio dialogues) — partial (Dialog close; scripted-contact triggers missing)
- Boss battles with unique mechanics (Psycho Mantis controller swap, Ocelot revolver reloads) — partial (`BossPhases` close; boss-unique input remap missing)
- Cardboard box disguise — **not in v0** (`DisguiseItem` — equip to flip detection rules)
- Item inventory + weapon inventory (separate) — partial (Inventory)
- Ration + healing — partial (PickupLoop close)
- Save via Codec call (meta-fiction save) — not a mechanic, but flags: save-point variant (see RE)
- Ladders / climbing — **not in v0** (`ClimbableSurface`)
- First-person aim mode via button-hold — **not in v0** (`AimModeToggle`)
- Voice acting + cinematic cutscenes — partial (cutscene/intermission support gap)
- Stealth-kill (behind-back takedown) — **not in v0** (directional stealth attack; cousin of note_003 directional contact)
- Hiding bodies — **not in v0** (`CarryRelationship` — prompt_013)
- Boss rematch differences (alert vs. sneak) — complex flow state

**Coverage by v0 catalog:** ~2/15

**v1 candidates from this game:**
- Confirms prompt_013 list: `VisionCone`, `AlertState`, `CarryRelationship`, `CoverBinding`
- Adds: `AimModeToggle` (controller-mode transient switch), `ClimbableSurface`, `DisguiseItem`, boss-unique input remap
- Codec / scripted-contact triggers (scripted events on named trigger keys) — a `ScriptedEvent` mechanic

**Signature move:** the boss fights defying the conventional combat model (Psycho Mantis reading your memory card, Sniper Wolf requiring the sniper rifle, The End as real-time exploration-hunt). Each boss has a DIFFERENT sub-mechanic. v0's `BossPhases` handles phased-AI-swap bosses; MGS-style bosses require per-boss mechanic composition — which is exactly what the design-script method enables IF the catalog has enough primitives. Encouraging: the method's expressive ceiling scales with catalog size, and MGS-likes are reachable once stealth primitives land.
