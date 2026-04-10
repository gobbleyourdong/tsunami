import "./index.css"
import { useState } from 'react'
import { Card, Button, Input, Alert } from './components/ui'

export default function App() {
  const [submitted, setSubmitted] = useState(false)

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6">Form</h1>

        {submitted && (
          <Alert className="mb-4">Submitted successfully!</Alert>
        )}

        <form onSubmit={(e) => { e.preventDefault(); setSubmitted(true) }} className="flex flex-col gap-4">
          <div>
            <label className="text-sm text-muted mb-1 block">Name</label>
            <Input placeholder="Enter your name" />
          </div>
          <div>
            <label className="text-sm text-muted mb-1 block">Email</label>
            <Input type="email" placeholder="you@example.com" />
          </div>
          <div>
            <label className="text-sm text-muted mb-1 block">Message</label>
            <textarea
              className="w-full bg-2 rounded p-3 text-sm border border-white/10 focus:border-accent outline-none resize-none"
              rows={4}
              placeholder="TODO: Replace with your form fields"
            />
          </div>
          <Button type="submit" className="mt-2">Submit</Button>
        </form>
      </Card>
    </div>
  )
}
