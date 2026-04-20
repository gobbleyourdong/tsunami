# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Charts](#charts)
- [ ] [Filters](#filters)
- [ ] [Data](#data)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
Chart-heavy analytics page. Deeper viz than `dashboard` — the user came
to EXPLORE data, not glance at a console. Filter bar at top, chart
grid below, legend / display toggles in a side rail. No persistent nav.

Compose in `src/App.tsx`. State lives in `useState`/`useReducer`; mock
data in `src/data.ts`. Ship the chart + filter UX in one page.

## Charts
Pick the right chart per question (drone defaults badly; be deliberate):
| Question | Chart |
|---|---|
| trend over time | Line / Area |
| compare categories | Bar (vertical for ≤8, horizontal for more) |
| distribution | Histogram (Bar with tight bins) |
| relationship | Scatter |
| composition / share | Stacked Bar or Pie (≤5 slices) |
| density / matrix | Heatmap (custom SVG `<rect>` grid) |

Recharts ships these natively: `LineChart`, `AreaChart`, `BarChart`,
`ScatterChart`, `PieChart`, `RadarChart`. Wrap every chart in
`<ResponsiveContainer width="100%" height={...}>`. Use `<CartesianGrid>`
with `strokeDasharray="3 3"` and CSS-var stroke colors.

Drone-natural prop shapes for filter / legend / toggle UI are locked into
`__fixtures__/dataviz_patterns.tsx`.

Add `recharts` to `dependencies` at `project_init`.

## Filters
Filter bar in `src/components/FilterBar.tsx`:
- `Select label="Period"` — 1d / 7d / 30d / ytd / all.
- `Select label="Granularity"` — hour / day / week / month.
- `Input leftIcon={<🔍/>} label="Search series"` — substring filter.
- `Button variant="primary"` Apply, `Button variant="outline"` Reset.

Color legend: `ColorPicker` per series with `swatches` matching the
DEFAULT_PALETTE. Toggle row: `Switch` for grid / tooltip / log scale.

## Data
Static JSON in `src/data.ts` keyed by series:
```ts
export type Point = { x: string | number; y: number }
export const series: Record<string, Point[]> = {
  cpu: [...], mem: [...], disk: [...],
}
```
Filter logic in a `useMemo` over `series + active filters`. No fetch.

## Tests
- `Filter change → chart data subset assertion (count, first / last x)`
- `Series toggle off → its color row removed from Legend`
- `No data state → Alert variant="info" title="No data" rendered`
- `Color picker change → swatch background updates`

## Build
shell_exec cd {project_path} && npm run build

## Deliver
message_result with one-line description.
