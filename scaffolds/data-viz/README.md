# Data Visualization Template

React 19 + TypeScript + Vite + recharts + d3 + papaparse. For charts, graphs, and data exploration.

## Available Libraries

- `recharts` — React chart components (LineChart, BarChart, PieChart, AreaChart, ScatterChart)
- `d3` — low-level data visualization (scales, axes, shapes, transitions)
- `papaparse` — CSV parsing

## Build Loop

1. Write `src/App.tsx` FIRST with `import "./index.css"`
2. Import recharts components directly — they're installed
3. Use papaparse to load CSV data
4. For complex custom visualizations use d3 with useRef + useEffect

## recharts Examples

### Line chart
```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

const data = [{month:"Jan",value:40},{month:"Feb",value:55},{month:"Mar",value:70}]

<ResponsiveContainer width="100%" height={300}>
  <LineChart data={data}>
    <XAxis dataKey="month" /><YAxis /><Tooltip />
    <Line dataKey="value" stroke="#0ff" strokeWidth={2} />
  </LineChart>
</ResponsiveContainer>
```

### Bar chart
```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

<ResponsiveContainer width="100%" height={300}>
  <BarChart data={data}>
    <XAxis dataKey="name" /><YAxis /><Tooltip />
    <Bar dataKey="value" fill="#0ff" radius={[4,4,0,0]} />
  </BarChart>
</ResponsiveContainer>
```

### Area chart
```tsx
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

<ResponsiveContainer width="100%" height={300}>
  <AreaChart data={data}>
    <XAxis dataKey="month" /><YAxis /><Tooltip />
    <Area dataKey="value" stroke="#0ff" fill="#0ff22" />
  </AreaChart>
</ResponsiveContainer>
```

### Pie chart
```tsx
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts"

const COLORS = ["#0ff", "#f0f", "#ff0", "#0f0"]

<ResponsiveContainer width="100%" height={300}>
  <PieChart>
    <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100}>
      {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
    </Pie>
  </PieChart>
</ResponsiveContainer>
```

### Load CSV
```tsx
import Papa from "papaparse"

const [data, setData] = useState([])

function loadCSV(file: File) {
  Papa.parse(file, {
    header: true,
    complete: (result) => setData(result.data)
  })
}
```

## File Structure

```
src/
  App.tsx          ← Wire your visualizations here
  components/      ← Custom chart components
```
