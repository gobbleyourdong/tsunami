# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Layout](#layout)
- [ ] [Data](#data)
- [ ] [Charts](#charts)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
Admin/metrics console: persistent sidebar nav + top bar + content grid.
Mock data lives in `src/data.ts` as typed arrays — no backend. The job
is the visual story: KPIs at the top, charts and tables below, drill-in
dialogs on row click.

Compose in `src/App.tsx`. Sidebar + TopBar are always-visible chrome;
content swaps via local `useState<"overview"|"customers"|...>` (no router).

## Layout
- **Sidebar** — `src/components/Sidebar.tsx` — pure presentational; map
  over a `nav: { id, label, icon }[]` constant; highlight active.
  Use `Box bg="bg-1" padding={4} bordered` + `Button variant="ghost" fullWidth`.
- **TopBar** — `src/components/TopBar.tsx` — `Input leftIcon={<🔍/>} size="sm"`
  + `Tooltip + IconButton` notifications + `Dropdown` user menu (wrap `Avatar`).
- **KPI tiles** — `Card variant="filled" padding="md" hoverable` containing
  `AnimatedCounter` + `Badge variant="success|destructive" pill` for delta.
- **Status / activity** — `Progress size="sm" color` per row; `Timeline`
  for activity feed (drones reach for `{ year, event, body }` or `{ date, title, description }` shapes).
- **CmdK** — drop a `<CommandPalette>` at root with 4–8 commands.

Drone-natural prop coverage is locked into `__fixtures__/dashboard_patterns.tsx` —
read it for canonical shapes.

## Data
Pure TS arrays in `src/data.ts`. Shape every record:
```ts
export type KPI = { label: string; value: number; delta?: number; suffix?: string }
export type StatusRow = { label: string; pct: number; color: "success"|"warning"|"danger" }
```
No fetch — drones stub mock data. Time-series for charts uses
`{ x: string|number; y: number }[]` — recharts-friendly.

## Charts
Recharts API (drone reaches for these shapes — get them right or tsc fails):
```tsx
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
         Tooltip, Legend, ResponsiveContainer } from "recharts"

<ResponsiveContainer width="100%" height={240}>
  <LineChart data={series} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
    <XAxis dataKey="x" stroke="var(--text-muted)" fontSize={11} />
    <YAxis stroke="var(--text-muted)" fontSize={11} />
    <Tooltip contentStyle={{ background: "var(--bg-3)", borderRadius: 8 }} />
    <Legend />
    <Line type="monotone" dataKey="y" stroke="var(--accent)" strokeWidth={2} />
  </LineChart>
</ResponsiveContainer>
```
Add `recharts` via `dependencies` when calling `project_init`.

## Tests
`src/App.test.tsx`. One behavioral test per interaction:
- `Sidebar nav click → content swaps to that section`
- `KPI hover → border / hoverable visual change asserted via class`
- `Confirm-delete dialog → opens on button click, dismisses on Cancel`
- `Cmd-K shortcut → command palette opens, filters by query`

## Build
shell_exec cd {project_path} && npm run build

## Deliver
message_result with one-line description.
