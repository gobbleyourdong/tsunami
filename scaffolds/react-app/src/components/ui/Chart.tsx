import {
  LineChart, Line,
  BarChart, Bar,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts"

type ChartType = "line" | "bar" | "pie"

interface ChartDatum {
  x: string | number
  y: number
  [k: string]: any
}

interface ChartProps {
  type?: ChartType
  kind?: ChartType  // alias drones reach for
  data?: ChartDatum[]
  series?: ChartDatum[]  // alias drones reach for
  height?: number | string
  color?: string
  palette?: string[]
  showGrid?: boolean
  showLegend?: boolean
  showTooltip?: boolean
  legend?: boolean       // alias for showLegend
  grid?: boolean         // alias for showGrid
  animated?: boolean     // accepted for parity, recharts animates by default
  xKey?: string
  yKey?: string
  label?: string
  title?: string
  className?: string
  style?: React.CSSProperties
}

const DEFAULT_PALETTE = [
  "var(--accent)",
  "var(--success)",
  "var(--warning)",
  "var(--danger)",
  "var(--info)",
  "#b070f0",
]

function resolveCssVar(v: string): string {
  if (typeof window === "undefined") return v
  if (!v.startsWith("var(")) return v
  const name = v.slice(4, -1).trim()
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || v
}

export function Chart({
  type,
  kind,
  data,
  series,
  height = 280,
  color = "var(--accent)",
  palette = DEFAULT_PALETTE,
  showGrid,
  grid,
  showLegend,
  legend,
  showTooltip = true,
  animated,
  xKey = "x",
  yKey = "y",
  label,
  title,
  className = "",
  style,
}: ChartProps) {
  void animated
  const t = (type ?? kind ?? "line") as ChartType
  const rows = (data ?? series ?? []) as ChartDatum[]
  const showG = showGrid ?? grid ?? true
  const showL = showLegend ?? legend ?? false
  const seriesLabel = label ?? title ?? yKey
  const stroke = resolveCssVar(color)
  const axisColor = resolveCssVar("var(--text-muted)")
  const gridColor = resolveCssVar("var(--border)")
  const tooltipBg = resolveCssVar("var(--bg-3)")
  const resolvedPalette = palette.map(resolveCssVar)

  const tooltipStyle = {
    background: tooltipBg,
    border: `1px solid ${gridColor}`,
    borderRadius: 8,
    color: resolveCssVar("var(--text)"),
    fontSize: 12,
  }

  return (
    <div className={className} style={{ width: "100%", height, ...style }}>
      <ResponsiveContainer width="100%" height="100%">
        {t === "line" ? (
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            {showG && <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />}
            <XAxis dataKey={xKey} stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            <YAxis stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            {showTooltip && <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: gridColor }} />}
            {showL && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Line
              type="monotone"
              dataKey={yKey}
              name={seriesLabel}
              stroke={stroke}
              strokeWidth={2}
              dot={{ fill: stroke, r: 3 }}
              activeDot={{ r: 5 }}
              isAnimationActive
            />
          </LineChart>
        ) : t === "bar" ? (
          <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            {showG && <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />}
            <XAxis dataKey={xKey} stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            <YAxis stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            {showTooltip && <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />}
            {showL && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Bar dataKey={yKey} name={seriesLabel} fill={stroke} radius={[6, 6, 0, 0]} />
          </BarChart>
        ) : (
          <PieChart>
            {showTooltip && <Tooltip contentStyle={tooltipStyle} />}
            {showL && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Pie
              data={rows}
              dataKey={yKey}
              nameKey={xKey}
              cx="50%"
              cy="50%"
              outerRadius="80%"
              innerRadius="45%"
              paddingAngle={2}
              stroke={resolveCssVar("var(--bg-0)")}
            >
              {rows.map((_, i) => (
                <Cell key={i} fill={resolvedPalette[i % resolvedPalette.length]} />
              ))}
            </Pie>
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

export default Chart
