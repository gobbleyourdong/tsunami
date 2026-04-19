# GAP — data-viz

## Purpose
Chart-heavy analytics page. Deeper viz than `dashboard` — specifically
data exploration (pivot, filter, drill, scatter, heatmap). Recharts
plus custom SVG.

## Wire state
- **Not routed.** Scaffold dir exists; no plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥3 vision-PASS deliveries**.
- Delta: same shape as dashboard — routing + plan + chart-API hints.

## Structural blockers (known)
- Chart axis conventions (linear/log/time), legend placement, tooltip
  shape — all recharts specifics drones routinely get wrong.
- No plan_scaffold.

## Churn lever
1. Add `plan_scaffolds/data-viz.md` with explicit chart-type catalog
   (Line, Area, Scatter, Bar, Heatmap, Radar, Sankey).
2. Route on `data exploration / visualize / chart / plot / graph /
   analytics`.
3. Inline chart prop hints (data array shape, `<ResponsiveContainer>`,
   `Tooltip contentStyle`).
4. Ship: sales heatmap, sensor time-series, scatter clusters.

## Out of scope
- Server-side data (static JSON fixtures are fine).
- WebGL viz (stay in SVG/Canvas2D land).

## Test suite (inference-free)
Fixtures at `scaffolds/data-viz/__fixtures__/` exercise each chart
type. `npm run build` validates. Parallel-safe.

## Success signal
Three distinct viz specs render with correct chart choice and axis
labels, ≤4 iterations each.
