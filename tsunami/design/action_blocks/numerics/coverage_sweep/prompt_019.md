# Prompt 019 — Visual novel (Phoenix Wright / Clannad-style)

**Pitch:** text boxes + character sprites + background art; occasional choices branching the story; stat tracks affecting endings; sometimes mini-game inserts (Phoenix Wright cross-examination).

**Verdict:** **awkward → expressible with dialogue subset (note_001 option C)**

**Proposed design (sketch):**
- archetypes: `character_sprite_*` (pose/expression variants), `background_*` per scene, `player` (invisible — no spatial entity)
- mechanics: `DialogTree` (top-3 v1 candidate), `WorldFlags` (story state), `EndingBranches` (endings by accumulated flags), `HUD` (dialogue box overlay), `HotspotMechanic` (Phoenix Wright: click to examine/present)

**Missing from v0 (but addressable via dialogue subset):**
- **Character sprite swap** — expression/pose changes mid-dialogue. Archetype has multiple visual states; state-driven sprite selection. Overlaps with `StateMachineMechanic` if generalized.
- **Background transitions** — scene bg changes without full scene change. `BackgroundLayer` sub-archetype.
- **Dialogue with player choice points** — `DialogTree` with `choice_node` type.
- **Relationship stats affecting endings** — integer counters on player per-NPC.
- **Cross-examination (Phoenix Wright)** — text with contradictory-evidence branching. Dialogue + WorldFlags suffices.
- **Day/phase scheduling** (Clannad): calendar-driven scene availability — overlaps `DayNightClock` + `WorldFlags`.

**Forced workarounds:**
- Treat each dialogue scene as a flow step — verbose (hundreds of steps for a full VN). A `DialogScript` primitive that plays a sequence inline would be more compact.

**v1 candidates raised:**
- `DialogScript` — play sequence of (speaker, pose, line, [choice]) tuples as a single mechanic; compiles to engine dialog calls
- `CharacterSprite` archetype spec with pose/expression state list
- `BackgroundLayer` — non-entity visual asset swap
- `RelationshipCounter` component (generalizes to Sims need bars)
- `EndingBranches` — already noted (Chrono, RE) — scoring over `WorldFlags` → terminal scene

**Stall note:** VN is MUCH closer to expressible than IF (prompt_006) despite surface similarity. The difference: VN has spatial bg-character-dialogue rendering that maps to archetypes-in-scene; IF has pure state-graph. VN works via the narrow dialogue subset (note_001 option C). Option-(C) defense: this genre alone justifies the subset.
