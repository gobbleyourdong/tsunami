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
  data: ChartDatum[]
  height?: number | string
  color?: string
  palette?: string[]
  showGrid?: boolean
  showLegend?: boolean
  showTooltip?: boolean
  xKey?: string
  yKey?: string
  label?: string
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
  type = "line",
  data,
  height = 280,
  color = "var(--accent)",
  palette = DEFAULT_PALETTE,
  showGrid = true,
  showLegend = false,
  showTooltip = true,
  xKey = "x",
  yKey = "y",
  label,
  className = "",
  style,
}: ChartProps) {
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
        {type === "line" ? (
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            {showGrid && <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />}
            <XAxis dataKey={xKey} stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            <YAxis stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            {showTooltip && <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: gridColor }} />}
            {showLegend && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Line
              type="monotone"
              dataKey={yKey}
              name={label ?? yKey}
              stroke={stroke}
              strokeWidth={2}
              dot={{ fill: stroke, r: 3 }}
              activeDot={{ r: 5 }}
              isAnimationActive
            />
          </LineChart>
        ) : type === "bar" ? (
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            {showGrid && <CartesianGrid stroke={gridColor} strokeDasharray="3 3" vertical={false} />}
            <XAxis dataKey={xKey} stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            <YAxis stroke={axisColor} fontSize={11} tickLine={false} axisLine={{ stroke: gridColor }} />
            {showTooltip && <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.04)" }} />}
            {showLegend && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Bar dataKey={yKey} name={label ?? yKey} fill={stroke} radius={[6, 6, 0, 0]} />
          </BarChart>
        ) : (
          <PieChart>
            {showTooltip && <Tooltip contentStyle={tooltipStyle} />}
            {showLegend && <Legend wrapperStyle={{ fontSize: 12, color: axisColor }} />}
            <Pie
              data={data}
              dataKey={yKey}
              nameKey={xKey}
              cx="50%"
              cy="50%"
              outerRadius="80%"
              innerRadius="45%"
              paddingAngle={2}
              stroke={resolveCssVar("var(--bg-0)")}
            >
              {data.map((_, i) => (
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
