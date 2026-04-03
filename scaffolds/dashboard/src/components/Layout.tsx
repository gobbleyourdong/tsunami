import { ReactNode, useState } from "react"

interface NavItem { label: string; id: string; icon?: string }

interface LayoutProps {
  children: ReactNode
  title?: string
  navItems?: NavItem[]
  activeNav?: string
  onNav?: (id: string) => void
}

export default function Layout({
  children, title = "Dashboard", navItems = [], activeNav, onNav,
}: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="dashboard-layout">
      <nav className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-header">
          <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? "→" : "←"}
          </button>
          {!collapsed && <span className="sidebar-title">{title}</span>}
        </div>
        <div className="sidebar-nav">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-item ${activeNav === item.id ? "active" : ""}`}
              onClick={() => onNav?.(item.id)}
            >
              {item.icon && <span className="nav-icon">{item.icon}</span>}
              {!collapsed && <span>{item.label}</span>}
            </button>
          ))}
        </div>
      </nav>
      <div className="main-area">
        <header className="top-header">
          <h1>{title}</h1>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
