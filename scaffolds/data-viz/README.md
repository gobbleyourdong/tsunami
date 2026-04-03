# Data Viz Scaffold

Vite + React 19 + Recharts + D3 + PapaParse. Dark theme with chart styling.

## Components (import from `./components`)

### ChartCard
`<ChartCard title="Revenue" subtitle="Last 30 days" height={300}>{chart}</ChartCard>`
- Styled container with title bar for any chart

### CsvLoader
`<CsvLoader onData={(rows, columns) => setData(rows)} />`
- Drag-and-drop CSV upload, parses with PapaParse

### StatRow
`<StatRow stats={[{label:"Users", value:"12.4K", change:"+12%"}]} />`
- Row of stat cards with change indicators

## Recharts (import from `recharts`)
```tsx
import { LineChart, Line, BarChart, Bar, AreaChart, Area,
         PieChart, Pie, Cell, ScatterChart, Scatter,
         XAxis, YAxis, CartesianGrid, Tooltip, Legend,
         ResponsiveContainer } from 'recharts'

// Always wrap in ResponsiveContainer:
<ResponsiveContainer width="100%" height="100%">
  <LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="name" />
    <YAxis />
    <Tooltip />
    <Line type="monotone" dataKey="value" stroke="#4a9eff" />
  </LineChart>
</ResponsiveContainer>
```

## D3 (import from `d3`)
```tsx
import * as d3 from 'd3'
// Use for custom SVG visualizations, scales, transitions
```

## CSS Classes
- `.chart-card`, `.chart-header`, `.chart-body` — chart containers
- `.chart-grid-2`, `.chart-grid-3`, `.chart-grid-1-2`, `.chart-grid-2-1` — chart layouts
- `.stat-row`, `.stat-item`, `.stat-value` — summary stats
- `.csv-dropzone` — file upload area
- Recharts dark theme applied globally (grid, text, tooltip)

## Rules
- Always use `<ResponsiveContainer>` around recharts
- Use ChartCard to wrap charts for consistent styling
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
