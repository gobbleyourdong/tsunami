# Dashboard Template

React 19 + TypeScript + Vite + recharts. For data dashboards and admin panels.

## Pre-built Components

Import from `./components`:
- `Layout` — sidebar navigation + header + main content area
- `Card` — container with title and border
- `StatCard` — big number display (label, value, change %)
- `DataTable` — sortable table with column definitions

## Build Loop

1. Write types in `src/types.ts`
2. Use `Layout` as the outer shell with `navItems`
3. Fill with `StatCard` for metrics, `Card` for sections, `DataTable` for lists
4. Add recharts components for charts (`LineChart`, `BarChart`, `PieChart`)
5. Wire in `src/App.tsx`

## Usage Examples

```tsx
import { Layout, StatCard, Card, DataTable } from "./components"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

<Layout title="Sales Dashboard" navItems={[
  { label: "Overview", id: "overview" },
  { label: "Orders", id: "orders" },
]}>
  <div className="grid grid-4 gap-4">
    <StatCard label="Revenue" value="$12.4K" change="+12%" />
    <StatCard label="Orders" value="342" change="+8%" />
  </div>
  <Card title="Revenue Over Time">
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <XAxis dataKey="month" /><YAxis />
        <Tooltip /><Line dataKey="revenue" stroke="#0ff" />
      </LineChart>
    </ResponsiveContainer>
  </Card>
</Layout>
```

## File Structure

```
src/
  App.tsx            ← Wire your dashboard here
  types.ts           ← Your data interfaces
  components/
    Layout.tsx        ← Sidebar + header (ready to use)
    Card.tsx          ← Content card (ready to use)
    StatCard.tsx      ← Metric display (ready to use)
    DataTable.tsx     ← Sortable table (ready to use)
    index.ts          ← Barrel exports
```
