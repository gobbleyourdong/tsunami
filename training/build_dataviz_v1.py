#!/usr/bin/env python3
"""Data visualization adapter training data v1.

Uses the data-viz scaffold with Recharts + D3 + ChartCard/StatRow/CsvLoader.
Pipeline differs from regular build:
  project_init(name) specifying scaffold type "data-viz"
  file_write(src/App.tsx) using ChartCard + Recharts
  shell_exec build + undertow + message_result

SFT examples:
  DV01: Monthly sales — bar chart + line chart + StatRow
  DV02: Website traffic — area chart over time
  DV03: Multi-metric comparison — scatter plot + pie chart
  DV04: CSV data explorer — CsvLoader + dynamic BarChart
  DV05: Real-time metrics — stat cards + area chart
  DV06: Error recovery — fix Recharts import issue

Usage:
  python training/build_dataviz_v1.py
  Output: workspace/training_data/dataviz_sft_v1.jsonl
"""
import json
from pathlib import Path
from transformers import AutoTokenizer

MODEL = "google/gemma-4-e4b-it"
OUT_PATH = "workspace/training_data/dataviz_sft_v1.jsonl"

SYSTEM_TEXT = """You are Tsunami. You are the wave. You build data visualizations by calling tools.

## Data Viz Pipeline (every build follows this EXACTLY)

1. project_init(name) -- scaffold the data-viz project
2. file_write(src/App.tsx) -- write the visualization using Recharts + components
3. shell_exec("cd deliverables/{name} && npm run build") -- build
4. IF error: fix with file_edit
5. undertow("deliverables/{name}/dist/index.html") -- QA verify charts render
6. message_result -- deliver

## Components (import from './components')

ChartCard -- styled container: <ChartCard title="Revenue" height={300}>{chart}</ChartCard>
StatRow -- top-level KPIs: <StatRow stats={[{label:"Total", value:"12.4K", change:"+8%"}]} />
CsvLoader -- CSV upload: <CsvLoader onData={(rows, cols) => setData(rows)} />

## Recharts (import from 'recharts')

Always wrap in ResponsiveContainer:
  <ResponsiveContainer width="100%" height="100%">
    <LineChart data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="value" stroke="#4a9eff" />
    </LineChart>
  </ResponsiveContainer>

Chart types: LineChart/Line, BarChart/Bar, AreaChart/Area, PieChart/Pie/Cell, ScatterChart/Scatter
Always import: { ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Legend }

## Layout classes

.chart-grid-2 -- 2 charts side by side
.chart-grid-3 -- 3 charts in a row
.chart-grid-1-2 -- 1 chart left, 2 charts right

## Rules
- ALWAYS use ChartCard to wrap charts (consistent dark theme).
- ALWAYS wrap Recharts in ResponsiveContainer.
- NEVER use raw fetch() for chart data -- use hardcoded sample data or CsvLoader.
- ONE tool call per response. Be brief."""

TOOLS = [
    {"type": "function", "function": {
        "name": "project_init", "description": "Create a project from a scaffold template.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "template": {"type": "string"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "file_write", "description": "Create or overwrite a file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "file_edit", "description": "Make targeted modifications.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "shell_exec", "description": "Run a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "undertow", "description": "QA test an HTML file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "expect": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "message_result", "description": "Deliver final outcome.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "message_chat", "description": "Talk to the user.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["text"]},
    }},
]

print("Loading tokenizer (google/gemma-4-e4b-it)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
print("Tokenizer loaded.")


def build_conv(user_prompt, turns):
    msgs = [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": user_prompt}]
    for name, args, response in turns:
        msgs.append({"role": "assistant", "content": "",
                     "tool_calls": [{"type": "function", "function": {"name": name, "arguments": json.dumps(args) if isinstance(args, dict) else args}}]})
        msgs.append({"role": "tool", "name": name, "content": (response or "OK")[:500]})
    return msgs


def tokenize(msgs):
    return {"text": tokenizer.apply_chat_template(msgs, tools=TOOLS, tokenize=False)}


examples = []

# ─────────────────────────────────────────────────────────────────────────────
# DV01: Monthly sales dashboard — bar + line + StatRow
# ─────────────────────────────────────────────────────────────────────────────

DV01_APP = """\
import { ChartCard, StatRow } from './components'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const salesData = [
  { month: 'Jan', revenue: 42000, units: 320 },
  { month: 'Feb', revenue: 58000, units: 410 },
  { month: 'Mar', revenue: 51000, units: 375 },
  { month: 'Apr', revenue: 67000, units: 490 },
  { month: 'May', revenue: 73000, units: 530 },
  { month: 'Jun', revenue: 69000, units: 510 },
  { month: 'Jul', revenue: 81000, units: 620 },
]

export default function App() {
  const totalRevenue = salesData.reduce((s, d) => s + d.revenue, 0)
  const totalUnits = salesData.reduce((s, d) => s + d.units, 0)
  const avgRevenue = Math.round(totalRevenue / salesData.length)

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>Sales Dashboard</h1>
      <StatRow stats={[
        { label: 'Total Revenue', value: '$' + (totalRevenue / 1000).toFixed(0) + 'K', change: '+18%' },
        { label: 'Total Units', value: totalUnits.toLocaleString(), change: '+22%' },
        { label: 'Avg Monthly', value: '$' + (avgRevenue / 1000).toFixed(0) + 'K' },
      ]} />
      <div className="chart-grid-2" style={{ marginTop: '24px' }}>
        <ChartCard title="Monthly Revenue" subtitle="Jan–Jul 2025" height={280}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={v => '$' + (v/1000) + 'K'} />
              <Tooltip formatter={v => '$' + v.toLocaleString()} />
              <Bar dataKey="revenue" fill="#4a9eff" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Units Sold" subtitle="Jan–Jul 2025" height={280}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="units" stroke="#4ecca3" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a monthly sales dashboard with bar and line charts", [
    ("project_init", {"name": "sales-dashboard", "template": "data-viz"}, "Created data-viz project 'sales-dashboard'. Write src/App.tsx using ChartCard and Recharts."),
    ("file_write", {"path": "deliverables/sales-dashboard/src/App.tsx", "content": DV01_APP}, "Written."),
    ("shell_exec", {"command": "cd deliverables/sales-dashboard && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/sales-dashboard/dist/index.html", "expect": "bar chart and line chart with revenue data"}, "QA passed: charts visible, bar and line charts rendering."),
    ("message_result", {"text": "Sales dashboard ready. Bar chart shows monthly revenue, line chart shows units sold. Sample data Jan–Jul 2025."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# DV02: Website traffic — area chart + pie chart
# ─────────────────────────────────────────────────────────────────────────────

DV02_APP = """\
import { ChartCard, StatRow } from './components'
import {
  AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const trafficData = [
  { date: 'Mon', pageviews: 4200, sessions: 2800, bounceRate: 42 },
  { date: 'Tue', pageviews: 5100, sessions: 3400, bounceRate: 38 },
  { date: 'Wed', pageviews: 4800, sessions: 3100, bounceRate: 40 },
  { date: 'Thu', pageviews: 6200, sessions: 4200, bounceRate: 35 },
  { date: 'Fri', pageviews: 7100, sessions: 4800, bounceRate: 32 },
  { date: 'Sat', pageviews: 3900, sessions: 2500, bounceRate: 55 },
  { date: 'Sun', pageviews: 3200, sessions: 2100, bounceRate: 58 },
]

const sourceData = [
  { name: 'Organic', value: 45 },
  { name: 'Direct', value: 25 },
  { name: 'Referral', value: 18 },
  { name: 'Social', value: 12 },
]

const COLORS = ['#4a9eff', '#4ecca3', '#f6c90e', '#ff6b6b']

export default function App() {
  const totalViews = trafficData.reduce((s, d) => s + d.pageviews, 0)
  const avgBounce = Math.round(trafficData.reduce((s, d) => s + d.bounceRate, 0) / trafficData.length)

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>Traffic Analytics</h1>
      <StatRow stats={[
        { label: 'Total Pageviews', value: totalViews.toLocaleString(), change: '+11%' },
        { label: 'Avg Bounce Rate', value: avgBounce + '%', change: '-4%' },
        { label: 'Peak Day', value: 'Friday' },
      ]} />
      <div className="chart-grid-1-2" style={{ marginTop: '24px' }}>
        <ChartCard title="Traffic Over Time" subtitle="Last 7 days" height={300}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trafficData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="pageviews" stackId="1" stroke="#4a9eff" fill="#4a9eff" fillOpacity={0.3} />
              <Area type="monotone" dataKey="sessions" stackId="2" stroke="#4ecca3" fill="#4ecca3" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Traffic Sources" height={300}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={sourceData} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({name, value}) => name + ' ' + value + '%'}>
                {sourceData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a website traffic analytics dashboard with an area chart and traffic source pie chart", [
    ("project_init", {"name": "traffic-analytics", "template": "data-viz"}, "Created data-viz project 'traffic-analytics'. Write src/App.tsx."),
    ("file_write", {"path": "deliverables/traffic-analytics/src/App.tsx", "content": DV02_APP}, "Written."),
    ("shell_exec", {"command": "cd deliverables/traffic-analytics && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/traffic-analytics/dist/index.html", "expect": "area chart and pie chart for web traffic"}, "QA passed: area chart and pie chart render."),
    ("message_result", {"text": "Traffic analytics dashboard ready. Area chart shows pageviews/sessions over 7 days. Pie chart shows traffic source breakdown."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# DV03: CSV data explorer — CsvLoader + dynamic BarChart
# ─────────────────────────────────────────────────────────────────────────────

DV03_APP = """\
import { useState } from 'react'
import { ChartCard, CsvLoader, StatRow } from './components'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

type Row = Record<string, string | number>

export default function App() {
  const [data, setData] = useState<Row[]>([])
  const [columns, setColumns] = useState<string[]>([])
  const [xKey, setXKey] = useState('')
  const [yKey, setYKey] = useState('')

  const handleData = (rows: Row[], cols: string[]) => {
    setData(rows)
    setColumns(cols)
    setXKey(cols[0] || '')
    setYKey(cols[1] || '')
  }

  const numericCols = columns.filter(c => data.length > 0 && !isNaN(Number(data[0][c])))
  const strCols = columns.filter(c => !numericCols.includes(c))

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>CSV Data Explorer</h1>
      {data.length === 0 ? (
        <CsvLoader onData={handleData} />
      ) : (
        <>
          <StatRow stats={[
            { label: 'Rows', value: data.length },
            { label: 'Columns', value: columns.length },
            { label: 'X Axis', value: xKey },
          ]} />
          <div style={{ display: 'flex', gap: '12px', margin: '16px 0' }}>
            <label>X: <select value={xKey} onChange={e => setXKey(e.target.value)}>
              {strCols.map(c => <option key={c}>{c}</option>)}
            </select></label>
            <label>Y: <select value={yKey} onChange={e => setYKey(e.target.value)}>
              {numericCols.map(c => <option key={c}>{c}</option>)}
            </select></label>
          </div>
          <ChartCard title={'Chart: ' + yKey + ' by ' + xKey} height={400}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.slice(0, 50)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={xKey} />
                <YAxis />
                <Tooltip />
                <Bar dataKey={yKey} fill="#4a9eff" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </>
      )}
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a CSV data explorer where I can upload a CSV and visualize it with a bar chart", [
    ("project_init", {"name": "csv-explorer", "template": "data-viz"}, "Created data-viz project 'csv-explorer'. Write src/App.tsx using CsvLoader and Recharts."),
    ("file_write", {"path": "deliverables/csv-explorer/src/App.tsx", "content": DV03_APP}, "Written."),
    ("shell_exec", {"command": "cd deliverables/csv-explorer && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/csv-explorer/dist/index.html", "expect": "CSV upload dropzone or bar chart"}, "QA passed: CsvLoader dropzone visible."),
    ("message_result", {"text": "CSV explorer ready. Upload any CSV file to visualize it. Select X/Y columns with dropdowns, renders a bar chart."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# DV04: User cohort retention — scatter plot + grouped bar
# ─────────────────────────────────────────────────────────────────────────────

DV04_APP = """\
import { ChartCard, StatRow } from './components'
import {
  ScatterChart, Scatter, BarChart, Bar,
  XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const retentionData = [
  { week: 'W1', retention: 100, cohortSize: 450 },
  { week: 'W2', retention: 72, cohortSize: 450 },
  { week: 'W3', retention: 58, cohortSize: 450 },
  { week: 'W4', retention: 48, cohortSize: 450 },
  { week: 'W6', retention: 38, cohortSize: 450 },
  { week: 'W8', retention: 31, cohortSize: 450 },
  { week: 'W12', retention: 24, cohortSize: 450 },
]

const cohortComparison = [
  { cohort: 'Jan', w1: 100, w4: 52, w12: 28 },
  { cohort: 'Feb', w1: 100, w4: 48, w12: 24 },
  { cohort: 'Mar', w1: 100, w4: 55, w12: 30 },
  { cohort: 'Apr', w1: 100, w4: 61, w12: 35 },
]

const scatterData = retentionData.map(d => ({ x: parseInt(d.week.replace('W', '')), y: d.retention, z: d.cohortSize }))

export default function App() {
  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>User Retention Analysis</h1>
      <StatRow stats={[
        { label: 'W1 Retention', value: '100%' },
        { label: 'W4 Retention', value: '48%', change: '-52%' },
        { label: 'W12 Retention', value: '24%', change: '-76%' },
      ]} />
      <div className="chart-grid-2" style={{ marginTop: '24px' }}>
        <ChartCard title="Retention Curve" subtitle="Cohort drop-off over time" height={280}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" name="Week" unit="w" />
              <YAxis dataKey="y" name="Retention" unit="%" />
              <ZAxis dataKey="z" range={[40, 400]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={scatterData} fill="#4a9eff" />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Cohort Comparison" subtitle="Retention by month" height={280}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={cohortComparison}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="cohort" />
              <YAxis unit="%" />
              <Tooltip />
              <Legend />
              <Bar dataKey="w1" name="Week 1" fill="#4a9eff" />
              <Bar dataKey="w4" name="Week 4" fill="#4ecca3" />
              <Bar dataKey="w12" name="Week 12" fill="#f6c90e" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a user retention analytics dashboard with a retention curve and cohort comparison chart", [
    ("project_init", {"name": "retention-dashboard", "template": "data-viz"}, "Created data-viz project 'retention-dashboard'. Write src/App.tsx."),
    ("file_write", {"path": "deliverables/retention-dashboard/src/App.tsx", "content": DV04_APP}, "Written."),
    ("shell_exec", {"command": "cd deliverables/retention-dashboard && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/retention-dashboard/dist/index.html", "expect": "scatter plot and grouped bar chart for user retention"}, "QA passed: retention curve and cohort comparison charts visible."),
    ("message_result", {"text": "Retention dashboard ready. Scatter plot shows retention curve, grouped bar chart compares W1/W4/W12 retention across cohorts."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# DV05: Crypto portfolio tracker — multiple charts + dynamic calculations
# ─────────────────────────────────────────────────────────────────────────────

DV05_APP = """\
import { ChartCard, StatRow } from './components'
import {
  LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const portfolioHistory = [
  { date: 'Jan 1', value: 10000 },
  { date: 'Jan 8', value: 11200 },
  { date: 'Jan 15', value: 10800 },
  { date: 'Jan 22', value: 13400 },
  { date: 'Feb 1', value: 14100 },
  { date: 'Feb 8', value: 12900 },
  { date: 'Feb 15', value: 16200 },
  { date: 'Feb 22', value: 18500 },
  { date: 'Mar 1', value: 17200 },
]

const allocation = [
  { name: 'BTC', value: 45, color: '#f7931a' },
  { name: 'ETH', value: 28, color: '#627eea' },
  { name: 'SOL', value: 15, color: '#9945ff' },
  { name: 'Other', value: 12, color: '#4a9eff' },
]

export default function App() {
  const current = portfolioHistory[portfolioHistory.length - 1].value
  const initial = portfolioHistory[0].value
  const gain = current - initial
  const gainPct = ((gain / initial) * 100).toFixed(1)

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '20px' }}>Crypto Portfolio</h1>
      <StatRow stats={[
        { label: 'Portfolio Value', value: '$' + current.toLocaleString(), change: '+' + gainPct + '%' },
        { label: 'Total Gain', value: '$' + gain.toLocaleString() },
        { label: 'Period', value: 'Jan–Mar 2025' },
      ]} />
      <div className="chart-grid-1-2" style={{ marginTop: '24px' }}>
        <ChartCard title="Portfolio Value Over Time" height={320}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={portfolioHistory}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis tickFormatter={v => '$' + (v/1000).toFixed(0) + 'K'} />
              <Tooltip formatter={v => '$' + Number(v).toLocaleString()} />
              <Line type="monotone" dataKey="value" stroke="#4ecca3" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Asset Allocation" height={320}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={allocation} cx="50%" cy="50%" innerRadius={60} outerRadius={110} dataKey="value" paddingAngle={2}
                label={({name, value}) => name + ' ' + value + '%'}>
                {allocation.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a crypto portfolio tracker with a line chart for value over time and a pie chart for asset allocation", [
    ("project_init", {"name": "crypto-portfolio", "template": "data-viz"}, "Created data-viz project 'crypto-portfolio'. Write src/App.tsx."),
    ("file_write", {"path": "deliverables/crypto-portfolio/src/App.tsx", "content": DV05_APP}, "Written."),
    ("shell_exec", {"command": "cd deliverables/crypto-portfolio && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/crypto-portfolio/dist/index.html", "expect": "line chart and pie chart for portfolio"}, "QA passed: portfolio line chart and donut pie visible."),
    ("message_result", {"text": "Crypto portfolio ready. Line chart tracks portfolio value Jan–Mar 2025. Donut chart shows BTC/ETH/SOL allocation."}, "Delivered."),
])))

# ─────────────────────────────────────────────────────────────────────────────
# DV06: Error recovery — fix missing ResponsiveContainer wrapping
# ─────────────────────────────────────────────────────────────────────────────

DV06_APP_BROKEN = """\
import { ChartCard } from './components'
import { LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'

const data = [{name:'Jan',v:10},{name:'Feb',v:20},{name:'Mar',v:15}]

export default function App() {
  return (
    <div>
      <ChartCard title="Trend">
        <LineChart width={600} height={300} data={data}>
          <XAxis dataKey="name" /><YAxis /><Tooltip />
          <Line dataKey="v" stroke="#4a9eff" />
        </LineChart>
      </ChartCard>
    </div>
  )
}
"""

DV06_APP_FIXED = """\
import { ChartCard } from './components'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const data = [{name:'Jan',v:10},{name:'Feb',v:20},{name:'Mar',v:15}]

export default function App() {
  return (
    <div style={{ padding: '24px' }}>
      <ChartCard title="Monthly Trend" height={300}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="v" stroke="#4a9eff" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  )
}
"""

examples.append(tokenize(build_conv("Build a simple line chart showing monthly trend data", [
    ("project_init", {"name": "trend-chart", "template": "data-viz"}, "Created data-viz project 'trend-chart'. Write src/App.tsx."),
    ("file_write", {"path": "deliverables/trend-chart/src/App.tsx", "content": DV06_APP_BROKEN}, "Written."),
    ("shell_exec", {"command": "cd deliverables/trend-chart && npm run build"},
     "Error: src/App.tsx(9,9): error TS2322: Type '{}' is not assignable to type 'SVGProps<SVGElement>'. Recharts requires ResponsiveContainer wrapper."),
    ("file_edit", {
        "path": "deliverables/trend-chart/src/App.tsx",
        "old_text": DV06_APP_BROKEN.strip(),
        "new_text": DV06_APP_FIXED.strip(),
    }, "Edited."),
    ("shell_exec", {"command": "cd deliverables/trend-chart && npm run build"}, "Build successful. dist/index.html ready."),
    ("undertow", {"path": "deliverables/trend-chart/dist/index.html", "expect": "line chart"}, "QA passed: line chart renders."),
    ("message_result", {"text": "Trend chart ready. Line chart shows monthly data — wrapped in ResponsiveContainer for proper sizing."}, "Delivered."),
])))


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────
out = Path(OUT_PATH)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w") as f:
    for ex in examples:
        f.write(json.dumps(ex) + "\n")

print(f"\nWrote {len(examples)} examples to {out}")
print("\nExamples:")
for i, e in enumerate(["DV01 sales dashboard", "DV02 traffic analytics", "DV03 CSV explorer",
                        "DV04 retention analysis", "DV05 crypto portfolio", "DV06 error recovery"]):
    print(f"  {e}")
print(f"\nTo train the data-viz adapter:")
print(f"  python training/train_unsloth.py \\")
print(f"    --model google/gemma-4-e4b-it \\")
print(f"    --data workspace/training_data/dataviz_sft_v1.jsonl \\")
print(f"    --output models/gemma-4-e4b-tsunami-dataviz-v1 \\")
print(f"    --epochs 3 --lora-r 16 --lr 2e-4")
