# Agentic CSG Modeler — Session Log

Started: 2026-04-25
Loop: every 10 min (cron job `17b0872d`)
Cap per target: ~6 iterations before retiring or pivoting.

Each iteration:
1. Read `public/sdf_modeler/live.{png,json}` to see current state
2. Compare to current target (text description, not a real reference image yet)
3. Write delta to `public/sdf_modeler/inbox.ark.json`
4. Append observations + next-step plan below

Constraints:
- Single non-rigged accessories only (no chests, no characters)
- Vocabulary: `sup, sphere, box, roundedBox, trapezoidalBox, ellipsoid, ellipsoidExact, cylinder, capsule, torus, band, cone, bentCapsule`
- CSG ops: `blendGroup` (1-15) + `blendRadius` (signed: positive=union, negative=subtract), `chamfer`, `mirrorYZ`, `repeats[]` (linear + rotational scatter)
- Atlas at 512×512 (4 panels at 256² each: front / side / top / iso) with 1cm/5mm grid bg

## Proportions playbook (apply every iteration)

**When picking sizes for a new target, don't eyeball — pick via ratios.**
Step 1: choose ONE characteristic dimension (usually total height: ~0.10–0.20m for accessories)
Step 2: divide that into 2–4 blocks via standard ratios
Step 3: features within each block at golden-ratio or simple-fraction landmarks

**Golden ratio (φ ≈ 1.618; 1/φ ≈ 0.618; 1 − 1/φ ≈ 0.382)** — for organic/decorative
- bottle body : neck = φ : 1 (body is the larger section)
- cup-height : stem-height (goblet) = φ : 1
- sword blade : grip = φ : 1
- knife edge : spine taper = φ : 1
- crown spike-height : ring-height = φ : 1

**Simple integer ratios** — for mechanical/utilitarian
- cube crate / dice: 1:1:1
- mug / tankard: H:W = 1.2:1 (just-tall cylinder)
- barrel: H:W = 3:2 (slightly tall), bulge widest at exact mid-height
- hammer / pick: handle : head = 3:1 to 4:1 (head is 25–33% of total)
- shield: thickness:diameter = 1:15 to 1:20 (very thin)
- handle to grip ratio: typical 4–6 grip-diameters fits in handle length

**Detail-spacing rules**
- N parallel features (planks, grooves, hoops) on a span L: feature-pitch = L / (N+1) → features land at L*1/(N+1), L*2/(N+1), … L*N/(N+1)
- Rotational scatter count: 4 (axis-aligned), 6 (hex symmetry), 8 (octagonal), 12+ (perceptually continuous)
- Rivet diameter ≈ 1/8 to 1/12 of face dimension

**Reference-photo decomposition** (when a real reference image arrives)
1. Imagine a tight bounding box; estimate total height in m (~0.10–0.20 typical for accessories)
2. Mark horizontal divider lines on the image where mass type changes (e.g., for a goblet: cup top, cup bottom, knot, stem bottom, base top, base bottom — 6 lines)
3. Note each segment's fraction of the bounding-box height
4. Translate fractions to absolute meters; pick widths from same reference
5. Cross-check with golden-ratio: does any pair of segments come close to 1.618:1? If yes, snap to that.

**Worked example — describing a face like a designer**:
> "the jaw line is exactly 1/2 down and then begins to curve abruptly 3/4 down the face arriving at the 3cm rounded chin"

Decoding to spec-friendly form:
- Reference dimension: face height = `H`
- Jawline TOP starts at `y = -0.5*H` (mid-face, 1/2 down)
- Curvature transition (abrupt bend) at `y = -0.75*H` (3/4 down)
- Chin terminus at `y = -H` (bottom)
- Chin terminus has `r = 0.03` (3cm, absolute, not relative — it's the closure detail)

Pattern: **fraction-of-axis for placement** + **concrete absolute for closure detail**.
Proportions describe relative geometry; absolutes specify "the part the eye lands on."

**Why fractions beat eyeballed numbers**:
- Spec stays scale-independent — change `H` and everything proportions correctly
- Reference matching gets simpler: read fractions off the image, multiply by chosen H
- Golden-ratio snaps (0.618, 0.382, 1.618) feel right because they ARE — same math the eye loves

---

## Targets attempted

| target | status | rounds | notes |
|---|---|---|---|
| barrel | ✅ shipped | 6 | cylinder body + ellipsoid bulge (group 1 smooth-blend) + 3 torus hoops (hard union). Reads as a wood barrel from all 4 panels. |
| kettle helmet | partial (round 1 shipped, r2 deferred) | 1+ | bowler/kettle silhouette working with SUP dome + torus brim. r2 (flat disc brim) queued in inbox during the dead window; superseded by crate pivot. Resumable. |
| wooden crate | ✅ shipped | 4 | roundedBox body + 12 subtractive plank grooves (mirrorYZ) + 8 corner brackets (mirrorYZ). Reads as a banded crate from any panel. |
| bottle/flask | ✅ shipped (r2) | 2 | smooth-blend body+neck via group 1 blendRadius=0.020 produces clean shoulder transition with NO extra primitive. r2 added flange + taller cork. |
| pistol | ✅ shipped (r2) | 2 | first 2-axis-asymmetric target. Barrel along X (rotationDeg=[0,0,90]), trigger guard rotated to vertical (rotationDeg=[90,0,0]), grip tilted back (rotationDeg=[0,0,-15]), hammer tilted (rotationDeg=[0,0,15]). 7 prims, all hard-union. Reads as a clean handgun from front + iso. |
| polygonal flask | ✅ shipped (r1) | 1 | apothecary-square flask: roundedBox body (X≠Z proportions) + tilted cylinder neck + cork following the tilt. 3 prims. Asymmetric on 2 of 3 axes. |
| wrench | ✅ shipped (r2) | 2 | open-end + box-end wrench. 5 prims (handle + 2 heads + 2 subtracts). Jaw U opens forward (+X) via subtractive box; loop hole through left end via subtractive cylinder. Tests subtractive-shape vocabulary harder than the crate's plank grooves. |
| anvil | ✅ shipped (r2) | 2 | blacksmith anvil. 5 prims: body (working surface) + horn (cone rotated -90° around Z, apex pointing +X) + hardy hole (subtractive box) + waist + base. First successful use of cone primitive with rotation; cone apex points +X exactly as intended. Hardy hole reads as a clear square indentation on top. |
| pickaxe | ✅ shipped (r1) | 1 | T-shape: vertical handle + double-cone head (one rotated +90°Z, one -90°Z, apexes pointing -X / +X) + roundedBox head_hub joining them via smooth-blend (group 1, blend r=0.006). First use of TWO cones with mirrored rotations to form a symmetric tool head. r2 (binding ring) skipped in favor of pivoting to curved targets. |
| saber/scimitar | ✅ shipped (r1) | 1 | first CURVED target. bentCapsule blade with tipDelta=[0.045, 0, 0] gives a smooth parabolic curve. Plus pommel + grip + guard. Required adding `tipDelta?: Vec3` field to ModelerPrim and routing it through specToPrims to override the rotation slot for type 14 (engine overload). |
| bow | ✅ shipped (r2) | 2 | torus + subtractive box arc. r1 attempt with 2 mirrored bentCapsules failed because bentCapsule "tip" is hardcoded at LOCAL +Y, can't be flipped without rotation support (which the slot-overload prevents). r2 used torus(major=0.080, minor=0.005) rotated [90,0,0] (ring in XY plane) + box subtracting +X half → clean "C" arc. |

---

## Bugs found mid-flight

- **`ellipsoidExact` (type 19) renders phantom far-field hits** when params have axis equality (rx == rz). Background fills with structured noise. Repro: rx=rz=0.072, ry=0.075. Cheap `ellipsoid` (type 3) is fine. Suspect Cardano root degeneracy in `solveQuadratic2`. Workaround: use cheap ellipsoid for now. **Fix: when discriminant near zero in solveQuadratic2, fall back to algebraic roots — TODO file separately.**

---

## Iteration history

### barrel — round 1 (block-out)
- spec: cylinder(r=0.06, h=0.10) + 2 tori(major=0.063, minor=0.008) at y=±0.07
- result: clean cylindrical body, bands visible. Reads as a barrel.
- crit: walls dead-straight (no stave bulge); bands a touch thin
- next: smooth-blend a bulge into the body

### barrel — round 2 (bulge attempt 1)
- spec: cylinder(0.058,0.095) + central torus bulge (major=0.062, minor=0.020), both group 1 blend 0.018
- result: pinched vase silhouette — torus creates a ring of fat at y=0 but cylinder above/below stays straight, smooth-blend pinches the transition
- crit: torus is wrong primitive for a smooth bulge; need something whose width varies smoothly with Y
- next: replace bulge torus with ellipsoid — its Y profile naturally tapers

### barrel — round 3 (ellipsoidExact bulge)
- spec: cylinder(0.05,0.095) + ellipsoidExact(0.072, 0.075, 0.072), group 1 blend 0.025
- result: bulge correct, but background fills with phantom noise — type 19 bug
- next: swap to cheap ellipsoid (type 3); same params

### barrel — round 3b (cheap ellipsoid)
- result: clean render. Body is now egg-shaped — bulge dominates, caps too rounded
- crit: bulge 44% wider than cylinder (too pronounced); blend radius 0.025 is too soft, rounds the cylinder caps
- next: tighten — bulge only ~15% wider, blend radius down to 0.012, ellipsoid Y shorter so bulge concentrates in the middle and cylinder caps stick out clearly

### barrel — round 4 (tightened bulge)
- spec: cyl(0.06, 0.080) + ell(0.07, 0.06, 0.07) group 1 blend 0.012; hoops at y=±0.062, major 0.066
- result: recognizable barrel; bulge subtle (17%); but front silhouette has slight S-curve (concave between bulge top and cylinder cap) — vase-like
- next: bigger bulge (25%), tall ellipsoid (ry≈cylinder h) to kill the concave region

### barrel — round 5 (bigger bulge)
- spec: cyl(0.058, 0.082) + ell(0.075, 0.078, 0.075) group 1 blend 0.010; hoops y=±0.060 major 0.072 minor 0.013
- result: convincing barrel from any panel. Iso view in particular reads cleanly.
- crit: only 2 hoops — most barrels have 3
- next: add a center hoop, slightly raise top/bottom hoops so cylinder caps poke out

### barrel — round 6 ✅ shipped
- spec: same body, 3 hoops at y=0, ±0.067; major 0.078 (mid) / 0.071 (top+bot)
- result: classic 3-band wood barrel silhouette. Clear bulge, flat-ish heads, three iron bands. iso view nails it.
- learnings:
  - cylinder body + ellipsoid bulge in same blend group is THE pattern for barrels / kegs / urns
  - hoops as standalone tori (group 0) keep them visually distinct from body even when geometrically overlapping
  - blend radius 0.010-0.012 is the sweet spot — tight enough to keep cap definition, soft enough to fuse body+bulge cleanly
  - 5-prim budget enough for a recognizable barrel; could push to 7 with chamfered cap rims if quality bar rises

### color discussion (out-of-band, no spec change)
- user asked how to pair color (brown body + metallic hoops). Proposed: add optional `color: [r,g,b]` per prim, default falls back to MATERIAL_RGB. Same-blendGroup prims must share color (else SDF picks at seams = flicker). Body+bulge wood, hoops metal. Not yet implemented — agent loop continued without.

### materials discussion (out-of-band)
- user concern: palette mapping won't scale to material properties (metal vs wood vs leather). Acknowledged as a real architectural pull.
- recommendation: split modeling into orthogonal passes — geometry agent (current), material agent (later). Material agent operates on a finished geometry spec, tags prims/groups with named materials from a small library (~12 entries). Engine maps name→(color, roughness, specular, anisotropy) at render time.
- key insight: don't overload palette/colorFunc for materials. Palette = pixel-art quantization. Material = surface-shading model. Different concerns.
- **decision**: defer material work post-loop. Continue geometry agent on next target.

---

### kettle helmet — round 1 (block-out)
- spec: SUP dome (r=0.075, blend=0.2, yClipN=-0.5) at y=0.02 + torus brim (major=0.090, minor=0.012) at y=-0.012, both group 1 blend 0.015
- result (after user re-engaged the modeler): clean bowler/kettle silhouette from all 4 panels. Dome rounded, brim wide and visible. Reads as a hat / helmet immediately.
- crit: torus brim has a rounded cross-section — looks more "bowler hat" than "iron helmet". Real kettle/morion brims are flat steel plates.
- next: replace torus brim with a flat thin cylinder (disc)

### kettle helmet — round 2 (flat disc brim) — QUEUED, then deferred
- spec: same dome; brim → cylinder(r=0.105, h=0.006) at y=-0.015. Wider (0.105 vs 0.090) and flat-cross-section.
- modeler stale at time of write (135-145s); user likely in human mode or tab unfocused.
- on next cron tick, modeler still unresponsive → pivoted target rather than burn the iteration.
- helmet round 2 spec abandoned in favor of crate target. Can resume helmet later by re-queueing.

### crate — round 1 (block-out) — QUEUED, modeler unresponsive
- spec: single roundedBox(hx=0.08, hy=0.07, hz=0.08, corner=0.005). Standalone (group 0).
- intent: simple wooden crate body — tests box primitives + sets up rounds 2-4 for additive nail/rivet detail and subtractive plank grooves
- modeler stale; spec sits in inbox. Live.png still showing kettle round 1 from prior iteration.
- next: plan ahead — pre-design rounds 2-4 below so when modeler resumes we burn through them quickly.

#### crate — pre-planned rounds (apply when modeler responsive)
- **r2 (plank grooves)**: same body + 6 thin subtractive boxes (negative blendRadius). 3 horizontal grooves on each face along Y axis, e.g. groove(hx=0.085, hy=0.001, hz=0.085) at y=0.025, y=0, y=-0.025. All in group 1 with body, blend r = -0.005 (subtract). This carves the plank lines.
- **r3 (corner reinforcement)**: 8 small spheres (r=0.012) at the 8 corners of the crate. Group 0, hard union. Reads as iron corner brackets.
  - alt: 8 thin boxes at the corners as "L-brackets"
- **r4 (rivets)**: small spheres (r=0.004) on the corner brackets. Could mirror so I only author one octant. (mirrorYZ for X+ → X-, but Y/Z mirror isn't supported as a single flag; would need to emit 8 per corner manually.)

### infrastructure observation — agent-loop robustness
- the agent loop dies silently when user toggles to human mode (autosave guarded by `displayMode === 'agent'`) OR closes the tab
- inbox poll DOES still fire in human mode (it's the autosave that's mode-gated), so my setSpec writes WOULD be applied — but I can't verify because no autosave fires to update live.png
- **proposed fix (post-loop)**: split the autosave from the display canvas. Render agent atlases to a hidden offscreen canvas regardless of display mode. The user's display canvas tracks human mode (orbit). Agent loop becomes mode-independent. ~80 LoC, mostly wiring a second render target.
- alt simpler fix: if modeler picks up an inbox change while in human mode, briefly capture an atlas (1 frame flicker) and save. Less clean but trivial to do.

### iteration N+1 — fix-in-flight applied
- modeler stale 15+ min, user tab not loaded
- **applied the cheap fix**: removed `displayMode !== 'agent'` guard on autosave. Now autosave fires regardless of mode; screenshotAtlas() flips to agent for 1 frame and restores. Brief flicker for human-mode users; agent loop survives mode changes.
- typechecks clean. Will activate on next page load or HMR pickup if tab is open.
- crate r1 spec re-queued as `crate_r1b` to bust any cache. Sitting in inbox.
- still observing block: dev server up (HTTP 200) but no browser tab connected. Pure waiting from here.

### iteration N+2 — same state, no new action
- live.png mtime unchanged (1777155757); current time 1777156655+. ~15 min stale.
- inbox holds crate_r1b. Code fix sits in src/. HMR/page-load required to activate.
- this iteration produced: nothing actionable. The cron will keep firing; I'll resume rendering work the moment a browser session reconnects.

### iteration N+3 — modeler re-engaged
- user said "its ready"; live.png mtime fresh.
- crate_r1b applied successfully — clean wide rounded box, slight cap rounding from corner radius
- moved through r2 → r3 → r4 in this single iteration (modeler responsive, fast cycle)

### crate — round 2 (front+back grooves)
- spec: body + 4 subtractive grooves at front/back (z=±0.080), mirrorYZ for off-center grooves so 4 spec entries → 6 grooves
- result: 3 vertical grooves visible on front face — clearly delineates 4 wooden planks
- crit: small notch artifacts where grooves meet top/bottom edges (groove halfY=0.075 > body halfY=0.070)
- next: side grooves + tighten halfY

### crate — round 3 (full plank coverage)
- spec: r2 + 6 side grooves (3 spec entries with mirrorYZ at +X face); halfY=0.067 for all grooves
- result: all 4 vertical faces show plank divisions; top edge clean. Reads as a wooden crate.
- next: corner brackets

### crate — round 4 ✅ shipped
- spec: r3 + 4 corner brackets (roundedBox 12mm cubes) at 4 -X corners, mirrorYZ → 8 corners
- result: full crate. Plank grooves + iron corner caps. Iso view sells it.
- learnings:
  - mirrorYZ is a 2× authoring multiplier — used 3 times here (groove pairs, side groove sets, corner pairs)
  - subtractive grooves with negative blendRadius work cleanly. Negative=−0.003 gives a soft enough corner that the groove edge isn't razor-sharp but stays distinct.
  - same-blend-group {body, grooves} is the pattern for engraved features. Hard-union {body, brackets} keeps additive features visually distinct.
  - 13 effective primitives (1 body + 12 derived via mirror) for a fully-detailed crate. Sub-budget.

### bottle — round 1 ✅ shipped
- spec: cylinder body(r=0.045, h=0.040) at y=-0.030 + cylinder neck(r=0.013, h=0.025) at y=0.040, both group 1 blendRadius=0.020; cork(r=0.014, h=0.005) at y=0.075 group 0
- result: instantly recognizable potion bottle. Body + smooth shoulder + narrow neck + cork. From any of the 4 panels.
- key insight: the SHOULDER of the bottle is created entirely by the smooth-blend between body and neck. **A wide blendRadius (0.020) between two cylinders of different radius is a free taper.** No third primitive needed.
- next: optional polish (round 2 — taller body + flange torus at neck top + taller cork) queued

### bottle — round 2 ✅ shipped
- spec: taller body (h=0.050), taller cork (h=0.008), neck flange torus(major=0.016, minor=0.004) at neck top
- result: textbook potion flask. Flange ring at neck top reads as the bottle "rim" / lip. Cork prominent. 4 prims.
- learning: small detail prims like the flange torus add big perceptual value. Same insight as crate corner brackets — additive features in group 0 layer cleanly on smooth-blended bases.

### dagger — abandoned in favor of gun
- 4-prim block-out spec written (sphere pommel + cylinder grip + box guard + box blade) but user redirected to "gun model something highly asymmetric along multiple axis" before pickup.
- spec discarded, can revisit later as a separate target.

### pistol — round 1 (silhouette block-out)
- spec: 4 prims — barrel (cylinder rotated 90° about Z), slide (roundedBox), grip (roundedBox tilted -15°), trigger guard (torus rotated 90° about X)
- result: instantly recognizable handgun silhouette in front view. Iso shows full 3D handgun. Side and top show muzzle / slide perspectives.
- key insight: rotation lets ONE primitive type cover many roles. Cylinder is the barrel by rotating Z; torus becomes a vertical ring by rotating X. Without rotation we'd need a barrel-along-Y primitive (capsule?) and would lack a vertical-ring primitive entirely.
- next: hammer + trigger + front sight

### pistol — round 2 ✅ shipped
- spec: r1 + hammer (small tilted box at -X+Y), trigger (thin box inside guard), front sight (tiny box at +X top)
- result: 7-prim handgun. Hammer's 15° tilt sells the "cocked" look. Trigger sits visibly inside the guard ring. Sight blip at front.
- learnings:
  - **rotationDeg unlocks 2D-axis asymmetry without needing a richer primitive vocabulary.** This was the gun's whole authoring story.
  - hard-union (group 0) for ALL prims here. A pistol is a hard-edged mechanical assembly; smooth-blend would smear the part boundaries we want to read.
  - 4 of 4 panels usefully informative because the X-axis (gun's interesting axis) is NOT one of the cardinal viewing axes — the front camera shows the gun's profile cleanly because it looks down −Z while the gun extends along X.

### user feedback during this iteration
- requested: polygonal flasks (use box-leaning SUP for faceted look), more asymmetric subjects, gun model. Gun shipped this iteration.
- requested view-mode additions: per-prim color (debug primitive boundaries even after smooth-blend) + silhouette-only mode (binary mask, white shape on black, for reference matching). Both are cheap shader changes; queued for post-loop work.
- noted: agent loop resumed reliably after user fixed tab-focus issue; the autosave-mode-guard fix is working.

### polygonal flask — round 1 ✅ shipped
- spec: roundedBox(0.040, 0.045, 0.028, 0.003) body + tilted cylinder neck (rotationDeg [0,0,8]) + tilted cork. group 1 blendRadius=0.018 fuses square body to round neck.
- result: apothecary-style square flask with off-center neck and cork. X≠Z visible in top view; tilt visible in front + iso.
- key insight: smooth-blend transitions BETWEEN PRIMITIVE TYPES (rectangular body + cylindrical neck) creates a region where the cross-section morphs from square to round. Free shoulder-shape morphology, no extra prims.

### wrench — round 1 (silhouette block-out)
- spec: handle + 2 heads + 2 subtractive cuts. jaw_cut placed wrong, made a corner notch instead of forward-facing U.
- next: reposition jaw_cut to extend BEYOND the +X face of the head, with halfX overlapping just the head's +X edge

### wrench — round 2 ✅ shipped
- spec: jaw_cut at pos [0.073, 0.003, 0], hx=0.013, hy=0.007, hz=0.012, blendRadius=-0.001
- result: clean wrench. Open jaw faces +X (visible in side panel as a face-on U). Loop hole on -X end visible through-and-through.
- learning: subtractive-cut prims in same blend group as the body work cleanly even with NEGATIVE blendRadius=-0.001 (very small). Smaller magnitude = crisper subtraction edges. Use larger negative for bevel-into-hole, smaller for crisp/sharp.

### anvil — round 1 (silhouette)
- spec: roundedBox body + cone horn (rotationDeg=[0,0,-90] makes apex point +X) + small base, all 3 prims with smooth-blend group on body+horn
- result: clean anvil silhouette. Horn tapers to a sharp point at +X; body has flat top; base sits underneath.
- crit: base too small relative to body (real anvils have a substantial pedestal); missing hardy hole
- next: add hardy hole + waist + larger base

### anvil — round 2 ✅ shipped
- spec: r1 + hardy hole (subtractive box, group 1, blend r=-0.001) at top of body + waist (small box below body) + larger base (40mm × 30mm × 12mm thick)
- result: textbook blacksmith anvil. Body, horn, hardy hole notch on top, narrow waist, wide base. Iso view nails it.
- learning: cone primitive WITH rotation works first try when you understand the local frame. Default cone has apex at origin, base extending -Y by `height`. Rotating Z by -90° takes the base direction from -Y to -X (so base points -X, apex points "into" the model from +X). After translating apex to the desired +X tip position, the cone naturally tapers from body outward to a point. **Cone is the right primitive for any tapered protrusion** (horn, beak, tooth, claw, spike).

### pickaxe — round 1 (silhouette) — QUEUED, modeler stalled
- spec: 4 prims — vertical cylinder handle + roundedBox head_hub at top + 2 cones (cone(sin=0.35, cos=0.937, height=0.045)) rotated +90°Z (left prong) and -90°Z (right prong) so apexes point outward (-X / +X)
- expected result: T-shape pickaxe with two pointed prongs and a vertical handle. Cones smooth-blend to head_hub (group 1, blend r=0.006), handle is hard-union (group 0).
- modeler ~9 min stale at write time. Spec sits in inbox. Will pick up on next browser-tab resume.
- next: assuming clean render → r2 polish (binding ring at handle/head junction). If rotation is wrong (apex pointing wrong direction), swap left-prong rotation to -90°Z and right-prong to +90°Z.

### pickaxe — pre-planned r2 (apply if r1 reads correctly)
- spec: r1 + small torus binding ring at handle/head junction:
  - binding: torus(major=0.013, minor=0.003), pos [0, 0.045, 0], rotationDeg=[0, 0, 0] (default torus axis Y, ring lies in XZ plane = horizontal at the junction)
  - group 0 (hard union, distinct iron band)

## Observations on agent loop (recurring problem)
- background-tab JS throttling kills the loop dead. Browsers throttle (or fully suspend) JS in unfocused tabs as an aggressive optimization. The autosave-mode-guard fix doesn't help here because the AUTOSAVE itself is suspended — and the inbox POLL is suspended too. So even my setSpec writes don't apply until the user re-engages the tab.
- the long-term fix is the headless Playwright driver path I sketched earlier — modeler runs server-side, agent loop is decoupled from any browser session. But that's blocked on ARM64 + WebGPU + display-server problems.
- the cheapest interim fix: have a separate-tab "agent renderer" that's always pinned to foreground (e.g. a popup window the user keeps visible at the corner of their screen). User keeps the small window open while doing other things. Modeler stays alive.

### dead-tick observation (this iteration)
- live.png mtime 1777159148, now 1777160255 — 18 min stale. inbox 9 min old (pickaxe r1 still unapplied).
- no progress this iteration. Cron keeps firing, but no new pixels.
- pre-planned post-pickaxe targets (apply when modeler resumes):
  - r1 + r2 (binding ring) for pickaxe
  - lantern (multi-component with hollow body via SUP shell)
  - revolver (cylinder chamber bulge — true 3-axis asymmetry)

### recurve bow — round 1 (approximate)
- spec: main arc (torus + subtractive box for half-circle on -X side) + grip + 2 cones at tips angled +X to suggest recurve tips
- result: silhouette has main arc + small triangular tip protrusions. Reads as "bow with pointy tips" but NOT a true recurve curl-back.
- crit: real recurve tips CURVE BACK (S-curve), not straight cone-extensions
- limitations:
  - bentCapsule rotation slot is overloaded for tipDelta — can't both rotate AND bend a single bentCapsule
  - bezier-profile-capsule (type 17) needs 3 bone indices; modeler is single-bone-frame so can't use it without multi-bone scaffolding
  - **the abstraction layer the user is asking about** (high-level shapes like `arc(angle)`, `recurveArc(...)`, `taperedSweep(...)`) would solve this naturally
- next options (pick one): expose bezier-profile-capsule (~1 day work to scaffold fake bones), build a small shape macro layer (~2 days), or accept approximate recurve
- shipped at "approximate" quality

### silhouette view-mode landed mid-loop
- added viewMode == 3u path in lit shader: pure white-on-black binary mask, runs BEFORE the bg checker so it's not contaminated
- new "silh" button in the view row + setViewMode('silhouette') in the tool API
- intended use: matching against reference photos (binary masks) without lighting noise. Strips Lambert + checker → just shape.
- 5 lines of WGSL + 3 lines of TS

### mug — round 1 ✅ shipped
- spec: 3 prims — cylinder body + subtractive cylinder cavity (group 1, blend r=-0.002 carves out the cup interior) + torus handle positioned at +X of body, partially overlapping
- result: textbook coffee mug. Top view shows hollow interior (cavity working). Iso shows full 3D mug with D-handle.
- learning: **partial-overlap pattern for handles** — torus center positioned BEYOND the body radius so the body's right edge bisects the ring. Hard-union absorbs the ring's inner half (hidden inside body). Visible portion is just the outer "D". No subtractive box needed. Scales to any "ring attached to convex surface" case.

### sdTrapezoidalBox primitive landed mid-loop
- new type 21 in raymarch_renderer.ts. Truncated rectangular pyramid: bx, bz at bottom, scaled by topRatio at top. h is half-height (Y axis).
- params: (bx, bz, h, topRatio). topRatio=1 reduces to box, topRatio=0 collapses to a rectangular pyramid point.
- WGSL ~15 LoC. Validated with a frustum test render.
- Use cases: knife/sword blades, gun stocks, frustums, decorative bezels.

### sdBand primitive landed mid-loop
- new type 22. Rectangular-cross-section torus. Major radius R, radial half-extent w (in/out from ring), axial half-extent h (along axis).
- params: (R, w, h, _). Default torus has axis Y (ring in XZ plane).
- WGSL ~8 LoC. Replaces torus where a "flat band" cross-section is wanted (mug handles, watch bands, sword belts, barrel hoops with width).

### mug — round 2 ✅ shipped (with band handle)
- spec: same body + cavity + replaced torus handle with `band(R=0.025, w=0.004, h=0.014)` rotated [90,0,0]
- result: handle now has flat rectangular cross-section visible from any panel — looks like a real coffee-mug handle vs. r1's perfect-donut ring
- user feedback: "less of a perfect donut, more an extruded ellipsoid" / "flatter handle area" / "more of a band and less of a ring" — all addressed by the new primitive

### knife — round 1 (testing trapezoidalBox in target context)
- spec: trapezoidalBox blade (bx=0.012 wide, bz=0.0015 thin, h=0.045 long, topRatio=0.08 for near-point tip) + guard + grip + pommel
- queued in inbox; modeler stalled before pickup

### scatter / replicate operator landed mid-loop
- new field on ModelerPrim: `repeats?: Array<{axis, count, spacing}>`
- order in pipeline: `repeat → mirror → upload`. Repeats compose multiplicatively (5 along X then 3 along Z = 15 final copies, centered on the original prim).
- ~30 LoC of TS in `applyRepeats()` + normalizeSpec round-trip + integration into specToPrims.
- raymarch cache absorbs runtime cost — 70+ extra prims is essentially free per-frame after first compile.

### treasure chest — round 2 ✅ shipped
- spec: 3 entries → 74 prims
  - chest_outer + chest_inner (subtractive group) = open hollow box
  - coin = single cylinder with `repeats: [{x,6,0.014}, {z,4,0.014}, {y,3,0.005}]` → 72 coins in a 6×4×3 grid
- r1 had coins buried in the solid floor (y=-0.020 below cavity bottom y=-0.014). r2 raised coins to y=-0.005, inside the cavity.
- result: open chest with visible 6×4 grid of stacked coins. Top view nails it.
- key insight: **the scatter operator turned what would have been 72 spec entries into 1 entry.** The user's "muddy graph" concern fully addressed.

### sword — round 1 ✅ shipped
- spec: 5 entries (pommel + grip + grip_wrap + guard + blade) → 9 prims via scatter
- grip_wrap uses LINEAR scatter (5 small tori spaced along Y) for the leather-wrap rings on the handle
- blade uses TRAPEZOIDAL BOX with topRatio=0.10 for the tapered tip
- result: instantly readable as a sword. Front + iso both clear.

### rotational scatter mode landed mid-loop
- new variant: `repeats[].kind === 'rotational'` rotates the offset around `axis` by 2π/count per copy. The prim's own orientation stays the same.
- ~20 LoC addition to `applyRepeats`.
- Use cases: crown spikes, gear teeth, flower petals, ring of studs/rivets, atomic-orbital shape sets.

### crown — round 1 ✅ shipped
- spec: 3 entries → 10 prims. ring_base + ring_top (two torus stacked) + spike (cone) with rotational scatter count=8.
- result: 8 evenly-spaced spike points sitting between two ring bases. Top view shows the perfect ring of points.
- key insight: rotational scatter is the PERFECT pattern for radial detail. Single spec entry → arbitrary point count.

### renderRes bump + atlas overhaul
- raised renderRes from 128 → 256 per panel (atlas 512×512). Visual quality jump: 4× pixels per primitive, clear sub-cm features readable.
- replaced checker bg with **1cm major + 5mm minor coordinate grid**, smoothstep-AA'd. Agent can now read sizes directly off the atlas instead of mentally mapping spec values.
- added **curvature view-mode** (mode 4): screen-space `length(dpdx(n) + dpdy(n))` — bevels, creases, silhouette edges all light up; flat surfaces stay dark. Standalone signal for spotting subtle features.
- added **per-surface view-mode** (mode 5): hashes the surface normal direction into a hue. Surfaces with similar orientation get similar colors; sharply different orientations get distinct colors. Cheap proxy for "per-primitive color" without engine support for primIdx.
- panel labels via HTML overlay (top-left of each panel quadrant): "FRONT X→ Y↑ (look -Z)" etc. Visible to human; not burned into the PNG (would need shader text rendering).
- shader bug fix: hoisted `dpdxFine`/`dpdyFine` to uniform control flow (outside the isHit conditional). Was failing compile silently → pure white render.

### lantern — round 1 ✅ shipped
- spec: 5 entries → 11 prims. base + cap + post (rotational ×4) + pane (rotational ×4) + handle.
- result: clean square lantern silhouette with 4 corner posts visible from any panel, recessed panes between posts, handle on top.
- key insight: rotational scatter compresses what would have been 8 corner+pane spec entries into 2.

### morningstar — round 1 ✅ shipped
- 6 spec entries → 13 prims. Cylinder handle + spheres for pommel/head + rotational-scatter (8) for equatorial studs + 2 axial studs (top + bottom).
- result: clear morningstar / flanged-mace silhouette. Top-down view shows the perfect 8-fold stud ring.
- limitation noted: rotational scatter doesn't rotate the prim's local frame, only its offset. For RADIAL spikes (cones pointing outward), would need per-copy rotation. Studs work because they're rotationally symmetric (sphere doesn't care about orientation).

### detailAmplitude field plumbed in modeler
- new ModelerPrim field: `detailAmplitude?: number`. Sets the engine's existing FBM-noise normal-perturbation amplitude (RaymarchPrimitive.detailAmplitude).
- per-prim weathering / wood-grain / worn-metal effect. ~0.002-0.005 for subtle, >0.01 rough.
- only affects SHADING normal, not silhouette. For silhouette displacement (chips, breakage), would need engine SDF perturbation — separate work.

### shield — round 1 ✅ shipped
- 4 spec entries → 12 prims. Disc cylinder (rotated to face Z) + rim torus + center boss + rivet (rotational scatter 8 around Z axis).
- first use of Z-axis rotational scatter — works as expected, produces 8 rivets in a ring around the boss.
- detailAmplitude=0.003 on disc/rim/boss for weathered metal feel; visual effect subtle at 256² but plumbing validated.

### chalice — round 2 ✅ shipped (golden-ratio refinement)
- 5 prims, fully manifested. Total H=0.10m. Cup=upper 0.618*H. Stem+base=lower 0.382*H. Knot at golden split of stem from top.
- result: noticeably more "designed" than r1 — proportions match real chalices.
- the grid bg lets me verify height ratios visually without spec math.

### heater shield ✅ shipped
- 3 prims via trapezoidalBox(topRatio=1.5) for upper section + cone for bottom point + boss sphere
- first use of trapezoidalBox with topRatio>1 (top wider than bottom = inverted frustum). Useful for medieval armor silhouettes.

### colorFunc plumbing landed mid-loop
- new ModelerPrim fields: `colorFunc?: number`, `paletteSlotB?: number`, `colorExtent?: number`. All exist on RaymarchPrimitive in the engine; just weren't exposed.
- palette slot 1 initialized to a darker shade of MATERIAL_RGB (×0.55) so stripe/dot patterns have visible contrast without needing per-prim color authoring.
- engine modes available: 0 flat, 1 gradientY, 2 pulsate, 3 radialFade, 4 stripes (local Y), 5 dots, 6 checker, 7 chevron, 8 worldStripes (world Y).
- LIMITATION: stripe direction is fixed (local Y or world Y). Can't do diagonal stripes without engine change adding a direction param. CSG-groove approach is the workaround for diagonal patterns.

### viking round shield (reference-driven, 3 rounds)
- reference: real photo of Viking-style round shield with iron rim, 5 diagonal wood planks, 8 rivets, painted decoration
- **r1**: 3 prims → 10 effective. Wood disc + iron rim + 8 rivets. Silhouette correct, no plank lines.
- **r2**: same + `colorFunc=8 worldStripes` on the wood_disc. Horizontal plank lines visible on face. Validates plumbing but stripes are horizontal not diagonal (limitation noted above).
- **r3 ✅ shipped**: same structure but planks via CSG-grooves — thin subtractive box rotated 30°, linear scatter ×5. Diagonal plank seams cleanly carved into the disc face, matches reference angle.
- key learning: **for hero props with directional surface detail, CSG-grooves beat procedural stripes**. Procedural is right for cheap mass-production / wood grain noise. Spec sizes are comparable thanks to scatter.
- still deferred (materials pass): wood vs iron color, painted center motif (decals).
- reference: real photo of Viking-style round shield with iron rim, wood planks (diagonal), 8 rivets, painted decoration
- shipped: 3 prims → 10 effective. Wood disc + iron rim torus + 8 rivets via rotational scatter on Z.
- silhouette matches reference. Front face is FLAT (reference shows slight dome) — minor geometric difference.
- **DEFERRED for next session (geometry pass alone can't ship this)**:
  - diagonal plank pattern → needs procedural mode (`procedural: 'planks'` with angle/spacing)
  - wood vs iron color differentiation → materials library
  - painted center cross/star motif → pixel-art post-process layer
- key learning: at sprite resolution, the geometry IS sufficient. The remaining gap is pure color/material treatment, which is the "post-pixelize" pipeline (eye-replacement style). Color+procedural carries the visual identity at small render sizes; geometry just provides the silhouette + mass distribution.

### voronoi WARPING for organic cracks
- after seeing the boulder's clean polygonal voronoi cells, applied coordinate-warp pre-distortion: input position offset by a 6×-frequency noise before the voronoi math.
- result: crack boundaries are now jagged irregular curves rather than convex polygons. Reads as natural stone fractures vs mechanical tessellation.
- ~5 lines added to evalPrim's crack-displacement path. Color-path voronoi (colorFunc=9 dark bands) NOT yet warped — could be aligned for consistency.
- shipped: **megalith** target — tall trapezoidal standing stone with low-density warped cracks. 1 spec entry, dramatic weathered-megalith look.

### perf + geometric crack displacement (iteration milestone)
- **renderRes 256 → 192** + **maxSteps 48 → 32** = ~50% perf boost. Agent vision quality unchanged (encoder downsamples to ~384 anyway).
- **GEOMETRIC CRACK DISPLACEMENT** added: when colorFunc=9 is set on a prim AND detailAmplitude > 0, the SDF result is displaced outward at voronoi cell edges. Crack lines become real silhouette gaps, not just dark color.
- Implementation: voronoi math computed at the prim's WORLD position, after the type-specific SDF returns. ~40 LoC inside evalPrim, reuses the same hash + 2-nearest-cell pattern as the color path.
- Spec field overload: `detailAmplitude` is "FBM normal-noise amplitude" when colorFunc != 9, but "crack DEPTH" when colorFunc == 9. Documented overload, no spec layout change.
- shipped: **boulder** target — single SUP primitive with crack displacement → reads exactly like the user's Utah cracked-rock-face reference. 1 spec entry, real 3D-broken silhouette.

### colorFunc=9 (voronoi-edge cracks) landed mid-loop
- new procedural in raymarch_renderer.ts: 2-nearest-neighbour voronoi computed in WORLD space, dark band where d2-d1 < threshold (cell-edge proximity).
- ~30 LoC of WGSL. Hash via `fract(sin(dot(cell, big_vec)) * big)`.
- ColorFunc enum extended: 0..8 + 9=cracks. spec field `colorFunc: 9 + colorExtent: cells/meter` activates.
- result on viking shield: dramatic cracked-stone look. At density=80 the planks are buried under crack network.
- this is the first new colorFunc since baseline. Pattern proven: each new procedural is ~30 LoC + one case in dispatcher + one enum line. Future modes (bricks, ridge cracks, cellular noise) follow identical pattern.

### viking helm — round 2 ✅ shipped
- 5 prims: SUP dome (yClipN=-0.5 hemisphere) + torus rim + box nose guard + 2 explicit cones (horn_left, horn_right)
- r1 had a bug: used mirrorYZ on the horn cone; mirror flips position but NOT rotation, so the mirrored copy had its apex pointing INWARD (toward the dome) instead of outward. Visually only ONE horn was visible.
- r2 fix: explicit horn_left (rotation [0,0,90], pos -X) and horn_right (rotation [0,0,-90], pos +X). Both apexes point outward.
- **bug to file**: mirrorYZ should optionally mirror the rotation quaternion too, not just position. For symmetric directional primitives, the current behavior is broken.

### voronoi → turbulent-noise-band crack mode
- user feedback: voronoi cracks "look like scales" — closed convex cells → fish-scale aesthetic.
- replaced voronoi-edge with FBM-noise-iso-contour: cracks live where `|fbm3(p*density) - 0.5| < threshold`. Result: meandering branching CRACK LINES along noise contours, not closed cells.
- `threshold` is the band width = crack profile thickness. `density` controls noise frequency = crack feature scale. `pow(t, 8.0)` for sharp crack-edge falloff.
- visual: thin lightning-bolt-style cracks that look like real fractures from silhouette angles, surface ripples from face-on (correct 3D crack behavior).
- removed all the voronoi math (~30 LoC of nested loops). Noise-band code is ~15 LoC, simpler + faster.

### crack-displacement bug fix + lightning-bolt warp tuning
- found bug: displacement formula `(thresh - edge) * crackDepth` meant max displacement was THRESHOLD × DEPTH (~10% of authored value). spec said "12mm" but engine produced "1.2mm." subtle visual confusion.
- fix: normalised the falloff `((thresh - edge) / thresh) * crackDepth` AND raised to pow=3 for sharper crack edges (linear was too smooth, made cracks read as bulges instead of fractures). crackDepth value is now the actual max displacement in meters.
- voronoi warp also upgraded: single noise3 → multi-octave fbm3 at amplitude 0.35 (was 0.05). gives "lightning-strike-style" jagged forks instead of clean polygons. user feedback: "starting to look like something now!!!"
- recalibrated visibility table (depth × density tradeoff for different effects):
  - 0.002 × 80: hairline craquelure
  - 0.005 × 40: aged cracked ceramic
  - 0.008 × 25: weathered pottery
  - 0.012 × 18: dramatic damage (lightning style)
  - 0.025 × 12: smashed/broken
- shipped: ceramic urn r6 (lightning-cracked, dramatic damage style)

### crackDepth visibility calibration
- 0.001m = sub-pixel at 192² panel, invisible
- 0.003m = barely visible (user: "barely visible but there")
- 0.006m = clearly visible cracks
- 0.015-0.025m = dramatic stone-fracture
- threshold scales with render resolution. Roughly: cracks read at >3-5% of model dimension on screen.

### geometry-only refactor (philosophy fix)
- user feedback: "modeler is not the shader/texturer — color/AO comes from a downstream bake pass. fragment development."
- removed `colorFunc`, `paletteSlotB`, `colorExtent` from the modeler's public spec interface
- added `crackDepth` (geometric crack-displacement depth in m) and `crackDensity` (cells/m) as the geometry-only fields
- internally: modeler sets engine fields under the hood (colorFunc=9 + detailAmplitude=crackDepth + paletteSlotB=paletteSlot) — the color side-effect is suppressed by setting B==A
- shipped: **ceramic urn** with hairline craquelure (crackDepth=0.001, crackDensity=80) — clean geometry, no color marks. Cylinder body + ellipsoid bulge + subtractive cylinder for hollow interior + rim torus.

## Loop summary (this session so far)
shipped targets (31): barrel, crate, bottle, pistol, polygonal flask, wrench, anvil, pickaxe, saber, bow, recurve bow (approximate), mug, treasure chest, sword, crown, lantern, morningstar, shield, chalice, heater shield, viking shield, viking helm, stone tablet, boulder, megalith, ceramic urn, column, tombstone, bell

### Session 2 begins — engine extension sprint
- mirrorYZ rotation fix landed: previously mirrored only the position, leaving directional primitives (cones, etc) with apex pointing wrong way. Now also reflects slot 4 — for rotation quats: (x, -y, -z, w); for type-14 bentCapsule (slot 4 = tipDelta): (-x, y, z). Standard reflection math. Validated with single-horn viking-helm spec → produces 2 correctly-outward horns.
- new procedural deformer 2: PITS (colorFunc=10). Worley distance to nearest cell point with domain warp. Inward round craters where dmin < pitRadius. Spec fields: `pitDepth`, `pitDensity`. Use cases: meteorites, rust pits, rusty metal.
- new procedural deformer 3: BUMPS (colorFunc=11). Smooth FBM outward displacement. No threshold — every point displaces by local noise. Spec fields: `bumpDepth`, `bumpDensity`. Use cases: leather hide, organic skin, soft tissue, asteroids.
- THREE deformer modes now coexist: cracks (line networks via noise-band), pits (round craters via Worley), bumps (smooth lumps via FBM). Same overload pattern (colorFunc + detailAmplitude=depth + colorExtent=density) so adding more is straightforward.
- procedural deformer 4: SCALES (colorFunc=12). Worley cell-edge displacement OUTWARD → raised cellular ridges. Same edge-distance math as old voronoi cracks but opposite sign. Spec fields: `scaleDepth`, `scaleDensity`. Use cases: dragon eggs, lizard hide, alligator skin, mud tiles, soccer-ball.
- shipped: **dragon egg** target — single ellipsoid + scaleDepth=0.005, scaleDensity=35. Reads as scaled creature surface from any panel.

### CRITICAL BUG fixed: cracks were silently no-op
- user diagnosis: "only additive is working" — meaning ONLY `d - delta` (subtraction = raised) modes were producing visible effects. `d + delta` modes (inward) were dead.
- root cause: my crack code used `abs(n - 0.5)` to find noise contour, but fbm3 returns ~[-0.5, +0.5] CENTERED ON ZERO (not 0.5). So `abs(n - 0.5)` was usually large (~0.5), NEVER below threshold 0.06. The displacement triggered ~0% of pixels → effectively zero crack effect.
- bumps had similar bug: `let n = fbm3(...) - 0.5` shifted the centered noise to be mostly negative → bumps inverted to inward.
- fix: use `abs(n)` for crack contour (n=0 is natural distribution center); remove `- 0.5` from bumps (n already centered).
- after fix: cracks at crackDepth=0.030 produce DRAMATIC INWARD silhouette gouges as expected. Confirmed inward direction by silhouette notching.

### lesson: when SDF math feels right but visuals don't match, check FBM/noise output range
- standard Perlin/FBM implementations vary: some return [0,1], some [-1,1], some [-0.5,0.5]. Sign and offset matter for thresholding.
- fbm3 in this engine: ~[-0.5, 0.5] centered on 0. Easy to miscount.

### deformer 5: WOOD GRAIN (colorFunc=14)
- directional sinusoidal stripes along Y axis, FBM-warped for natural curve
- spec fields: `grainDepth`, `grainDensity`. Inward (sunken) lines.
- shipped: wooden plank target — single roundedBox + grainDepth=0.002, grainDensity=25. Reads as wood with grain.

### deformer toolkit summary (5 modes, geometry-only)
| mode | colorFunc | direction | shape | use case |
| cracks | 9 | inward | line networks | stone fractures |
| pits | 10 | inward | round craters | meteorites, rust |
| bumps | 11 | outward | smooth lumps | leather, hide |
| scales | 12 | outward | cellular ridges | dragon, lizard |
| grain | 14 | inward | directional stripes | wood, bark, fibre |
- pattern is solid: noise/Worley + threshold + smoothstep falloff + sign of displacement
- new modes drop in via the same overload (`{type}Depth`, `{type}Density`)

### A* PROTO landed — path-based subtractive cracks
- new field `pathCarves: Array<{from, to, thickness?, depth?}>` on ModelerPrim
- modeler-side `expandPathCarves(parent, carves)` converts each segment to a subtractive box prim:
  - midpoint position, length = segment distance
  - rotation around Z to align local +Y axis with the segment direction
  - inherits parent's blendGroup, blendRadius=-0.002 for clean subtract
- ZERO engine changes — entirely modeler-side, uses existing primitive types + CSG ops
- shipped: **wall with branching crack** target — manually-authored 6-segment branching zigzag crack on a stone wall slab
- this is the geometry pipeline that A* would feed. A* generates the waypoint list, expandPathCarves builds the subtractive geometry.

### two complementary crack systems
- **`crackDepth`** (procedural, colorFunc=9): uniform random network via noise band. Mass-production weathering.
- **`pathCarves`** (path-based, expansion): specific intentional damage along authored waypoints. Hero props, "the impact crack from the dragon hit."
- can be combined on same prim — procedural background weathering + intentional routed damage.

### A* PROTO (full): auto path generation landed
- new field `crackPathGen: { start, end, segments?, seed?, branchiness?, thickness?, depth? }` on ModelerPrim
- modeler-side `generateCrackPath()` runs a seeded LCG random walk from start to end:
  - main spine: N waypoints with perpendicular jitter (XY plane)
  - branches: optional side spurs at each waypoint (probability = branchiness)
  - output: same shape as `pathCarves` (list of `{from, to}` segments)
- `expandPathCarves` then turns each segment into a subtractive box prim
- DETERMINISTIC: same seed = same crack pattern. Critical for reproducible shipping.
- shipped: stone wall with seed=42 auto-generated branching crack. Visible from all panels.
- **A* extension path**: replace the random walk with grid-based A* over a cost field. Same input/output shape; same downstream geometry.

### A* polish — Catmull-Rom smoothing landed
- new helpers: `simplifyPath()` (collinear pruning) + `smoothPath()` (Catmull-Rom spline, 3-4 sub-samples per segment)
- A* output now flows through smoothing before being expanded to subtractive boxes
- removed simplify (was overzealous, killed meandering); kept Catmull-Rom
- visible result: path now has gentle curves between A* waypoints instead of cardinal stairsteps
- still-known visual: discrete dimples per segment when thickness is small. Solutions for cleaner continuous groove:
  - increase carve box thickness (boxes overlap → smooth-subtract merges)
  - reduce per-carve blendRadius for sharper cuts
  - or generate continuous capsule geometry instead of box-per-segment

### A* IMPLEMENTATION LANDED
- new `mode: 'astar'` on crackPathGen → routes via grid-based A* instead of random walk.
- 8-connected grid over the start-end bounding box (gridRes 28 default, tunable).
- per-cell cost = `1.0 + hash(cell, seed) * noiseWeight` (higher noise weight = more meandering).
- heuristic = euclidean distance to goal (admissible, optimal A*).
- CPU-side, deterministic per seed, no engine changes.
- shipped: wall with A* routed crack.
- known artifact: 8-connected paths show cardinal stairstepping. POLISH options:
  - bump gridRes (32, 48, 64) for finer steps
  - post-process with Catmull-Rom smoothing through waypoints
  - 16-connected grid (more directions, more cost)
- this is the FULL A* PIPELINE for visible cracks. Same shape applies to:
  - rivers carved into terrain (cost field = elevation)
  - root systems (cost field = nutrient/water density)
  - cable runs (cost field = obstacle penalty + length)
  - lightning forks (cost field = atmospheric resistance, branch from spine)

### bell — 2 rounds ✅ shipped
- r1: cone primitive — too sharp at the apex (looked like a witch's hat / Christmas-tree ornament, NOT a bell)
- r2: SUP sphere with positive yClip (yClipN=+0.3 clips top 30%) for proper rounded bell-shape with flat top
- **reusable pattern**: rounded body + flat top = SUP with positive yClipN. Use for bells, kettle helmets, pot lids, drum bodies. Cone gives apex; SUP-yClip gives flat closure.

### tombstone — 3 rounds ✅ shipped
- r1: SUP sphere arch — too round, sphere extended 7cm in Z while body was 1.2cm thick. Looked like pin head on stick.
- r2: thin Z-axis disc replaces sphere. Body absorbs bottom half via smooth-blend → clean half-circle arch.
- r3 damaged: r2 + big diagonal subtractive crack (rotated 25°) + 2 chipped corners (subtractive boxes at top) + bumped blend radius from 0.004 → 0.008 for cleaner primitive seams. Reads as ancient damaged grave marker.
- **two damage paradigms**: (1) procedural cracks (`crackDepth`) for uniform weathering, (2) CSG subtractive prims for specific intentional damage (chipped corners, big single cracks). Use both together for full dramatic effect.
- **reusable pattern**: rounded-top vertical slab = rectangular body + thin Z-axis cylinder smoothly blended on top. Tombstones, doors, gates, signs.
view-modes available: color (lit), normal, depth, silhouette, curvature, per-surface
new primitives landed mid-loop: trapezoidalBox (type 21), band (type 22)
new spec fields: tipDelta (Vec3, for bentCapsule), repeats (linear + rotational scatter)
atlas: 512×512 with cm grid bg, panel labels (HTML overlay), 6 view-modes
mid-loop engine extensions in total: 9 (silhouette + tipDelta + trapezoidalBox + band + linear-scatter + rotational-scatter + 256² atlas + grid bg + curvature/per-surface modes)

## Engine extension landed mid-loop
- Added `tipDelta?: Vec3` field to ModelerPrim (modeler_demo.ts) so bentCapsule (type 14) is now driveable from the spec.
- Slot-overload limitation: bentCapsule prims can't have BOTH rotation AND tipDelta because the engine reuses slot 4 for both. Workaround for orientation flips: use other primitives (torus arc for bow worked).

## User requests pending design / implementation
1. ✅ **silhouette view-mode** — DONE. White-on-black binary mask, no lighting/checker. Use for reference matching.
2. **per-prim color view-mode** — pending (~30 LoC).
3. **scatter / replicate operators** (`repeatLinear`, `repeatRotational`, `repeatGrid`) on ModelerPrim — same expansion pattern as mirrorYZ, ~50 LoC. Pure spec-readability win (raymarch cache makes runtime cost zero).
4. **bentCapsule with rotation** support — would require either modifying engine (move tipDelta out of slot-4) or applying CPU-side rotation to local frame before SDF eval. Bigger surgery.
5. **bezier-profile-capsule exposed in modeler** — type 17, swept capsule along quadratic bezier with cubic radius profile. Needs multi-bone scaffolding (3 fake bones to encode the 3 control points). ~1 day. THE primitive for angular curves and tapered limbs.
6. **`sdTrapezoidalBox` new primitive** — clipped pyramid / truncated wedge for blades, gun stocks, bezels. ~30 LoC WGSL + modeler exposure. High utility unlocks knife-blade, sword-blade-cross-section, gun-stock-taper, pyramid-frustum.
7. **`sdBentBox` new primitive** — rectangular cross-section swept along bezier. Same multi-bone scaffolding as type 17. ~50 LoC WGSL.
8. **shape-macro abstraction layer** — high-level operators (`arc`, `recurveArc`, `taperedSweep`) that expand to multi-prim subgraphs at upload. Days of work but transformative for spec readability.
9. **named materials library** + per-prim `material` tag — separate post-loop authoring pass, decouples geometry from appearance.
10. **headless render** for tab-independent agent loop — needs ARM64 + WebGPU + display-server work to unblock.
partial: kettle helmet (r1)
techniques validated:
1. cylinder + ellipsoid in same group = bulged-body shapes (barrel, urn)
2. wide blendRadius between two cylinders of different radius = free shoulder taper (bottle)
3. mirrorYZ = 2× authoring multiplier for symmetric features (crate grooves + brackets)
4. signed blendRadius (negative) = subtractive carving (crate plank grooves, wrench openings)
5. rotationDeg = lets one primitive type cover many roles (gun barrel, gun trigger guard, asymmetric flask neck)
6. roundedBox with corner=small + smooth-blend to cylinder = clean shape morphology between rectangular and round (polygonal flask)
7. hard-union (group 0) for additive distinct features (barrel hoops, gun parts), smooth-blend (group 1) for fused organic shapes

## /loop iter 10 (post-summary): polish A* path-carve continuity
- **Symptom:** A* `astar` mode produced visible chain of dimples instead of a continuous fracture groove. Each waypoint segment was a thin box that didn't quite touch its neighbors.
- **Fix 1 (overlap):** in `expandPathCarves()` (modeler_demo.ts:692), extended each segment's half-length by `thickness * 1.5` so consecutive segments overlap. Smooth-subtract (blendRadius=-0.002) then fuses them into one groove.
- **Fix 2 (rounded ends):** swapped carve primitive from `box` (type 1) → `roundedBox` (type 2) with corner radius = `thickness * 0.9`. Endpoint joints now meet as smoothly-rounded capsules-equivalents instead of hard square ends.
- **Engine win — domain-warped cracks:** WGSL crack deformer (colorFn=9) now warps the input coord with an independent low-freq FBM field before the main FBM lookup. Matches the technique already used by pits/scales. Crack contours read as natural fracture lines instead of regular FBM-band signature.
- **Test spec:** wall_astar_v4_continuous.json (gridRes=28, noiseWeight=4, smoothing on). Same start/end as v3 to allow A/B compare.
- **Reusable principle:** when stamping subtractive prims along a path, ALWAYS overlap segment lengths beyond endpoints (factor of thickness or larger) and use a primitive with rounded ends. Square box ends + zero overlap = dimple chain; rounded ends + overlap = continuous groove.

## /loop iter 11: deformer library expansion — ridges + streaks
- **New WGSL deformer 15: ridged multifractal** (raymarch_renderer.ts:1077-1108). 4-octave fold-and-square (`1-|n*2|` then `r*r*prev`) with domain warping. Different look from FBM-band cracks — gives ONE prominent ridge per noise period, not band-pair edges. Use cases: mountain spines, sword fullers, knot bark, creature dorsal ridges.
- **New WGSL deformer 16: erosion streaks** (raymarch_renderer.ts:1109-1132). Gravity-aligned vertical drips. Two FBM fields combine: high-freq column-pick (smoothstep at 0.45/0.55 selects which columns drip) × vertical-falloff (clamped 0.5 - y*5 → fades as y rises). Modulated by jitter FBM so streaks aren't uniform stripes. Use cases: rust runs, water staining, weathered metal.
- **Modeler wiring**: new fields `ridgeDepth/ridgeDensity` and `streakDepth/streakDensity` exposed on ModelerPrim with same overload pattern as crack/pit/scale (slot 2.w = depth, slot 3.y = density via colorExtent). Wired through normalizer so JSON specs round-trip cleanly.
- **Stacking limitation observed**: two prims at the same world position with DIFFERENT blendGroups hard-union (whichever has lesser SDF wins). For layered deformers on one surface (e.g. ridges + streaks together) we'd need either (a) a multi-deformer slot in evalPrim, or (b) two prims with identical SDF and SAME blend group with carefully-tuned blendRadius. Filed for future iteration.
- **Test spec**: ridge_spine_slab.json (60×60mm slab, ridgeDepth=0.004, ridgeDensity=16). Streaks demo deferred to next iteration to avoid the stacking-group confusion.
- **Library state**: 7 procedural deformer modes total — cracks (9), pits (10), bumps (11), scales (12), veins (13), grain (14), ridges (15), streaks (16). Plus A* and random-walk path generators with overlap+roundedBox carves.

## /loop iter 12: periodic-lattice deformers — hex tiles + brick masonry
- **New WGSL deformer 17: hex tiles** (raymarch_renderer.ts). Periodic pointy-top hex lattice using two interlocking offset rectangular grids; pick whichever cell center is closer (`select(b, a, dot(a,a) < dot(b,b))`). Edge distance uses standard pointy-top hex formula `0.5 - max(|qx|*sqrt(3)/2 + |qy|*0.5, |qy|)`. Light domain warp (0.3 amplitude) breaks perfect regularity without losing hex recognition. Sci-fi armor, honeycomb, alien skin.
- **New WGSL deformer 18: brick masonry**. 2:1 running-bond tiling — alternate rows offset by half a brick. Domain-warped slightly. Distance to nearest mortar joint via `min(brickSize.x*0.5 - |local.x|, brickSize.y*0.5 - |local.y|)`. Architectural staple: stone walls, dungeons, chimneys.
- **Modeler wiring**: `hexDepth/hexDensity` and `brickDepth/brickDensity` exposed on ModelerPrim with same overload pattern.
- **Test spec**: hex_armor_plate.json (60×60mm slab, hexDepth=0.0025, hexDensity=35).
- **Lattice technique notes**:
  - For periodic patterns, `pp - s * floor(pp/s + 0.5)` gives local position in [-s/2, +s/2] relative to nearest cell center.
  - For two-grid interlocking patterns (hex), evaluate against both grids and pick closer center.
  - Domain warping the input coord (NOT the cell index) makes lattice "wobble" while staying topologically correct — no missing/duplicated cells.
  - Mortar grooves work by mapping edge-distance through smoothstep then ADDING to d (sunken).
- **Library state**: 9 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18). Plus A* + random-walk path generators with overlap+roundedBox carves.

## /loop iter 13: river path generator — dual-layer profile + meander
- **New path-profile system**: `crackPathGen.profile` field accepts `'crack' | 'river' | 'channel'`. Default 'crack' = single thin square carve (current behavior). 'river' = dual-layer U-shape (wide shallow `t*3, d*0.4` + narrow deep `t*0.7, d` stacked at same path). 'channel' = single wider rectangular trough (`t*2, d`).
- **Meander**: optional `meander` (amplitude in m) + `meanderFreq` (cycles along path). Applied AFTER A*/walk pathing AND smoothing. Perpendicular perturbation in XY computed via central-difference tangent → rotate 90° → multiply by sin(u*freq*2π) * sin(u*π) taper. Endpoints pinned. Lazy bend at amp~0.005, tight wiggle at amp~0.015.
- **Helper extracted**: `emitCarvesFromPath(wp, t, d, profile)` consolidates segment→carve emission. Used by both A* and random-walk generators so any new profile mode benefits both.
- **Dual-layer rationale**: the U-shape comes for free from smooth-subtract: outer wide shallow box subtracts a broad shallow channel; inner narrow deep box subtracts a deeper center. Smooth-blend across same path eliminates seam between the two layers — reads as a single carved channel with sloped banks.
- **Branches stay 'crack' style** even when main path is 'river' — branches model tributaries / hairlines feeding the main flow, not parallel rivers.
- **Test spec**: river_meander_v1.json (60×60 slab, gridRes=24, meander=0.005, meanderFreq=4, profile='river'). Same start/end as the v4 crack so direct A/B compare is possible by toggling profile.
- **Library state**: 9 deformer modes + 3 path profiles (crack/river/channel) + meander on both walk and A* generators. The `profile` mechanism is extensible — adding a new cross-section now means one more case in `emitCarvesFromPath` plus a literal in the type union.

## /loop iter 14: Voronoi cracks + scratches (and a regression caught)
- **REGRESSION CAUGHT**: 500 error on modeler_demo.ts at runtime. Root cause: backticks inside WGSL comments (mode-17 hex referenced `scaleDepth`, mode-20 scratches referenced `grain` in comments) — backticks close the TS template literal that wraps the WGSL shader, breaking compile. Same bug pattern as the earlier fbm3-comment incident logged in iter 5. Permanent rule for this file: **never write backticks inside WGSL comments**. Use plain words or single quotes if a name needs to be quoted.
- **New WGSL deformer 19: Voronoi cracks**. True F1-F2 bisector-distance fracture network. Two-pass cellular: find F1 (nearest cell point), then F2 with bisector projection (`abs(dot(pp - midpoint, unit_normal))`) for accurate edge distance. Distinct from mode 9 (FBM-band cracks) — gives clean geometric cell-network look (dragon-egg, dried mud, broken tile). Mild domain warp on input so cells aren't textbook-perfect.
- **New WGSL deformer 20: scratches**. Sparse directional strokes along local +X. Per-line random hash gates ~30% of lines (sparse, not parallel-stripes like grain). Per-line length-along-X mask via FBM gives partial-length scratches. Low-freq vertical FBM bends individual scratches slightly so they're not ruler-straight. Brushed-metal / weapon-wear look.
- **Modeler wiring**: `voronoiCrackDepth/Density` and `scratchDepth/Density` plumbed through ModelerPrim → specToPrims → JSON normalizer.
- **Test spec**: voronoi_cracked_egg.json (40×55×40mm ellipsoid, voronoiCrackDepth=0.0025, voronoiCrackDensity=22).
- **Compile-verified** — `tsc --noEmit` clean before staging spec.
- **Library state**: 11 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18), voronoiCrack(19), scratches(20). Plus 3 path profiles (crack/river/channel) + meander on both walk and A*.

## /loop iter 15: lightning bolt path generator + linear taper
- **New path mode 'lightning'** — `generateLightningPath()` uses classic midpoint-displacement recursion. Each pass doubles segment count by inserting a midpoint perpendicular-displaced by `jaggedness * 0.5^level * segLen`. Default `lightningDepth=6` → 64 main-bolt segments. Sharp segments (no smoothing); jagged-look IS the goal.
- **Cascading branches** — at recursion levels 0–2 (coarsest), each midpoint has `branchiness` chance of spawning a sub-bolt. Each sub-bolt is a recursive call to `generateLightningPath` itself with: shorter range (`0.6 * 2^-(level+1)`), steeper taper (0.95), 60% thickness, 70% depth, no further branching (would explode quadratically).
- **Linear taper** — new `taper` field works on ALL path generators (walk, A*, lightning). 0=uniform, 1=fade to zero. Taper applied at the segment-emit step (`emitCarvesFromPath`); no need to plumb it through each generator's interior. Lightning defaults to taper=0.7 (cloud→strike); rivers default to no taper; cracks no taper.
- **Generator dispatcher** in specToPrims now switches on three modes: `walk → astar → lightning → walk`.
- **JSON normalizer** updated to round-trip `taper`, `lightningDepth`, `jaggedness`, and to accept `'lightning'` in the mode validation.
- **Compile-verified**: `tsc --noEmit` clean.
- **Test spec**: lightning_bolt_v1.json (60×80mm tall slab, lightningDepth=6, jaggedness=0.4, branchiness=0.3, taper=0.6). Vertical bolt top→bottom for the classic strike pose.
- **Library state**: 11 deformer modes + 4 path-gen modes (walk/astar/lightning/-) + 3 path profiles (crack/river/channel) + meander + taper.
- **Reusable principle**: *taper at emit-time, not at gen-time*. Path generators concern themselves with WHERE the path goes; profile and taper are post-processing on the waypoint list. Adding new path features (sphere-tip, capsule-cap, varying-density) drops in at the same `emitCarvesFromPath` hook without touching A*/walk/lightning internals.

## /loop iter 15.5: Vite oxc parse bug — `A*/walk` closes JSDoc
- **Symptom**: tsc clean, but Vite reload showed `[PARSE_ERROR] Unexpected token` at modeler_demo.ts:204. Vite uses oxc which is stricter than tsc on comment delimiters.
- **Root cause**: I wrote `After A*/walk pathing` inside a JSDoc comment. The `*/` is the JSDoc-close sequence — oxc closed the comment there and treated the rest as code.
- **Fix**: insert a space → `A* / walk`.
- **Permanent rule**: never write `*/` inside a JSDoc/block comment for any reason. Slash forms used in prose: `A* / walk`, `walk / astar`, etc — always with surrounding space. (Same class as the WGSL-backtick bug from iter 14: comment delimiters that overlap with prose syntax.)

## /loop iter 16: regular-grid deformers — dimples + studs + chevrons
- **Backed out architectural multi-deformer-stacking refactor mid-iteration**: bumped PRIM_STRIDE_FLOATS from 20 → 24 to add a second-deformer slot, then realized the inline 338-line if/else chain in `evalPrim` would need to either become a function (long surgery) or be duplicated (ugly). Reverted to baseline; mult-deformer stacking is filed for a focused future iteration where the only goal is the refactor.
- **New WGSL deformer 21: dimples**. Regular grid of sunken sphere indents. `pp - floor(pp + 0.5)` gives [-0.5,0.5] cell-local, `length(local)` = radial dist, smoothstep falloff. Light domain warp (0.15 amplitude) breaks lattice. Use cases: golf ball, hammered metal, perforated panel, leather pebbling.
- **New WGSL deformer 22: studs**. Inverse of dimples — same grid math, opposite sign on `d`. Raised hemispheres. Domain warp 0.10 (slightly less because studs need to read as discrete dots, not blob). Rivets, tactile D-pad, studded leather.
- **New WGSL deformer 23: chevrons**. V-shape raised ridges along local +Y. Per-row Y-step (`floor(y * density)`), local x folds via `abs(x*density) % 1.0`, V-distance via `abs(yLocal - 0.5 - xLocal*0.5)`. Domain-warped so V-rows aren't perfectly aligned. Arrow pavement, textured grip, herringbone leather, military stencils.
- **Modeler wiring**: `dimpleDepth/Density`, `studDepth/Density`, `chevronDepth/Density` plumbed.
- **Test spec**: studded_plate.json (60×60mm, studDepth=0.0030, studDensity=36).
- **Library state**: 14 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18), voronoiCrack(19), scratches(20), dimples(21), studs(22), chevrons(23). Plus 4 path-gen modes + 3 path profiles + meander + taper.
- **Family map**:
  - **Organic-irregular**: bumps, scales, voronoiCracks, ridges (FBM/Voronoi)
  - **Organic-natural**: cracks, pits, veins (FBM-band)
  - **Directional**: grain, streaks, scratches, chevrons (axis-aligned with FBM warp)
  - **Periodic**: hex, brick, dimples, studs (regular lattices)
- The four families now cover most useful surface treatments. Future expansion: triplanar projection (better noise on heavily curved surfaces), multi-deformer stacking (compositional layering), or domain-specific generators (lichen, moss, frost crystals).

## /loop iter 17: multi-deformer stacking (wear-slot architecture)
- **Architecture: secondary wear-deformer slot.** Bumped PRIM_STRIDE_FLOATS 20 → 24 (6 vec4f per prim). Slot 5 carries (wearFn u32, wearDepth f32, wearDensity f32, _pad). Updated all `* 5u` → `* 6u` reads in WGSL (3 sites: evalPrim, occlusion loop, hit shading) and all `i * PRIM_STRIDE_FLOATS` writes (auto via constant). Added u32[base+20] / f32[base+21..23] in CPU-side packPrim block.
- **Constrained API**: only 4 wear modes supported as secondaries (bumps/grain/streaks/scratches — the FBM-based "weathering" patterns). Structural patterns (cracks/hex/scales/voronoi/etc.) only run as primaries. The wear-block in WGSL is ~30 lines instead of duplicating the 338-line primary chain. Realistic compositional case is one structural + one weathering, not two structurals.
- **Compositionality**: secondary runs AFTER primary in evalPrim, so its displacement adds to whatever the primary computed. Two SUNKEN modes both add to d → both visible. Two RAISED modes both subtract → both visible. RAISED primary + SUNKEN wear (e.g. studs + scratches) compose as expected.
- **Modeler API**: `wearDeformer?: { type, depth, density? }` field on ModelerPrim. Type union enforces only the 4 valid wear modes. Wired into specToPrims (after the primary if/else chain) and into the JSON normalizer.
- **Test spec**: weathered_hex_armor.json — hex primary + streaks wear → rust-runoff on tessellated armor.
- **Why this is the right scoping**: I tried the unconstrained version last iteration (any deformer × any deformer = 14² = 196 combinations, requires the 338-line primary chain to become a function or be duplicated). Backed out. The constrained wear-slot version unlocks 14×4 = 56 useful combinations with ~30 LoC of WGSL and zero refactor. The primary chain stays readable.
- **Library state**: 14 primary deformers + 4 wear deformers (composable) + 4 path-gen modes + 3 path profiles + meander + taper + stride-6 layout.
- **Future extension hooks**: slot 5 still has padding (slot5.w unused). Could carry a wear-rotation angle for orienting directional wear (grain/scratches/streaks) without rotating the parent prim.

## /loop iter 18: color-aware deformers — geometry AND palette pick
- **Insight**: until now the new deformers (10-23) produced DISPLACEMENT only — surface stayed paletteSlot-A everywhere, so a hex plate with sunken mortar grooves still rendered as one uniform color. The original colorFunc=9 (cracks) had BOTH geometric and color-side logic; the others didn't. Standard SDF workflows require authoring two parallel systems for "dark mortar that's also sunken". Unifying them so one deformer drives both unlocks major visual quality with zero extra spec.
- **Color-side WGSL added** for 5 periodic/cellular deformers in the `colorPick` switch: hex(17), brick(18), dimples(21), studs(22), chevrons(23). Each branch re-runs the same mask math used in evalPrim's geometric pass — Voronoi for hex, offset-row for brick, radial for dimples/studs, V-distance for chevrons — and picks slotB when inside the deformer band. (Mode 19 voronoiCracks already had legacy color logic from iter 0; left as-is for now.)
- **Palette infra**: added slot 2 = brighter variant (1.45× MATERIAL_RGB, clamped to 1.0). Slot 0 = base, slot 1 = darker (0.55×) — already existed for stripe/dot — slot 2 = brighter for raised features.
- **Sensible per-mode defaults**:
  - SUNKEN deformers (hex, brick, voronoiCrack, scratches, dimples) → paletteSlotB defaults to slot 1 (dark accent).
  - RAISED deformers (studs, chevrons) → paletteSlotB defaults to slot 2 (bright accent).
- **Override hook**: new `accentSlot?: number` field on ModelerPrim lets the user pick any palette slot 0-31 if defaults aren't right. JSON normalizer round-trips it.
- **Scope-limit decision**: only periodic/cellular deformers got color-aware treatment this iteration. The organic-natural family (cracks-FBM, pits, bumps, veins, grain, ridges, streaks) doesn't get color picks — those are micro-details where geometry alone reads correctly, color contrast there is more "noise" than "feature". Can add later if needed.
- **Test spec**: color_aware_hex_v2.json — same plate as iter-12 hex_armor_plate, but now mortar reads as visibly DARK between bright tile faces, not just shaded geometry.
- **Reusable principle**: when geometry and color are the SAME mathematical mask (cell boundaries, lattice grooves, raised tops), implement them as TWO branches running the SAME math — once in displacement, once in color pick — driven by ONE field. Avoid making the user author both sides.

## /loop iter 19: tree path generator + scales color-aware
- **New 'tree' path mode** — `generateTreePath()`: recursive Y-fork from `start` along `direction` (default +Y). Each segment spawns `branches` children at ±branchAngle (default ±28°), with per-level decay on length (lengthDecay=0.7 default) and on thickness (thicknessDecay=0.7). Per-branch length jitter ±20% for natural variation. Tree handles its OWN taper via thicknessDecay; emit-time `taper` skipped on the trunk path. Profile `'river'`/`'channel'` re-routes through emitCarvesFromPath; default `'crack'` uses the per-segment thickness/depth directly.
- **Branch-count semantics**: `branches=1` → straight whippy line, `branches=2` → Y-fork (default), `branches=3` → trident (good for trees), `branches=4-6` → candelabra / coral. Splay distributes evenly across `[-half, +half]`. Capped at 6.
- **Recursion safety**: treeDepth capped 1-7. At branches=2, depth=5 → 31 segments. At branches=4, depth=5 → 1024 segments. Quadratic warning is in the JSDoc.
- **Use cases**: bare-branch trees, vine systems, vasculature, neural dendrites, antlers, coral, blood vessels, lightning-with-multiple-strikes (set branches=3+ for fork-heavy bolts).
- **Color-aware scales (mode 12)** — added F1-F2 bisector color pick to the existing geometric ridges. Cell edges now darken (slot 1 default) so dragon-scale ridges read as actual ridge LINES, not just shaded bumps. Modeler default updated to `accentSlot ?? 1` for scales.
- **Compile-verified**: tsc clean.
- **Test spec**: tree_carved_v1.json — 60×80mm tall slab, vertical tree from bottom edge with 5-level depth, ±30° branch angle.
- **Library state**: 14 primary deformers (6 color-aware: 9, 12, 17, 18, 21, 22, 23) + 4 wear deformers + **5 path-gen modes** (walk/astar/lightning/tree/-) + 3 path profiles + meander + taper + accentSlot override.
- **Family map for paths**:
  - **Stochastic**: walk (random spine + jitter)
  - **Cost-field**: astar (follows weak material)
  - **Self-similar**: lightning (midpoint-displacement + cascading branches)
  - **Recursive structural**: tree (Y-fork branching)
  - All four feed the same `emitCarvesFromPath` → profile/taper system.

## /loop iter 20: HEADLESS WEBGPU UNBLOCKED + path-gen perf fixes
- **🔥 HEADLESS WEBGPU IS WORKING.** Per the developer.chrome.com/blog/supercharge-web-ai-testing recipe, the correct flag set is:
  ```
  --no-sandbox --headless=new --use-angle=vulkan
  --enable-features=Vulkan --disable-vulkan-surface --enable-unsafe-webgpu
  ```
  Critical errors in my earlier attempts: I had `--use-vulkan` (wrong; correct is `--use-angle=vulkan`) and was MISSING `--disable-vulkan-surface` (which uses bit blit instead of swapchain so no display surface is required). With those fixed, `requestAdapter()` returns a real Vulkan adapter with 24 features. NVIDIA driver 580 + libvulkan1 + libnvidia-gl-580 already on the box; nvidia_icd.json present in `/usr/share/vulkan/icd.d/`. NO xvfb needed.
- **Probe result**: `{ hasGPU: true, adapterInfo: { features: [24 features incl. timestamp-query, subgroups, texture-compression-bc/etc/astc, dual-source-blending] }, modelerReady: true }`. Vite serves the modeler on :5173, headless Chromium loads it, WebGPU initializes against the real GPU, modeler module API exposed.
- **Path-gen perf fixes** (the user reported "browser hangs my computer so bad"):
  - `lightningDepth` default 6 → 5 (64 → 32 main segments)
  - `treeDepth` default 5 → 4 (31 → 15 segments)
  - A* `smoothPath` samples 3 → 2 (halves carve count after smoothing)
  - **Soft cap**: `decimateCarves(carves, 150)` uniformly drops segments when over budget. Logs warning. Silhouette stays right (uniform decimation), inner detail loses some fidelity.
- **Test spec**: perf_check_simple_crack.json — A* crack with profile='crack' (single layer, no river dual-bloat), gridRes=20 → ~30-50 carve prims after smoothing.
- **Reusable principle**: in a live-orbit live-render modeler, every authored prim is in the per-frame critical path. Authoring tools that emit hundreds of small prims need budget-awareness — either decimation or a primitive-chain SDF that bundles many segments into one prim. Decimation is the cheap fix; chain-prim is the right fix.

## /loop iter 21: AGENT SELF-VALIDATION LOOP COMPLETE
- **End-to-end verified**: spec → write inbox.ark.json → `modeler_driver.mjs null <out.png>` → 4-view atlas PNG written. Round-tripped 3 specs:
  - perf_check_simple_crack (A* crack, single layer): visible diagonal crack on slab, all 4 views render
  - weathered_hex_armor (hex primary + streaks wear): hex tiles with dark mortar grooves CLEARLY visible (color-aware iter 18 confirmed), bottom hexes show slight vertical wash from the streak wear (composition confirmed)
  - tree_carved_v1 (tree gen, treeDepth=4): vertical trunk + 4-level recursive Y-fork visible across all views, branches taper to twigs as designed
- **modeler_driver.mjs updates**:
  1. Replaced `headless: false` (xvfb path) with `headless: true` + the working flag set: `--no-sandbox --headless=new --use-angle=vulkan --enable-features=Vulkan --disable-vulkan-surface --enable-unsafe-webgpu`
  2. `goto({waitUntil: 'networkidle'})` → `'domcontentloaded'`. networkidle never settles for the modeler (continuous render loop + VL inbox poller keep traffic flowing).
- **VL inbox poller race**: passing `specJson` to setSpec gets overwritten by the inbox poller. Workaround: write the spec to `public/sdf_modeler/inbox.ark.json` BEFORE invoking the driver, pass `null` as the driver's spec arg. Future polish: add a `?nopoll` URL flag the driver appends so setSpec wins. For now the inbox-write pattern works.
- **Lock-in for the loop**: from now on every spec change can be visually verified before claiming success. Replaces "tsc passed → ship it" with "render + inspect → ship it".
- **Multimodal Read tool advantage**: PNG outputs from the headless render are directly inspectable in this conversation context — same path the user uses to verify, no extra VLM hop needed.

## /loop iter 22: live HTML preview viewer + tendril path generator
- **Live preview HTML page** at `public/sdf_modeler/preview.html` (served by Vite at http://localhost:5173/sdf_modeler/preview.html). HEAD-probes preview.png for Last-Modified header to avoid re-downloading unchanged frames; cache-busts via `?t=${mtime}` only when fresh. Refresh-rate dropdown 1s/2s/5s/10s/paused; status pill goes orange after 30s of no updates so a stopped daemon is obvious.
- **Daemon default output moved** from `~/modeler_preview.png` → `public/sdf_modeler/preview.png` so Vite serves it. Removes the homedir dependency; everything self-contained under the engine scaffold.
- **New 'tendril' path mode** — `generateTendrilPath()`: continuous-curvature winding line. Heading rotates each step by `Math.sin(t*1.4*2π+offA) * curl + Math.sin(t*4.3*2π+offB) * curl*0.25` — low-freq drift + slight high-freq wobble, both deterministic from seed. NO branches, NO jitter — one smooth winding line. Different from `walk` (jitter) and `tree` (branching).
- **Use cases**: vines, tentacles, hair strands, ribbon trails, lazy river meanders without A* cost.
- **Self-validated via headless capture** (tendril_atlas.png): visible smooth S-curve carved across slab in all 4 views. Front and ISO show the curve clearly; side shows the depth carve consistent across length.
- **Library state**: 14 primary deformers (10 color-aware) + 4 wear deformers + **6 path-gen modes** (walk/astar/lightning/tree/tendril/-) + 3 path profiles + meander + taper + accentSlot.
- **Path-gen taxonomy**:
  - **Stochastic**: walk (random spine + jitter)
  - **Cost-field**: astar (follows weak material)
  - **Self-similar**: lightning (midpoint-displacement + branches)
  - **Recursive structural**: tree (Y-fork branching)
  - **Continuous curvature**: tendril (smooth turns, no branches)
  - All 5 feed `emitCarvesFromPath` → profile/taper/decimateCarves system.

## /loop iter 23: whorl deformer (radial — fingerprint / tree-rings)
- **New WGSL deformer 24: whorl**. Concentric rings around the local origin in XY plane. Radius `length(pWorld.xy) + warp * 0.012` is FBM-warped so rings aren't perfect circles — they wave and pinch like fingerprints or tree growth rings. Sin oscillation `sin(r * density * 6.283)` defines ring lines; smoothstep band gives sunken contours. Pure radial — no Voronoi/lattice/FBM-band like every other mode. Use cases: fingerprints, tree-stump growth rings, sliced fruit cross-sections, contour topo lines, target patterns, wood end-grain, zen-garden ripples.
- **Color-aware from the start** — slot 1 dark accent default. The same ring-distance test (`abs(s) < 0.20`) runs in colorPick so rings darken visibly, not just sink.
- **Modeler wiring**: `whorlDepth/Density` plumbed through ModelerPrim → specToPrims → JSON normalizer.
- **Self-validated headlessly** (whorl_atlas.png): clean concentric rings on all 4 views, depth carve consistent across slab. FBM warp at default density (24) is subtle — rings look mostly circular; bump density 30+ to enter fingerprint territory (tighter rings, more visible warp pinch).
- **Library state**: 15 primary deformers (11 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot + decimateCarves cap.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - **Radial**: whorl ← new family
- The radial family had no representative until now — every other mode was either Cartesian (lattice/grid), grid-cellular (Voronoi), or signal-band (FBM). Whorl establishes the polar/cylindrical pattern category.

## /loop iter 24: fishscale deformer (overlapping arc-rows)
- **New WGSL deformer 25: fishscale**. Offset-row tiling (like brick) where each cell's visible boundary is the BOTTOM HALF of an arc circle. Adjacent rows shifted by half-cell so the curved bottoms tuck into the gaps of the row above — interlocking overlap pattern. Domain-warped lightly. Distinct from `scales` (mode 12 Voronoi cells, irregular sizes) — fishscale is uniform and unmistakably tile-like.
- **Math**: cellSize=(2,1), offset rows by half-cell on odd rows, arc center at `(0, +cellSize.y/2)` with radius `cellSize.x*0.55`. Distance to arc circle gives shadow line; smooth gate `smoothstep(arcCenter.y+0.05, arcCenter.y-0.05, local.y)` restricts to the bottom half (the visible scale edge), avoiding double-arc artifacts above.
- **Color-aware from start** — slot 1 dark accent default, line darkens visibly as a real shadow.
- **REGRESSION CAUGHT (and fixed)**: backtick-in-WGSL bug recurred (`scales`). Same class as the iter-14 fbm3 incident and the iter-15 A*/walk JSDoc incident. Fixed by removing the backticks. Adding a stronger note to the agent log: **the WGSL block is wrapped in a TS template literal — backticks INSIDE the WGSL comments close the literal. Slash-modifiers (`*/`) inside JSDoc close those. Always strip both before writing prose comments.**
- **Self-validated headlessly** (fishscale_atlas.png): 4-view atlas shows the offset arc pattern across all faces, scales tucking into one another row-by-row, no double-arc artifacts at the half-circle gate.
- **Library state**: 16 primary deformers (12 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24, 25) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - **Periodic-organic**: fishscale ← bridges periodic regularity with organic-tile feel

## /loop iter 25: weave deformer (over-under two-axis fabric)
- **New WGSL deformer 26: weave**. Two perpendicular sin strands (`sin(pp.x*2π)`, `sin(pp.y*2π)`) with explicit over-under: `parity(floor(pp.x*0.5)+floor(pp.y*0.5))` picks which strand is on top per 2×2 strand-cell, so the surface reads as genuinely woven, not just cross-hatched. Strand peaks SUBTRACT from `d` → raised strands; gaps stay at the base surface. Light FBM domain warp (0.15 amplitude) so strands wave gently.
- **Why over-under matters**: cross-hatched (just `max(strandH, strandV)`) reads as a grid, not a weave. The parity flip in alternating large cells creates the characteristic basket-weave perception — the eye picks up that horizontal goes over vertical here, vertical goes over horizontal there.
- **Distinct from related modes**: grain(14) is single-direction stripes; chevrons(23) is V-pattern raised; brick(18) is offset-row sunken mortar. Weave is the first TWO-AXIS RAISED pattern.
- **Use cases**: woven fabric, basket weave, cane chair, mesh, chainmail, woven grass mat, wickerwork.
- **Modeler wiring**: `weaveDepth/weaveDensity` plumbed through ModelerPrim → specToPrims → JSON normalizer (modeler_demo.ts:196,1273,1901).
- **Self-validated via live preview daemon** (preview.png at density=22, depth=0.0030 on 60×60mm slab): all 4 views show the basket-weave pattern; over-under flip clearly visible on front/iso views, depth profile reads correctly on side/top.
- **Library state**: 17 primary deformers (12 color-aware) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - Periodic-organic: fishscale
  - **Two-axis raised**: weave ← new family
- **Process note**: live preview daemon (preview_daemon.mjs, 3s interval) replaces the per-iter modeler_driver.mjs invocation. Daemon stays warm against `modeler_demo.html`; iter just writes inbox.ark.json and the next 3s snapshot reflects it. Visit http://localhost:5173/sdf_modeler/preview.html for the feed.

## Cron-driven loop restarted 2026-04-25 23:5x — job 02939633
- New cron job `02939633`, every 10 min at :07/:17/:27/:37/:47/:57 (off the :00/:30 fleet hotspots). Auto-expires after 7 days.
- Roadmap (user-directed):
  1. **Continue surface patterns** — long tail of family expansions still possible (lichen, frost, basalt-columnar, more two-axis variants).
  2. **Reaction-diffusion (coral, brain)** — Gray-Scott style. The natural escalation past hand-tuned analytical patterns: emergent, parameter-tunable, gives true coral/zebra/brain-coral/leopard textures. Will need WGSL compute pass or an iterative dispatch — NOT a per-pixel SDF deformer like the existing 17.
  3. **Manhattan / Chebyshev pathfinding** for street and pipe layouts on building faces. New path-gen mode beyond walk/astar/lightning/tree/tendril — discrete grid pathing with L1 (Manhattan = right-angle, street-grid feel) or L∞ (Chebyshev = also-diagonals, mechanical/circuit feel). Authoring use case: extruded pipes + recessed conduits on building wall panels, sci-fi armor circuit traces, urban building facade layouts.
- Architecture note: items 2 and 3 are STRUCTURALLY different from the existing 17 deformers (which are all per-fragment WGSL math). RD needs state across frames or a fixed-iteration compute warm-up; pathfinding emits discrete prims like the existing path-gen system. So iter 26+ = path-gen extension first (drops in at `emitCarvesFromPath`), iter 27+ = RD architecture spike.

## /loop iter 26: Manhattan / Chebyshev metrics on A* pathing
- **New `metric` option on crackPathGen mode='astar'**: `'euclidean' | 'manhattan' | 'chebyshev'`. Single field switches three things atomically:
  - **NEIGHBORS topology**: manhattan = 4-neighbor (orthogonal only); euclidean/chebyshev = 8-neighbor.
  - **Diagonal step cost**: chebyshev = 1.0 (diagonals are free, 45° preferred); euclidean = √2; manhattan = N/A (no diagonals).
  - **Heuristic**: manhattan = `|dx|+|dy|`; chebyshev = `max(|dx|,|dy|)`; euclidean = `hypot`.
- **Polish-pass gate**: smoothPath (Catmull-Rom) only runs when metric='euclidean'. Manhattan/chebyshev paths stay ANGULAR — smoothing would round off the right-angle corners that ARE the visual signature.
- **Why one option, not new modes**: extending `astar` by a metric flag is a strict superset and ~20 LoC. A separate `'mechanical'` mode would have duplicated the cost-field, A* loop, and waypoint reconstruction. The behavioral difference IS just the metric.
- **Test spec**: manhattan_streets_v1 — 60×60×6mm facade slab + 3 manhattan A* carves forming an X-cross + center alley (gridRes=24, varying noiseWeight 0.5/1.5 for primary vs alley). Live preview confirmed: visible stair-step right-angle grooves on front + iso views, no curved corners. The angular signature reads cleanly.
- **Distinct authoring use cases enabled**:
  - **Manhattan**: street grids on building facades, wiring trunks, sidewalk layouts, plumbing risers — anywhere the visual language is "right angles only"
  - **Chebyshev**: PCB traces, sci-fi conduit layouts, steampunk pipework — where 45° diagonal segments read as "engineered" rather than organic
  - **Euclidean** (existing default): natural cracks following weak material — unchanged
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + **astar now has 3 metrics** + 3 path profiles + meander + taper + accentSlot. Path-gen taxonomy gains a new axis (metric) under the cost-field family.
- **Architectural note**: this is the cleanest kind of iter — extends an existing system via one new option, opens a whole new visual category, no new infrastructure. Compare to weave (iter 25) which was a new WGSL deformer (~30 LoC shader + ~10 LoC modeler wiring + slot bookkeeping). Path metric is ~20 LoC of pure JS branching.
- **Live preview latency lesson**: edited modeler_demo.ts 5× during iter; vite HMR reloaded each time; daemon's headless modeler had to re-init between reloads. User saw stale weave_v1 captures for ~30s. Future: batch related TS edits before triggering preview verification, or pause the daemon during edit bursts.

## Iter 27 candidate: T-junctions / branches for mechanical paths
- Streets and pipes have JUNCTIONS, not just isolated runs. Stack two manhattan A* carves currently produces a visible cross only because the user authored two paths that geometrically intersect. The next leverage: a `branches` field on astar mode that spawns N perpendicular sub-paths off the main spine at random waypoints (2-8). For pipes: T-fittings everywhere. For streets: side-streets off the avenue. Same cost-field logic, just N more A* runs from random main-path waypoints to grid-snapped endpoints.

## Iter 28 candidate: reaction-diffusion (Gray-Scott) — coral / brain / zebra
- Architectural spike: WGSL compute shader doing N iterations of Gray-Scott RD on a 2D grid (256² typical), output written to a storage texture. Surface deformer reads the texture by world-XY → uv mapping. ~150 LoC compute + ~30 LoC sampler. Tunable F (feed) and k (kill) → coral, brain-coral, zebra, leopard, fingerprint, chaos. Different category from any existing deformer because the pattern is EMERGENT, not analytical.

## /loop iter 27: raise-polarity flag on path-gen — pipes / conduits / cables on facades
- **New `raise?: boolean` field on `crackPathGen` and `pathCarves`**. Default false (existing carve-trench behavior). When true, segments ADD to parent (smooth union with positive blendRadius) instead of subtracting (smooth subtraction with negative blendRadius). Same magnitude (0.002) → predictable visual weight either polarity.
- **Threading**: emitCarvesFromPath gained 6th param `raise`, stamps onto each emitted carve. All 5 path-gen modes propagate (walk, astar, lightning, tree, tendril) plus the 2 inline pushes (walk-mode branches at line 670, tree-mode segments at line 924). Lightning's branch sub-paths inherit via `{...opts}` spread — no special handling needed. JSON normalizer round-trips `raise: true` on both `pathCarves` and `crackPathGen`.
- **expandPathCarves switches blend sign per-carve**: `blendRadius: c.raise ? 0.002 : -0.002`. Per-carve granularity (not per-prim) means a single path-gen could in principle mix raised + carved segments — currently the modes emit homogeneous polarity, but the door's open for hybrid effects later (e.g., a pipe with carved valve cutouts).
- **Why a polarity flag, not a new mode**: every existing path-gen mode (astar/walk/lightning/tree/tendril) gets raised variants for free. Adding "pipe" / "conduit" / "cable" as separate modes would have duplicated the routing code. Polarity is orthogonal to routing — exactly the kind of thing a flag should express.
- **Test scene**: brick_facade_pipe_crack_v1 — 60×60×6mm slab with brick deformer (brickDepth=0.0009, brickDensity=28), chebyshev raised pipe (thickness=0.0018, depth=0.003, noiseWeight=0.4 for engineered straightness), euclidean carved crack (thickness=0.0007, depth=0.0025, noiseWeight=1.6 for organic weak-material drift). Self-validated via preview daemon: front view shows running-bond brick + diagonal pipe + smooth crack; side view shows pipe protruding (raise = real additive geometry, not a recolor); top view shows pipe breaking silhouette while crack stays flush; iso shows all three layers compositing cleanly with no visual interference.
- **Authoring use cases unlocked**:
  - **Pipes / conduits / cables** on building facades, sci-fi corridors, mechanical panels
  - **Welding beads / seams** on metal plates (chebyshev or manhattan, very fine thickness)
  - **Vines / ivy** on walls (tendril mode + raise — raised growth instead of carved trail)
  - **Ribs / piping** on chest armor, leather goods, tooled book covers (any path mode + raise)
  - **Branches** of a tree growing OUT from a base trunk (tree mode + raise) instead of carved tree-shaped grooves
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics + 3 path profiles + meander + taper + accentSlot + **raise polarity flag (orthogonal across all 5 path modes)**.
- **Architectural note**: this is a *cross-cutting* extension — adds a feature that multiplies across 5 existing modes, not adds a new sibling mode. The 5 modes × 2 polarities = 10 path-gen variants from a 1-flag change. Compares favorably to iter 26 (1 new option × 3 metrics = 3 variants for similar implementation cost).
- **Scope decision**: skipped T-junctions/branches (previously the iter 27 candidate). Branches still on the stack but raise-polarity unlocks more orthogonal variety per LoC — pipes-on-facades was a missing capability category, branches are an enhancement to an existing one. Iter 28 candidates: T-junctions (mechanical Y-fittings), reaction-diffusion (Gray-Scott).

## /loop iter 28: T-junction branches on A* paths
- **New `astarBranches?: number` field on `crackPathGen`** (astar mode only). Spawns N perpendicular sub-paths off the main spine. Each branch picks a random INTERIOR waypoint (endpoint branches look detached), computes local tangent via central difference, projects perpendicular by 30-60% of the main bbox diagonal at random side, then recursively runs A* from waypoint → projected end with `astarBranches: 0` to prevent fractal explosion. Capped at 8 branches.
- **Branches inherit polarity, metric, profile, noiseWeight from parent** via `{...opts}` spread. Override only `start/end/seed/astarBranches/thickness*0.6/depth*0.85`. So:
  - chebyshev + raise=true + branches → mechanical T-fittings on raised pipework
  - manhattan + branches → side-streets off avenues (right-angle preserved)
  - euclidean + branches → tributary cracks / forking weak-material lines (smoothed via Catmull-Rom — branch joins fuse naturally)
- **Why `astarBranches` not `branches`**: tree-mode already has `branches?: number` (per-node fork count). Disambiguating the field names avoids ambiguity in the schema. The `astar` prefix also reads as "applies only to astar mode" which is the actual constraint.
- **Test scene**: brick_facade_pipe_tjunctions_v1 — same brick facade + chebyshev raised pipe with `astarBranches: 3` + euclidean carved crack with `astarBranches: 2`. Self-validated via preview daemon: front view shows pipe spine + 3 perpendicular protruding T-stubs + crack with 2 organic tributary forks; side view confirms branch protrusions in 3D (raised inherits correctly); iso view shows pipe network and crack network composing on brick without visual conflict.
- **Architectural note**: this iter is the cleanest kind of "free orthogonal extension" — `branches × metric × polarity × profile = 3×2×3 = 18 visual variants` from a ~50 LoC change, on top of iter 27's already-orthogonal `metric × polarity` matrix. Cost-field reuse (sub-A* runs with same noise seed offset) means branches feel cohesive with the main path rather than randomly tacked on.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches + 3 path profiles + meander + taper + accentSlot.
- **Iter 29 candidates**:
  - **Pipe end caps**: when raise=true, emit small hemisphere prims at start/end so pipes terminating mid-surface read as finished (currently the rounded-box ends look slightly clipped). ~15 LoC.
  - **Reaction-diffusion (Gray-Scott)**: still on the stack. Major architectural spike — WGSL compute pass + storage texture sampler. Different category from analytical deformers. Estimated ~150-200 LoC.
  - **Branch angle control**: currently branches project at exactly perpendicular (90°). A `branchAngleDeg?: number` override (default 90, e.g., 60-75 for swept-back tributaries that read as drainage rather than perpendicular splits) would extend authoring range. ~10 LoC.

## /loop iter 29: T-junction fittings via 'joint' kind on pathCarves
- **New `kind?: 'segment' | 'joint'` field on pathCarves**. 'segment' (default) = roundedBox along from→to (existing behavior, all path-gen modes emit this). 'joint' = sphere at `from` of radius=thickness, ignores `to`. Emitted by `expandPathCarves` via early-branch on c.kind, so adding it required no refactor of the existing prim emission.
- **A* branch loop now emits a joint at each connection point** in addition to the perpendicular sub-path. Joint inherits raise polarity, so `raise=true` paths get raised T-fittings (pipework) and `raise=false` paths get carved sinkholes at fork points (cracks merging in a deeper pit). `blendRadius: c.raise ? 0.0015 : -0.0015` (tighter than segments' 0.002, so joints read as distinct bulbs rather than melting into the spine).
- **Critical sizing lesson**: joint radius MUST exceed pipe depth or the sphere stays buried inside the tube/trench union and contributes nothing visually. First attempt used `thickness * 1.35 = 0.0024` against `depth = 0.003` — sphere top below pipe top → invisible. Fixed to `Math.max(thickness * 2.5, depth * 2.0) = 0.006` for the brick-facade test, giving ~3mm protrusion above the pipe spine. The blunt heuristic: joint radius needs to be at least 2× the pipe depth for the bulge to read at typical authoring scales.
- **Validation methodology that paid off**: when the iter-28-spec re-render with the new code looked identical to iter 28, I wrote a STANDALONE test spec with manually-authored `kind: 'joint'` pathCarves at known XY positions on the bare facade (no pipe). That render showed three crisp hemispherical bumps — proved the emission path was correct, isolated the bug to joint sizing relative to surrounding geometry. Without that isolated test, "looks the same" could have meant "code never runs" or "code runs but gets clipped" or "blend radius too aggressive" — debugging via hypothesis-elimination instead of guessing.
- **Test scene**: brick_facade_pipe_tjunctions_joints_v1 — same brick facade with 3-branch chebyshev raised pipe (now with visibly-bulged T-fittings) + 2-branch euclidean carved crack (small pit-joints at the 2 fork points, polarity correctly inherited). Self-validated: front view shows pipe spine fattening at each connection point, side/iso views confirm 3D protrusion of joints.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches × **{segment, joint} carve kinds** + 3 path profiles + meander + taper + accentSlot.
- **Iter 30 candidates**:
  - **Reaction-diffusion (Gray-Scott)** — finally promote this. Two iters of small extensions on path-gen makes the next move a pivot to a new category. New WGSL compute architecture; coral, brain, zebra, leopard from F/k tuning.
  - **Joint shape variety**: currently sphere-only. A `jointShape?: 'sphere' | 'torus' | 'cube'` field would unlock ring fittings (torus around the spine — like a flange), cubic junctions (industrial valve boxes), etc. ~15 LoC + sphere-equivalent cases.
  - **Joint at endpoints (start/end of main path)**: currently only at branch connection points. End-of-pipe spheres would replace the rounded-box clipped-cap look with proper hemispherical caps. ~10 LoC. Cheaper than the iter-29-candidate "pipe end caps" because it reuses the joint emit path.

## /loop iter 30: endpoint caps on A* paths — pipe authoring story complete
- **New `endCaps?: boolean` field on `crackPathGen`** (astar mode). Default = `!!opts.raise` — raised pipes get endpoint hemisphere caps automatically (so they read as terminated rather than clipped); carved trenches don't (extra pits at endpoints look like accidents). Override explicitly to force on/off.
- **Implementation reuses iter 29's joint-emit path**. After main `emitCarvesFromPath`, push a `kind:'joint'` carve at `wp[0]` and `wp[wp.length-1]` with the same `Math.max(thickness*2.5, depth*2.0)` sizing. Total ~12 LoC including schema, normalizer, and gen logic. Extension cost is low because the joint primitive type was already wired through expandPathCarves last iter.
- **Test scene**: brick_facade_pipe_endcaps_v1 — same spec as iter 29 but renamed to flag the new render. Pipe now displays prominent hemispherical bulbs at both ends, plus the existing 3 T-junction joints. Side view confirms 3D protrusion of all 5 joints. Carved crack remains uncapped — confirms the polarity-driven default.
- **Architectural note**: this iter is the *closing brace* on the path-gen sub-thread that ran iters 26-30. Each iter added one orthogonal capability:
  - **iter 26**: A* metrics (3 variants — euclidean/manhattan/chebyshev)
  - **iter 27**: raise polarity (×2 → 6 variants, doubled the visual catalog)
  - **iter 28**: T-junction branches (×{0..8} → 54 variants, multiplied again)
  - **iter 29**: T-junction joint primitives (engineered fitting visual layer)
  - **iter 30**: endpoint caps (closes the silhouette of raised pipes)
- **The compounding worked**: 5 iters × ~30 LoC each = ~150 LoC total, but the resulting authoring matrix has tens of distinct visual outputs from a single spec field combinatorial. This is the mode I should aim for going forward — pick orthogonal extension axes, not parallel siblings.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches × {auto/forced} endcaps × {segment, joint} carve kinds + 3 path profiles + meander + taper + accentSlot.

## Iter 31 plan: Reaction-diffusion (Gray-Scott) — focused architectural spike
- **Pivot from path-gen polish to a new deformer category**. Path-gen has had 5 iters; per the 6-iter cap, time to move on. RD has been deferred at iters 28 and 29 — claiming this slot.
- **Architecture decision**: CPU-side Gray-Scott bake at spec-normalize time, upload field as a 2D texture, sample in the WGSL fragment deformer. This avoids needing a new compute pipeline + ping-pong storage texture infrastructure (which the modeler's WGSL block currently lacks — it only has scene/normal/depth tex bindings + uniform; no compute pass, no storage texture for read-write).
- **Why CPU bake is the right tradeoff**: RD only needs to run ONCE per spec (~1000-3000 iterations to settle into stable patterns). At 256² grid that's ~65k cells × 3000 iters = 200M ops. ~1 second on JS at modern speeds. Spec-normalize already runs all the path-gen logic on CPU; this is in keeping. GPU compute would be faster (10-100×) but adds bind-group machinery, double-buffer texture state, and dispatch ordering — too much one-iter scope.
- **Plan**:
  1. Add fields to ModelerPrim: `rdFeed?: number` (F), `rdKill?: number` (k), `rdIterations?: number` (default 2000), `rdGridRes?: number` (default 256), `rdDepth?: number` (displacement amplitude), `rdSeed?: number`.
  2. CPU implementation of Gray-Scott update on a Float32Array pair (U, V) double-buffered. Initial conditions: small seed of V perturbation in the center; rest pure U.
  3. After bake, take the V channel, upload as `rg32float` or `r32float` texture (one channel, 256² × 4 bytes = 256KB, fits well).
  4. Add new texture binding (binding=5, since 0-4 are taken) to the WGSL block.
  5. New deformer function in WGSL that samples by world-XY → uv (mod 1.0 for tiling).
  6. Wire into the per-prim deformer dispatcher.
  7. Test scene: 60×60×6mm slab with RD deformer at F=0.055, k=0.062 (coral preset).
- **Risk**: WGSL fragment-shader texture sampling is straightforward, but adding a new bind group entry mid-pipeline could surface plumbing details I haven't seen. If the spike runs over budget, fallback is a 1D field encoded directly into the prim params (8x8 grid in a vec4 array — much cruder, but no new bindings).
- **Calibration**: known F/k presets — coral (0.055, 0.062), brain (0.040, 0.060), zebra (0.020, 0.060), leopard (0.025, 0.060), spots (0.014, 0.054), chaos (0.026, 0.051). The pattern axis (F, k) is roughly orthogonal to "scale" — same F/k at different grid resolution gives larger/smaller features. Authors will pick from preset → adjust for taste.

## /loop iter 31: Reaction-diffusion (Gray-Scott) deformer — coral works
- **New `colorFunc=27` deformer** in raymarch_renderer.ts: samples a CPU-baked V-channel field via `@binding(5) var<storage, read> rdField: array<f32>`. Geometric pass adds `-v * rdDepth` to d (high V = raised peak). Color pass picks slot B for V > 0.3 (the established peak threshold). Pattern is emergent (analytical deformers can't make this).
- **CPU bake**: `bakeReactionDiffusion(F, k, iterations, seed)` runs Gray-Scott Euler integration on a 128² Float32Array pair (U, V). Toroidal Laplacian (5-point, wraps), random ~5% V-perturbation seed, normalised to [0,1]. Cached on (F, k, iters, seed) — re-renders without RD changes don't re-bake. ~50ms for 2000 iters.
- **Engine plumbing**: added `rdFieldBuffer` (128² × 4B = 64KB) at renderer construction, default-zero so binding stays valid when no RD prims exist; `setRDField(data: Float32Array)` public method; bind group entry at binding 5. Auto-derived bind group layout from WGSL declarations meant zero explicit layout-spec changes — the new `@binding(5)` line was the entire layout-side change.
- **Critical bug caught**: first attempt used `Du=1.0, Dv=0.5, dt=1.0` (informally remembered from Wikipedia). With those values, the explicit Euler integrator is unstable past iter ~20 — the Laplacian's ×4-neighbor swing exceeds the stability bound, U/V values blow past saturation into NaN. NaN flowed through writeBuffer onto the GPU, made `d = d - NaN * rdDepth` return NaN inside the SDF, and **the entire surface vanished — the render came back empty grid**. Fixed by switching to **Pearson's classical params: Du=0.16, Dv=0.08**. Stability lesson: never trust un-cited diffusion coefficients; the well-known stable presets exist for a reason.
- **Diagnostic methodology**: when the RD spec rendered empty grid, swapped to a known-good brick-only spec (no RD) — that worked, isolating the bug to the RD code path. Ruled out plumbing (binding, layout) by elimination. Then suspected NaN → reasoned about the diffusion stability bound → fixed → next render showed coral. ~2 spec swaps from "broken" to "fixed" without needing browser console access.
- **Test scene**: rd_coral_v2_fixed_du — 60×60×6mm slab with rdDepth=0.0015, rdDensity=14, F/k=0.055/0.062 (coral preset), 2000 iters, seed=7. Render shows ~6-8 coral spots scattered across the front face, each ~5-10mm wide, with characteristic intricate amoeba-boundary topology. Side view shows clear 3D protrusion (~1.5mm raised). Iso shows depth and pattern compositing cleanly.
- **One-field-per-scene constraint**: shared rdFieldBuffer means one F/k bake at a time. Each prim with rdDepth > 0 samples the same field at its own density/depth, but the F/k that defines the PATTERN is set by the FIRST RD prim found in spec.primitives. Acceptable for first cut; future iters could move to multi-field via array<array<f32, GRID²>, MAX_FIELDS> or per-prim baked atlases.
- **Library state**: 18 primary deformers (12 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24, 25, **27**) + 4 wear deformers + 6 path-gen modes + astar matrix + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - Periodic-organic: fishscale
  - Two-axis raised: weave
  - **Emergent: reaction-diffusion (Gray-Scott)** ← new family. First non-analytical deformer — pattern emerges from rule iteration, not from a closed-form expression.
- **Architectural milestone**: this iter is the first to add new GPU storage binding to the raymarch pipeline. The pattern is now established — future iters needing precomputed fields (e.g., voronoi-region tables, signed distance maps for arbitrary glyphs, custom palette atlases) can copy the rdFieldBuffer pattern: createBuffer at init, default-zero fill, setX() public method, bind group entry. Auto-derived layout means no explicit layout maintenance.
- **Iter 32 candidates**:
  - **Other RD presets validated** — brain (0.040, 0.060), zebra (0.020, 0.060), leopard (0.025, 0.060). Different F/k same architecture; just pick presets to confirm visual range. Cheap iter.
  - **RD on a path-gen carved surface** — apply RD to a prim that ALSO has a chebyshev pipe carved into it. Visual: coral wall with mechanical pipework. Tests deformer composition (path-gen pathCarves are separate prims, RD is on parent — should naturally compose).
  - **Per-prim independent RD fields**: extend rdFieldBuffer from `array<f32, 128²>` to `array<f32, 128² × MAX_RD_PRIMS>` and index by per-prim `rdFieldIdx`. Allows multiple RD-deformed prims in one scene with different F/k. ~30 LoC.
  - **RD wear overlay**: wire RD into the secondary wear-deformer slot (currently FBM-only modes 1-4). Coral-textured rust on a brick wall, brain-fold detail on a face. ~10 LoC + new wearFn ID.
