import "./index.css"
import { Card, Button, Badge } from './components/ui'

export default function App() {
  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="flex justify-between items-center p-6 max-w-6xl mx-auto">
        <h1 className="text-xl font-bold">Brand</h1>
        <div className="flex gap-4 items-center">
          <a className="text-muted hover:text-white transition" href="#">Features</a>
          <a className="text-muted hover:text-white transition" href="#">Pricing</a>
          <Button>Get Started</Button>
        </div>
      </nav>

      {/* Hero */}
      <section className="text-center py-24 px-6 max-w-4xl mx-auto">
        <Badge className="mb-4">New Release</Badge>
        <h2 className="text-5xl font-bold mb-6 leading-tight">Build something amazing today</h2>
        <p className="text-xl text-muted mb-8 max-w-2xl mx-auto">
          TODO: Replace with your product description. This is the landing page scaffold.
        </p>
        <div className="flex gap-4 justify-center">
          <Button className="text-lg px-8 py-3">Start Free</Button>
          <Button className="text-lg px-8 py-3 ghost">Learn More</Button>
        </div>
      </section>

      {/* Features */}
      <section className="grid grid-3 gap-6 max-w-6xl mx-auto px-6 py-16">
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-2">Feature One</h3>
          <p className="text-muted">TODO: Describe your first feature here.</p>
        </Card>
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-2">Feature Two</h3>
          <p className="text-muted">TODO: Describe your second feature here.</p>
        </Card>
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-2">Feature Three</h3>
          <p className="text-muted">TODO: Describe your third feature here.</p>
        </Card>
      </section>

      {/* Footer */}
      <footer className="text-center py-8 text-muted text-sm border-t border-white/5">
        © 2026 Brand. All rights reserved.
      </footer>
    </div>
  )
}
