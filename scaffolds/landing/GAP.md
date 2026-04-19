# GAP — landing

## Purpose
Single-page marketing / product-launch variant of react-app. Would host
hero headline, feature grid, CTA, waitlist form, social proof.

## Wire state
- **Not routed.** No plan_scaffold, no keyword match in planfile.py.
- `landing/` dir exists with the scaffold files; `index.html`,
  `main.tsx`, `package.json`, `node_modules/` all in place.
- Zero deliveries this session used it. react-app catches landing-
  style tasks via the fallback.

## Numeric gap
- Delivery count: **0**.
- Target: **≥3 vision-PASS deliveries** to prove the scaffold.
- Delta: no routing. Nothing selects this scaffold.

## Structural blockers (known)
- No `tsunami/plan_scaffolds/landing.md`.
- No keyword signal in `planfile.py::_DOMAIN_SIGNALS`.
- `tools/project_init.py::_pick_scaffold` has `"landing": "landing"` in
  the alias map but no detection logic that triggers it.

## Churn lever
1. Add `plan_scaffolds/landing.md` — 5 sections (Hero, Features, CTA,
   Waitlist, Footer).
2. Add keywords in `planfile.py::_DOMAIN_SIGNALS` BEFORE react-build
   fallback: `landing page / waitlist / product launch / coming soon /
   signup page`.
3. Extend `_pick_scaffold` in project_init.py to detect the same
   keywords and return `"landing"`.
4. Ship 3 landing tasks (SaaS waitlist, product launch, podcast).
5. Mark wire-state proven.

## Out of scope
- Duplicating react-app's 44 UI components — landing IS react-app
  with a smaller default App.tsx stub.
- Backend signup handling (that's `form-app` territory).

## Test suite (inference-free)
Same shape as react-app — fixture App.tsx that exercises a landing
template, `npm run build` validates. Parallel-safe. Serialize live
inference runs via `~/.tsunami/inference.lock`.

## Success signal
Landing plan routing fires on "SaaS waitlist page" prompt, scaffold
gets picked over react-app, delivery ships vision-PASS in ≤3 iters.
