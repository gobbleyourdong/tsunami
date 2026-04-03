import { ReactNode, useState } from "react"

interface NavItem {
  label: string
  id: string
  icon?: string
  section?: string
}

interface LayoutProps {
  children: ReactNode
  title?: string
  navItems?: NavItem[]
  activeNav?: string
  onNav?: (id: string) => void
  headerRight?: ReactNode
}

export default function Layout({
  children, title = "Dashboard", navItems = [], activeNav, onNav, headerRight,
}: LayoutProps) {
  const [collapsed, setCollapsed] = useState(false)

  // Group nav items by section
  const sections = navItems.reduce<Record<string, NavItem[]>>((acc, item) => {
    const key = item.section || "_default"
    ;(acc[key] ||= []).push(item)
    return acc
  }, {})

  return (
    <div className="dashboard-layout">
      <nav className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-header">
          {!collapsed && <span className="sidebar-title">{title}</span>}
          <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? "→" : "←"}
          </button>
        </div>
        <div className="sidebar-nav">
          {Object.entries(sections).map(([section, items]) => (
            <div key={section}>
              {section !== "_default" && !collapsed && (
                <div className="nav-section-label">{section}</div>
              )}
              {items.map(item => (
                <button
                  key={item.id}
                  className={`nav-item ${activeNav === item.id ? "active" : ""}`}
                  onClick={() => onNav?.(item.id)}
                  title={collapsed ? item.label : undefined}
                >
                  {item.icon && <span className="nav-icon">{item.icon}</span>}
                  {!collapsed && <span className="nav-label">{item.label}</span>}
                </button>
              ))}
            </div>
          ))}
        </div>
      </nav>
      <div className="main-area">
        <header className="top-header">
          <h1>{title}</h1>
          {headerRight && <div className="flex gap-2">{headerRight}</div>}
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
