# Dashboard Scaffold

Vite + React 19 + TypeScript + Recharts. Dark theme with sidebar layout.

## Quick Start
Write your dashboard in `src/App.tsx`. Components are ready to import.

## Available Components (import from `./components`)

### Layout
`<Layout title="My Dashboard" navItems={[{label:"Home",id:"home",icon:"🏠"}]} onNav={setPage}>`
- Collapsible sidebar with navigation
- Header with title
- Main content area

### StatCard
`<StatCard label="Revenue" value="$12.4K" change="+12%" icon="💰" />`
- Big number display with optional change indicator and icon

### DataTable
`<DataTable columns={cols} rows={data} searchable onRowClick={row => ...} />`
- Sortable columns (click header to sort)
- Search filter
- Custom cell renderers via `render` prop on columns

### Card
`<Card title="Section">content</Card>`

### Charts (recharts)
```tsx
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
         XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
```

## Dashboard CSS Classes
- `.dashboard-layout` — full-height flex container
- `.stats-grid` — auto-fit grid for stat cards
- `.chart-container` + `.chart-title` — styled chart wrapper
- All base utilities from react-app (.flex, .grid, .card, etc.)

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- `App.tsx` is YOUR file
- Use recharts for all data visualization
