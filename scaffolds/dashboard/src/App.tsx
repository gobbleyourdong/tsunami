import "./index.css"
import { Card, Button, Badge, Progress, Avatar } from './components/ui'

export default function App() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <nav className="w-64 bg-1 p-4 flex flex-col gap-2 border-r border-white/5">
        <h1 className="text-lg font-bold p-2 mb-4">Dashboard</h1>
        <Button className="justify-start">Overview</Button>
        <Button className="justify-start text-muted">Analytics</Button>
        <Button className="justify-start text-muted">Settings</Button>
      </nav>

      {/* Main */}
      <main className="flex-1 p-8">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-2xl font-bold">Overview</h2>
          <Avatar className="w-8 h-8" />
        </div>

        {/* Stats */}
        <div className="grid grid-4 gap-4 mb-8">
          <Card className="p-4">
            <p className="text-muted text-sm">Total Users</p>
            <p className="text-2xl font-bold mt-1">1,234</p>
            <Badge className="mt-2">+12%</Badge>
          </Card>
          <Card className="p-4">
            <p className="text-muted text-sm">Revenue</p>
            <p className="text-2xl font-bold mt-1">$45,678</p>
            <Badge className="mt-2">+8%</Badge>
          </Card>
          <Card className="p-4">
            <p className="text-muted text-sm">Orders</p>
            <p className="text-2xl font-bold mt-1">892</p>
            <Badge className="mt-2">+5%</Badge>
          </Card>
          <Card className="p-4">
            <p className="text-muted text-sm">Conversion</p>
            <p className="text-2xl font-bold mt-1">3.2%</p>
            <Progress value={32} className="mt-2" />
          </Card>
        </div>

        {/* Content area */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
          <p className="text-muted">TODO: Replace with your dashboard content</p>
        </Card>
      </main>
    </div>
  )
}
