import "./index.css"
import { Card, Badge, Button, Progress } from './components/ui'

const data = [
  { label: 'Jan', value: 65 },
  { label: 'Feb', value: 78 },
  { label: 'Mar', value: 52 },
  { label: 'Apr', value: 91 },
  { label: 'May', value: 84 },
  { label: 'Jun', value: 73 },
]

export default function App() {
  const max = Math.max(...data.map(d => d.value))

  return (
    <div className="min-h-screen p-8 max-w-5xl mx-auto">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Data Visualization</h1>
        <Badge>Live</Badge>
      </header>

      <div className="grid grid-3 gap-4 mb-8">
        <Card className="p-4">
          <p className="text-muted text-sm">Total</p>
          <p className="text-2xl font-bold">{data.reduce((s, d) => s + d.value, 0)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-muted text-sm">Average</p>
          <p className="text-2xl font-bold">{Math.round(data.reduce((s, d) => s + d.value, 0) / data.length)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-muted text-sm">Peak</p>
          <p className="text-2xl font-bold">{max}</p>
        </Card>
      </div>

      {/* Bar chart */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-6">Monthly Overview</h2>
        <div className="flex items-end gap-3 h-48">
          {data.map(d => (
            <div key={d.label} className="flex-1 flex flex-col items-center gap-2">
              <span className="text-sm font-medium">{d.value}</span>
              <div
                className="w-full bg-accent/80 rounded-t transition-all"
                style={{ height: `${(d.value / max) * 100}%` }}
              />
              <span className="text-xs text-muted">{d.label}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
