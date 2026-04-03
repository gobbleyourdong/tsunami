# Dashboard Scaffold

Vite + React 19 + TypeScript + Recharts. Sidebar layout with deep surface hierarchy.

## Components (import from `./components/ComponentName`)

| Component | Usage |
|-----------|-------|
| **Layout** | `<Layout title="Dashboard" navItems={items} activeNav={page} onNav={setPage} headerRight={<button>New</button>}>` — Collapsible sidebar with section labels |
| **StatCard** | `<StatCard label="Revenue" value="$12.4K" change="+12%" icon="💰" trend="up" />` — Trend arrows, tabular nums |
| **DataTable** | `<DataTable columns={cols} rows={data} searchable onRowClick={...} />` — Sort, search, custom renderers |
| **ChartCard** | `<ChartCard title="Revenue" subtitle="Last 30 days" action={<Select .../>}>{chart}</ChartCard>` — Chart wrapper with header |
| **Modal** | `<Modal open={show} onClose={close} title="Edit" size="md">` — Escape close, blur, scale-in, sm/md/lg |
| **Toast** | `toast("Saved!", "success")` + `<ToastContainer />` — 4 types with icons, click dismiss |
| **Card** | `<Card title="Section">content</Card>` |
| **Badge** | `<Badge>New</Badge>` |
| **EmptyState** | `<EmptyState icon="📭" title="No data" description="..." action={{label:"Create",onClick:...}} />` |

## Dashboard CSS Classes
- `.dashboard-layout` — full-height flex (sidebar + main)
- `.sidebar`, `.sidebar.collapsed`, `.nav-item.active` — collapsible nav with accent highlight
- `.nav-section-label` — uppercase section dividers in sidebar
- `.stats-grid` — auto-fit grid for stat cards
- `.stat-card`, `.stat-value`, `.stat-label`, `.stat-change.up/.down` — stat display
- `.chart-container`, `.chart-title` — styled chart wrapper
- `.badge.positive/.negative` — green/red badges for changes
- `.status-dot.online/.offline/.warning` — status indicators
- `.skeleton` — shimmer loading state
- All base classes from react-app (.card, .card.glass, .flex, .grid, etc.)

## Charts (recharts)
```tsx
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
         AreaChart, Area, XAxis, YAxis, CartesianGrid,
         Tooltip, ResponsiveContainer, Legend } from 'recharts'
```
Recharts dark theme overrides are built into the CSS — tooltips, grid lines, and text automatically match.

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Use CSS classes — avoid inline styles for colors, spacing, or layout
- Use recharts for all data visualization
- `App.tsx` is YOUR file — compose from the components above
