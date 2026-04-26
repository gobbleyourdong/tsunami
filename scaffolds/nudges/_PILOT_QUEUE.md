# Pilot Run Queue — first live ERNIE + Qwen validation

_When ERNIE :8092 + Qwen-Image-Edit :8094 are both up, work through this
queue in order. Each tier is a quantum of validation — don't start the
next tier until the previous tier's outputs look right. The whole queue
is ~60 min of compute on Turbo, zero exotic prompts, all pulled from
sister's canonical-game extraction corpus._

**Owning tooling:** `scaffolds/engine/asset_workflows/_common/batch_run.py`
(for 1D nudge chains) and `.../top_down_character/run_blockout.py` +
`run_animation.py` (for 2D direction × frame blockouts).

---

## Tier 0 — Pipe test (1 min)

Smallest possible validation. One static ERNIE-only payload. Confirms
ERNIE is reachable + output landing path works.

```bash
cd scaffolds/engine/asset_workflows/_common
python3 batch_run.py --apply \
    --essence 1985_super_mario_bros \
    --kind tile \
    --sub-kind level_layout \
    --limit 1
```

**Expected:** 1 ERNIE call (~17s Turbo), one `frame_000.png` under
`./out/bpc/1985_super_mario_bros/<first-matching-anim>/`. Static-disposition.

**Blocks if:** ERNIE down, save_path permission error, tsunami proxy
misrouting.

---

## Tier 1 — Gold-clean 1D chain (5-10 min)

The 7 nudge payloads that cleared `nudge_quality_report.py` with zero
flags. These are the highest-confidence Qwen chain validations.

```bash
python3 batch_run.py --apply \
    --essence 1981_galaga \
    --kind effect_layer \
    --min-nudges 3
```

Will match `1981_galaga/player_explosion` (the canonical 4-frame death
explosion: "small flash → expanding fire cross → scattered debris → fade").
If that one reads as an animation, Tier 2 is unlocked.

The full 7-gold set (fire one-by-one for first pass):

| # | Essence | Animation | Kind | Nudges |
|---|---|---|---|---|
| 1 | `1981_galaga` | `player_explosion` | effect_layer/explosion_vfx | 3 |
| 2 | `1986_castlevania` | `enemy_black_leopard_run` | character | 1 |
| 3 | `1986_castlevania` | `enemy_hunchback_fleaman_jump` | character | 1 |
| 4 | `1986_legend_of_zelda` | `leever_emerge_move` | character | 2 |
| 5 | `1987_castlevania_ii_simons_quest` | `boss_death_reaper` | character/boss | 1 |
| 6 | `1987_castlevania_ii_simons_quest` | `fleaman_jump` | character | 1 |
| 7 | `1987_mega_man` | `dr_light` | character/npc | 1 |

Fire one at a time via direct path:

```bash
python3 base_plus_chain.py ../.claude/nudges/1981_galaga/player_explosion.json --apply
```

**Expected per payload:** 1 ERNIE (~17s) + N Qwen (~80s each on 20-step
karras). A 4-frame animation from the first row should take ~4 min end-to-end.

**Success signals per frame:**
- Frame 0 (ERNIE base): magenta backdrop, single clean sprite, no drift
- Frame 1+ (Qwen nudges): same sprite identity, visible delta matching the
  nudge description, no collapse to generic

---

## Tier 2 — Strip assembly + engine-loadable output (2-3 min post-Tier-1)

After Tier 1 produces per-payload `frame_*.png` files, assemble them
into canonical N×1 strips the engine's sprite-loader can ingest.

```bash
python3 strip_assembler.py ./out/bpc/ --recurse
```

**Expected:** `strip.png` + `strip.manifest.json` per-payload dir.
Re-running is idempotent (skips when mtimes already ordered correctly).

---

## Tier 3 — Dragon Quest identity-preservation test (~35 min)

The flagship test. Sister's Dragon Quest extraction has 6 armor-tier
versions of the Hero — same character, differing only by equipment.
Qwen-Image-Edit + multi_angles LoRA should lock identity across the 6
while varying only the armor.

```bash
cd scaffolds/engine/asset_workflows/top_down_character

# Phase 1: 6 blockouts × 4 directions = 24 ERNIE calls (~7 min Turbo)
python3 batch_blockout.py \
    --essence 1986_dragon_quest \
    --name-match hero_ \
    --apply --model-kind Turbo

# Phase 2: frame-2 walk cycle via Qwen chain, 24 Qwen calls
for anim in hero_plainclothes_walk hero_leather_armor_walk hero_chain_armor_walk \
            hero_half_plate_walk hero_full_plate_walk hero_magic_armor_walk; do
    python3 run_animation.py "./out/blockouts/1986_dragon_quest/$anim/" \
        --apply --anim walk
done
```

**Expected:** 48 final frames — 6 characters × 4 directions × 2 frames.

**Success signals:**
- Identity: All 6 characters recognizable as the same Hero, differing
  only by outfit. Silhouette + pose + facial features consistent.
- Armor progression readable: plainclothes (brown tunic) → leather
  (brown with belt) → chain (silver mail) → half-plate (silver armor) →
  full-plate (thicker silver/gold) → magic (red-gold regal).
- Per-direction silhouette correct: N = back, E = right profile, S =
  front, W = left profile.
- Frame-2 walk alternation visible: opposite foot forward between
  `frame_<D>.png` (blockout) and `animated_walk/<D>/frame_*.png`
  (Qwen nudged).

**Failure signals to document:**
- If all 6 characters look too similar (no armor progression) → ERNIE
  seed too dominant, reduce seed influence or adjust prompt weight on
  armor description.
- If identity breaks between characters → Qwen strength=0.4 too high,
  drop to 0.3.
- If direction breaks (all poses face front) → blockout_prompts direction
  clause not being picked up by ERNIE; may need prompt surgery in
  blockout_loader.blockout_prompts.

---

## Tier 4 — Full Dragon Quest roster (~45 min)

Once the 6-hero identity test reads clean, fire the full 16-character
Dragon Quest roster: princess, king, NPCs, elder, friar, townspeople,
etc.

```bash
python3 batch_blockout.py --essence 1986_dragon_quest --apply --model-kind Turbo
# 16 × 4 = 64 ERNIE calls (~18 min)

# Animation pass (walk on the 14 that have walk anim_frame_targets)
for anim_dir in ./out/blockouts/1986_dragon_quest/*walk*/; do
    python3 run_animation.py "$anim_dir" --apply --anim walk
done
# ~14 × 4 = 56 Qwen calls (~20 min on 20-step karras)
```

**Expected:** Full DQ castle/town populated with canonical-sprite
characters.

---

## Tier 5 — Cross-essence validation (open-ended)

With DQ proven, extend to other essence's rosters as needed:

```bash
# Zelda moblins/lynels/darknuts (10 specs)
python3 batch_blockout.py --essence 1986_legend_of_zelda --apply

# All gold-clean 1D chains across corpus
python3 batch_run.py --apply --min-nudges 3 --no-static
```

---

## What to record after each tier

Create `_VALIDATION_LOG.md` alongside this file:

```markdown
## 2026-04-XX — Tier N — <status>

- model_kind: Turbo / Base
- ERNIE version: (from /healthz)
- Qwen-Image-Edit LoRA: multi_angles @ strength 1.0 (or changed)
- Wall-clock: <X min>
- Outputs: <N> final frames
- Issues: <any regressions or quality gaps>
- Tuning: <what was adjusted before next tier>
```

Let these logs flow back into `nudge_quality_report.py` as weights on
the `confidence` field — over time the quality audit calibrates to
real production signal, not just parse heuristics.

---

## Stop conditions

- If Tier 0 fails: don't continue — fix infra before burning tokens.
- If Tier 1 produces "looks OK" outputs on 1 of 7 but not 5+ of 7:
  pause and triage the parser. Something's systemically weak.
- If Tier 3's Dragon Quest 6-hero test shows no identity preservation:
  pause and investigate Qwen-Image-Edit's multi_angles LoRA strength.

Everything here assumes ERNIE-Image-Turbo-GGUF constants (steps=8,
CFG=1.0, use_pe=false) per `memory/ernie_image_turbo_constants.md`.
