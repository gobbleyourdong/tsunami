# Game 014 — Resident Evil (1996, PS1)

**Mechanics present:**
- Fixed pre-rendered camera per room — **not in v0** (CameraPresets — prompt_014)
- Tank controls (rotate + forward/back relative to facing) — **not in v0**
- Pre-rendered backgrounds with polygonal characters — not a mechanic (rendering choice)
- Inventory with slot limits (6 / 8 with vest) — **not in v0** (InventorySlotLimit)
- Item combining (herbs: G+G=heal more, G+R=cure poison) — **not in v0** (InventoryCombine)
- Item examining (rotate key in inventory to find clue) — **not in v0** (`ExamineMode`)
- Save typewriter + ink ribbons (limited saves) — **not in v0** (ResourceGatedAction — prompt_014)
- Documents / files (lore readables) — **not in v0** (LoreEntry)
- Door-loading screens (hide loads) — not a mechanic; engine-level
- Ammo scarcity + multiple gun types — partial (Inventory close, scarcity absent)
- Zombies, Hunters, Cerberus (typed enemies with distinct AI) — partial (ai: chase + BT library gap)
- Key items (shield key, helmet key) unlocking specific doors — ✅ `LockAndKey`
- Crank / valve puzzles (USE item ON world object) — **not in v0** (Hotspot+ItemUse)
- Two playable characters with different item availability (Chris/Jill) — **not in v0** (`CharacterSelect` at start flow)
- Multiple endings — **not in v0** (EndingBranches)
- S-rank / speedrun reward (unlockable weapons) — **not in v0** (`PostRunUnlock`)

**Coverage by v0 catalog:** ~1/14

**v1 candidates from this game:**
- Confirms prompt_014 list
- Adds: `ExamineMode` (in-inventory 3D object inspection — niche)
- `CharacterSelect` (pre-game archetype choice flow)
- `EndingBranches` (multi-ending flow)
- `PostRunUnlock` (persistence across runs — same shape as NewGame+)

**Signature move:** scarcity as a mechanic. Limited ammo, limited saves, limited inventory slots TOGETHER create constant resource tension. Not one mechanic — a *combination* of three. The method's emergence thesis (small catalog × composition = large space) is directly supported here: v1 could add 3 mechanics and get survival horror basically for free.
