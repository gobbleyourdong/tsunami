import "./index.css"
import { useState } from 'react'
import { Card, Button, Input, Badge, Alert } from './components/ui'

interface Item {
  id: number
  text: string
  done: boolean
}

export default function App() {
  const [items, setItems] = useState<Item[]>([
    { id: 1, text: 'Set up database', done: true },
    { id: 2, text: 'Build API endpoints', done: false },
    { id: 3, text: 'Connect frontend', done: false },
  ])
  const [input, setInput] = useState('')

  const addItem = () => {
    if (!input.trim()) return
    setItems(prev => [...prev, { id: Date.now(), text: input, done: false }])
    setInput('')
  }

  const toggle = (id: number) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, done: !i.done } : i))
  }

  return (
    <div className="min-h-screen p-8 max-w-2xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Fullstack App</h1>
        <p className="text-muted mt-2">TODO: Connect to your API backend</p>
      </header>

      <Card className="p-6 mb-6">
        <div className="flex gap-3">
          <Input
            value={input}
            onChange={(e: any) => setInput(e.target.value)}
            placeholder="Add a task..."
            onKeyDown={(e: any) => e.key === 'Enter' && addItem()}
            className="flex-1"
          />
          <Button onClick={addItem}>Add</Button>
        </div>
      </Card>

      <div className="flex flex-col gap-2">
        {items.map(item => (
          <Card key={item.id} className="p-4 flex items-center gap-3">
            <input
              type="checkbox"
              checked={item.done}
              onChange={() => toggle(item.id)}
              className="w-4 h-4 accent-accent"
            />
            <span className={item.done ? 'line-through text-muted flex-1' : 'flex-1'}>{item.text}</span>
            {item.done && <Badge>Done</Badge>}
          </Card>
        ))}
      </div>

      <Alert className="mt-6">
        {items.filter(i => i.done).length}/{items.length} tasks complete
      </Alert>
    </div>
  )
}
