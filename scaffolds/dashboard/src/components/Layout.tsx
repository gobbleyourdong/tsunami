import { ReactNode, useState } from "react"

interface LayoutProps {
  children: ReactNode
  title?: string
  navItems?: { label: string; id: string }[]
  onNav?: (id: string) => void
}

/** Dashboard layout with collapsible sidebar and header. */
export default function Layout({
  children,
  title = "Dashboard",
  navItems = [],
  onNav,
}: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f0f1a", color: "#e0e0e0", fontFamily: "system-ui" }}>
      {/* Sidebar */}
      <nav style={{
        width: collapsed ? 60 : 220,
        background: "#1a1a2e",
        borderRight: "1px solid #2a2a4a",
        padding: "16px 0",
        transition: "width 0.2s",
        overflow: "hidden",
        flexShrink: 0,
      }}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            background: "none", border: "none", color: "#888",
            cursor: "pointer", padding: "8px 16px", width: "100%", textAlign: "left",
          }}
        >
          {collapsed ? "→" : "← Collapse"}
        </button>
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => onNav?.(item.id)}
            style={{
              display: "block", width: "100%", textAlign: "left",
              background: "none", border: "none", color: "#ccc",
              padding: "12px 16px", cursor: "pointer",
              fontSize: 14, whiteSpace: "nowrap",
            }}
          >
            {collapsed ? item.label[0] : item.label}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <header style={{
          padding: "16px 24px",
          borderBottom: "1px solid #2a2a4a",
          fontSize: 20,
          fontWeight: 600,
        }}>
          {title}
        </header>
        <main style={{ padding: 24 }}>
          {children}
        </main>
      </div>
    </div>
  )
}
