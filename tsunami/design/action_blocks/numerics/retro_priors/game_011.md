# Game 011 — The Secret of Monkey Island (1990, PC)

**Mechanics present:**
- SCUMM verb × noun × noun interface — **not in v0**
- Cursor-driven point-and-click — **not in v0**
- Hotspots with context-sensitive actions — **not in v0**
- Dialogue trees with branching choices — **not in v0**
- Inventory with item-combining — **not in v0**
- Per-room fixed backgrounds — **not in v0**
- Puzzle state as persistent world flags — **not in v0**
- Insult sword fighting (dialogue-as-combat, pattern-matched) — **not in v0** (interesting case: input is dialogue choice, "hit" is correct response)
- Scoring via puzzle progress (not visible — internal progress tracker) — partial (Score component close)
- Multi-act narrative structure — **not in v0** (`Act` / `NarrativeChapter`)
- Ship voyage between islands (graph nav) — **not in v0** (`WorldMap`)
- No lose condition (can't die) — structural: v0 assumes LoseOnZero or similar

**Coverage by v0 catalog:** ~0/12

**v1 candidates from this game:**
- `PointerController`, `HotspotMechanic`, `DialogTree`, `InventoryCombine` — all noted in prompts 006, 011, 014
- `WorldFlags` — world-state tuple
- `NarrativeChapter` — multi-act progression
- Dialogue-as-combat (duel mechanic) — niche but echoes ComboAttacks

**Signature move:** insult sword fighting — dialogue trees repurposed as combat. Low-cost content (lines of text), high engagement. A game mechanic where the UI is the same as the adventure-interaction UI but in a combat frame. Notable for what's ABSENT: no twitch skill, no resource, no damage model — just pattern-match-and-respond.
