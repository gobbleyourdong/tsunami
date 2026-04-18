# Prompt 014 — Survival horror (Resident Evil-style)

**Pitch:** fixed camera angles per room; limited ammo and healing herbs; inventory with slot limits; tank controls; zombies that require multiple hits; save typewriter requires ink ribbons.

**Verdict:** **awkward**

**Proposed design (sketch):**
- archetypes: `player` (tank-controls), `zombie` (slow chase AI), `herb_green/red/blue`, `ammo_pickup`, `document`, `save_typewriter`
- mechanics: `RoomGraph` (not v0), `InventorySlotLimit` (not v0), `FixedCamera` per room (not v0), `LimitedSave` (not v0), `LoseOnZero`, `PickupLoop` (but scarcity, not respawn)

**Missing from v0:**
- **Fixed cinematic camera per room** — each room has a preset camera pose, changes on room transition. `CameraFollow` (noted previously) is follow-based; this is preset-based. New mechanic: `CameraPresets`.
- **Tank controls** — rotate+forward/back relative to facing. Not quite `platformer` or `topdown`. Possibly a variant of existing controllers with a flag.
- **Inventory slot limits** — `Inventory` component exists in v0 but no capacity. Core survival-horror loop is "dropping things you might need." Needs `InventorySlotLimit` mechanic with slot count, drop-on-full semantics.
- **Scarce non-respawning pickups** — `PickupLoop` respawns on timer. RE herbs/ammo are one-and-done. `max_simultaneous: 1` + `respawn_sec: Infinity`? Hack. Better: `PickupOnce` variant.
- **Herb combining (green+red → mixed)** — same as Monkey Island `InventoryCombine`.
- **Save-point-with-resource-cost** — save consumes an ink ribbon. Generic: `ResourceGatedAction`.
- **Document items that add lore entries** — readable items with text. `LoreEntry` mechanic (HUD variant).

**Forced workarounds:**
- Fake fixed cameras with scene-per-room (overkill; Mario-level-style sequencing).
- Scarce pickups by removing from world after collection — requires per-pickup lifecycle flag.

**v1 candidates raised:**
- `CameraPresets` mechanic — per-room camera pose authoring
- `InventorySlotLimit` — component param on Inventory
- `PickupOnce` mechanic (or param on PickupLoop: `respawn: 'never' | 'timer'`)
- `ResourceGatedAction` — generic "consume X to do Y"
- `LoreEntry` / document-archetype HUD integration

**Stall note:** survival horror is arguably expressible if v0 adds 4 mechanics and 1 camera variant. Lower-cost than RTS or IF. Worth a v1 slot because RE-likes are a respectable indie genre in 2026 and the primitives are shared with other genres (slot-limited inventory applies everywhere; `CameraPresets` applies to adventure games too).
