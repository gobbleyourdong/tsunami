import "./index.css"
import { useState, useEffect } from 'react'
import { Card, Button, Badge, Input } from './components/ui'

interface Message {
  id: number
  text: string
  time: string
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, text: 'Welcome to the chat!', time: '12:00' },
    { id: 2, text: 'Messages update in real-time.', time: '12:01' },
  ])
  const [input, setInput] = useState('')
  const [online, setOnline] = useState(3)

  const send = () => {
    if (!input.trim()) return
    const now = new Date()
    setMessages(prev => [...prev, {
      id: Date.now(),
      text: input,
      time: `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`,
    }])
    setInput('')
  }

  return (
    <div className="min-h-screen flex flex-col max-w-2xl mx-auto p-4">
      {/* Header */}
      <div className="flex justify-between items-center p-4 border-b border-white/5">
        <h1 className="text-xl font-bold">Live Chat</h1>
        <Badge>{online} online</Badge>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {messages.map(msg => (
          <Card key={msg.id} className="p-3 max-w-[80%]">
            <p>{msg.text}</p>
            <span className="text-xs text-muted mt-1 block">{msg.time}</span>
          </Card>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-white/5 flex gap-3">
        <Input
          value={input}
          onChange={(e: any) => setInput(e.target.value)}
          placeholder="Type a message..."
          onKeyDown={(e: any) => e.key === 'Enter' && send()}
          className="flex-1"
        />
        <Button onClick={send}>Send</Button>
      </div>
    </div>
  )
}
