# GAP — dashboard

## Purpose
Admin / metrics / analytics dashboard variant. Recharts + grid layout
+ sidebar nav. Target shape: SaaS admin, ops console, analytics panel.

## Wire state
- **Not routed.** Has `_pick_scaffold` alias `"dashboard": "dashboard"`
  but no detection logic fires it.
- Zero deliveries. react-app catches dashboard-style tasks instead.

## Numeric gap
- Delivery count: **0**.
- Target: **≥3 vision-PASS deliveries**.
- Delta: routing + a plan_scaffold + recharts integration guidance.

## Structural blockers (known)
- No `tsunami/plan_scaffolds/dashboard.md`.
- Keyword "dashboard" in react-build plan catches it first.
- Recharts API is specific (data shape, axis config, ResponsiveContainer)
  — drone will need a hint block similar to the `@engine` hints.

## Churn lever
1. Add `plan_scaffolds/dashboard.md` — sections: Metrics, Layout,
   Charts, Tables, Nav.
2. Add keyword routing before react-build catch-all: `admin dashboard /
   metrics dashboard / analytics panel / ops console`.
3. Inline recharts API signatures in the prompt when scaffold is
   dashboard (LineChart, BarChart, AreaChart with ResponsiveContainer
   wrapper).
4. Ship a SaaS admin, a monitoring board, a finance dashboard.

## Out of scope
- Real data wiring (use mock data; visuals are the delivery).
- D3.js (stick with recharts — it's in the scaffold deps).

## Test suite (inference-free)
Fixtures at `scaffolds/dashboard/__fixtures__/` with example recharts
usages. `npm run build` validates. Parallel-safe.

## Success signal
Three distinct dashboard specs ship with charts rendering and no
recharts API errors, ≤4 iterations each.
