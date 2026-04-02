import "./index.css"
// TODO: Replace with your dashboard
import { Layout, StatCard, Card } from "./components"

export default function App() {
  return (
    <Layout title="Dashboard" navItems={[{ label: "Overview", id: "overview" }]}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 24 }}>
        <StatCard label="Metric" value="0" />
      </div>
      <Card title="Data">
        <p style={{ color: "#666" }}>Replace this with your content.</p>
      </Card>
    </Layout>
  )
}
