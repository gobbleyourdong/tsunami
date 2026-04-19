# GAP — react-app

## Purpose
General-purpose React 19 + Vite + Tailwind SPA. Default scaffold for
anything that looks like a website / timer / dashboard / gallery /
single-page app. 44 UI components in `src/components/ui/`.

## Wire state
- Plan scaffold: `tsunami/plan_scaffolds/react-build.md`
- Routing: fallback catch-all in `planfile.py::_DOMAIN_SIGNALS` —
  `build / create / make / app / dashboard / website / tracker / game /
  viewer / editor / timer`.
- Proven: pomodoro replica, car website, art gallery, space invaders
  combo all vision-passed from this scaffold.

## Numeric gap
- Iter-1 build-pass rate on compositional 4+ component sites: **~40%** (2/5).
- Target: **90%**.
- Delta: prop-type alignment across imported scaffold-UI components.
  Drone writes `<Text size="xs">` despite scaffold.yaml listing only
  sizes "sm".."3xl"; writes `<GradientText as="h1" size="5xl">` where
  those props don't exist; writes `<Button variant="primary" size="md">`
  with legal props mixed with illegal. TS2322 cascades across multiple
  components in one write.

## Structural blockers (known)
- `Text.tsx` and `GradientText.tsx` widened in 1f5c0c1 to accept
  drone-natural props (size/muted/weight/as). 42 other UI components
  likely have the same asymmetry.
- scaffold.yaml encodes correct props but drone's habits override.

## Churn lever
1. Run a dozen diverse react-app tasks (landing, pricing page, blog,
  admin, portfolio, docs site).
2. For every TS2322 / TS2339 on a UI-component prop, widen the component
  to accept the drone's natural prop shape (tailwind passthrough pattern).
  Do NOT tighten the drone prompt to match scaffold — meet the drone
  where it is.
3. Re-measure iter-1 pass rate. Target 90%. Report which component had
  the most drone-prop misses.

## Out of scope
- New UI components (44 is enough).
- Prompt-engineering "please use className" — that was tried, failed.
- Removing scaffold.yaml — it's useful as a reference even if drones
  ignore it.

## Test suite (inference-free — for parallel instances)
The shared Qwen3.6 server on :8090/:8095 is the bottleneck. Prove
scaffold changes WITHOUT hitting it. Fixtures live at
`scaffolds/react-app/__fixtures__/` (create if missing).

Test flow per fix:
1. Write a minimal fixture App.tsx that exercises the prop shape a
   drone would naturally emit (e.g. `<Text size="xs" muted>`).
2. `cd scaffolds/react-app && npm install` (one-time per instance).
3. Run: `npm run build` — this is tsc + vite + vitest. Either passes
   (structural fix landed) or reports a concrete TS error to target.
4. Iterate the component, not the fixture.
5. When all fixtures pass, one integration run against the live
   inference server to confirm end-to-end.

Parallelism rule: N instances can run steps 1-4 concurrently (all
local, no inference). Only one instance hits the inference server at
a time — serialize step 5 via a file lock at
`~/.tsunami/inference.lock` (advisory; check + sleep 30s if present).

## Success signal
Three consecutive diverse tasks ship vision-PASS at ≤3 iterations
each, no human-visible prop friction.
