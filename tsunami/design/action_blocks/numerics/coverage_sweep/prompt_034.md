# Prompt 034 — God game (Populous / Black & White-style)

**Pitch:** you are a god; villagers pray to you; you cast miracles (rain, fire, earthquake) at cursor location to help or hurt; villages grow and follow; alignment (good/evil) via acts.

**Verdict:** **awkward (hybrid sim + cursor magic; close with v1 bundle)**

**Proposed design (sketch):**
- archetypes: `villager` (simple AI), `village` (growth archetype), `miracle_*` (cast-at-cursor effects)
- mechanics: `Resource` (mana/belief — v1), `HotspotMechanic` / `PointerController` (cursor aim — v1), `MiracleCast` (spend Resource → trigger ActionRef at cursor pos), `UtilityAI` (villagers — Sims), `AlignmentAxis` (good/evil meter — `ReputationGraph` variant), `RandomEvent` (weather, disasters), `HUD`, `SandboxMode` (v1 — no single lose condition; long-form progression)

**Missing from v0:**
- **Point-and-cast aim** — cursor-based ActionRef dispatch. Overlap with Light-gun AimCursor (prompt_027) and adventure HotspotMechanic.
- **Villager village growth** — Resource accumulation (population) tied to environmental inputs (food, faith). Multi-resource flow (like SimCity).
- **Alignment over time** — each miracle shifts meter; available miracles gated on alignment. `AlignmentGate` = DialogChoice.stat_gate for action selection.
- **Creature training (B&W)** — raise a pet that learns from reward/punish feedback. `TrainableAI` — an AI whose BT adjusts based on recorded reinforcement. Probably v2+.

**Forced workarounds:**
- Miracle system as named `HotspotMechanic` actions with Resource cost. Works.
- Village growth as multi-Resource accumulator + spawn rule (pop > X → spawn villager). Decent fit for Resource + WaveSpawner.

**v1 candidates raised:**
- `MiracleCast` / `CursorAction` — cursor-pos-targeted ActionRef with Resource cost. Generalizes Light-gun's AimCursor + adventure's Hotspot.
- `AlignmentGate` — action-availability gated on Resource (reputation) threshold
- `TrainableAI` — adjustable BT via reinforcement (v2+)

**Stall note:** god game is a *cursor-magic + sim hybrid*. v1 top-5 + Resource + PointerController + AlignmentGate gets 80%. TrainableAI (Black & White's signature) is a research-level mechanic — keep out-of-v1.
