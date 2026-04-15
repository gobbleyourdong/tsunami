import "./index.css"
import { useState } from 'react'
import { Card, Button, Badge } from './components/ui'
// Hooks available from './hooks': useLocalStorage, useDebounce, useMediaQuery,
// useMobile, useInterval. Prefer them over rolling raw localStorage / setInterval.

export default function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen p-8 max-w-4xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">My App</h1>
        <p className="text-muted mt-2">TODO: Replace with your app content</p>
      </header>

      <div className="grid grid-2 gap-6">
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Counter</h2>
          <div className="flex items-center gap-4">
            <Button onClick={() => setCount(c => c - 1)}>-</Button>
            <span className="text-2xl font-bold">{count}</span>
            <Button onClick={() => setCount(c => c + 1)}>+</Button>
          </div>
          <Badge className="mt-3">{count} clicks</Badge>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Getting Started</h2>
          <p className="text-muted text-sm">
            Edit <code className="bg-2 px-1 rounded">src/App.tsx</code> to build your app.
            Components available in <code className="bg-2 px-1 rounded">./components/ui</code>.
          </p>
        </Card>
      </div>
    </div>
  )
}
