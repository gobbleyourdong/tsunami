# Game 033 — Black & White (2001, PC)

**Mechanics present:**
- God-game view (hover camera over terrain) — CameraFollow variant, free-fly
- Cursor as your hand (pick up villagers, drop them, fling them) — **`PhysicalCursor`** (noted god game; generalizes HotspotMechanic)
- Creature AI that learns from reward/punish feedback — **`TrainableAI`** (noted prompt_034; v2+)
- Alignment (good/evil) visibly affects creature + temple appearance — AlignmentAxis (noted)
- Villages with prayer production (Resource) — Resource ✓ v1
- Miracles (fireball, rain, food) cast at cursor — MiracleCast/CursorAction (noted)
- Creature evolves with training (size, behavior shift) — statedrift
- Sandbox + campaign hybrid — flow + SandboxMode ✓
- Pet-player relationship dynamic — RelationshipGraph variant
- Procedural mission placement via world state — MissionGraph (v1)
- Physical gesture spellcasting (draw glyphs with cursor) — **`GestureRecognizer`** — pattern-match cursor trace against named shapes

**Coverage by v0 catalog:** ~2/11

**v1 candidates from this game:**
- `PhysicalCursor` — generalizes HotspotMechanic + Hand manipulation (pickup/drag/fling)
- `TrainableAI` — reinforcement-adjusted BT (v2+, research-level)
- `GestureRecognizer` — cursor-path → named-pattern matching. Niche but striking; echoes Okami's Celestial Brush.
- AlignmentAxis (confirmed)

**Signature move:** **trainable creature pet**. Lionhead's fame is
based on this one mechanic — the big dog/cow/monkey that watches your
actions and develops behavior. Genuinely novel at time. Still research-
level today: RL with on-policy feedback is hard to productize. If
Tsunami ever wants to emit "games with a companion that feels alive,"
this primitive needs external ML infrastructure, not just schema.

**Defer:** `TrainableAI` flagged as *too hard for v1 or v2*. Keep as
aspirational v3+ goal. In the meantime, `FSM-based companion with
affinity changes` (Sims-tier) is the pragmatic substitute.
