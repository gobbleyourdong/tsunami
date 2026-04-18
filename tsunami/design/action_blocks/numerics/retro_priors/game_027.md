# Game 027 — Phoenix Wright: Ace Attorney (2001 JP / 2005 EN, GBA/DS)

**Mechanics present:**
- Visual novel skeleton (bg + character + dialogue box) — partial (dialogue subset, v1)
- Story-driven cases with investigation + trial phases — multi-phase flow
- Investigation phase: point-click Hotspot (interview NPCs, examine scenes) — v1 candidates (noted)
- Evidence collection — Inventory with item descriptions
- Trial phase: cross-examination (press statements, present contradictory evidence) — **EmbeddedMinigame over DialogTree + WorldFlags matching**
- Penalty bar (wrong answers reduce it; zero → game over) — Health → LoseOnZero, named `Penalty`
- Multiple cases forming a larger arc — LevelSequence → NarrativeChapter
- Save anywhere (convenience) — persistent save (gap)
- Music cues per character / situation — audio event bank
- Objection button (evidence-present action) — specific UI + DialogTree gated action
- Psyche-Locks (later games: present items to shatter mental blocks) — DialogTree + Inventory + boolean puzzle
- No fail state within a case aside from Penalty — constrained LoseOnZero

**Coverage by v0 catalog:** ~2/11

**v1 candidates from this game:**
- All already noted: DialogTree, WorldFlags, HotspotMechanic, EmbeddedMinigame, Inventory (with descriptions = LoreEntry variant), LevelSequence, NarrativeChapter, EndingBranches
- `ContradictionMatch` — specific mini-mechanic: current dialogue statement × presented evidence → match or penalty. Specific instance of WorldFlags-gated DialogTree branching.

**Signature move:** cross-examination as a **structural mini-mechanic inside a larger dialogue flow**. This is the canonical case for note_006 `EmbeddedMinigame` — the outer game is "read the story", the inner game is "match statement to evidence." Same mechanics (DialogTree + WorldFlags + Inventory) but a different loop. Player-facing it feels like a different game mode; author-side it's a mechanic suspension/resumption.

**Composition win:** Phoenix Wright is expressible as
`DialogTree` (v1) +
`WorldFlags` (v1) +
`Inventory` with descriptions +
`EmbeddedMinigame` (v1) wrapping a ContradictionMatch sub-mechanic +
`LoseOnZero` on a Penalty resource +
`NarrativeChapter` flow.

All v1 candidates. This is a test-case for the method: if v1 ships the
top-10, Phoenix Wright should be authorable from a design script. Good
milestone to aim for.
