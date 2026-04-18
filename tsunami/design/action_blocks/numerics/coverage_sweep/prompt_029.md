# Prompt 029 — Dating sim (Tokimeki Memorial / Stardew Valley relationship-layer)

**Pitch:** 3 years of in-game time; balance school / club / social; date potential partners; stats (intelligence / charm / fitness) grow from activities; unlock endings per partner via affection thresholds; calendar-driven events.

**Verdict:** **awkward → expressible with NeedsBars + RelationshipGraph + calendar**

**Proposed design (sketch):**
- archetypes: `player` (no spatial body — stat container), `potential_partner_*` (affection counter, dialogue), `activity_location_*` (clickable, produces stat gains)
- mechanics: `DayNightClock` ✓ (v0 — drives calendar), `Calendar` (scheduled events on day-X), `ActivitySelect` (menu of daily actions), `StatGrowth` (each activity += stats), `RelationshipGraph` (per-partner affection), `DialogTree` (v1), `EndingBranches` (v1), `HUD`

**Missing from v0:**
- **Calendar** — date-based scripted events. Generalization of DayNightClock to date-indexed event list.
- **Daily action selection** — player picks 1-2 activities per day; activity granularity = day. Low-frequency tick.
- **Stat growth per activity** — each archetype-contact += stat. Simpler than XP systems but similar.
- **Affection counter per partner** — `RelationshipGraph` (Sims, noted).
- **Event triggers on calendar+flags** — "festival on day 30" + "if you asked them out → special event". Calendar × WorldFlags joint trigger.
- **Multiple endings per partner** — EndingBranches variant keyed on RelationshipGraph state at end-of-year.
- **Mini-games inserted as dates** — EmbeddedMinigame (noted) for hoop shoot, fishing date, etc.

**Forced workarounds:**
- Calendar as Difficulty ramp over day count — loses date-specific triggers.
- Daily action as scene-per-day — works but verbose (365+ scenes).

**v1 candidates raised:**
- `Calendar` mechanic — date-indexed event list (extends DayNightClock)
- `ActivitySelect` — menu-style action choice per tick (daily, per-turn)
- `StatGrowth` — reward-on-contact but for archetype-internal stats (generalization of PickupLoop)

**Stall note:** dating sim is *almost* expressible via DayNightClock + RelationshipGraph (v1) + DialogTree (v1) + EndingBranches (v1) + EmbeddedMinigame (v1). The missing piece is day-granularity calendar + action-menu authoring. Small additions, high payoff — 2020s dating/stat-sim/visual-novel scene is vibrant indie territory.

**Composition win:** dating sim layered with EmbeddedMinigame turns into rhythm-dating (Hatoful Boyfriend) or combat-dating (BG3's companion system). The composability is strong. Promotes Calendar to ~top-15 v1 candidate.
