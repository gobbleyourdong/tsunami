import { useState, ReactNode } from "react"

interface Tab {
  id: string
  label: string
  content: ReactNode
}

interface TabsProps {
  tabs: Tab[]
  defaultTab?: string
}

/** Tab navigation — pass tabs with id, label, content. */
export default function Tabs({ tabs, defaultTab }: TabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id || "")

  return (
    <div>
      <div className="flex gap-2" style={{ borderBottom: "1px solid var(--border)", marginBottom: 16 }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            style={{
              borderBottom: active === tab.id ? "2px solid var(--accent)" : "2px solid transparent",
              borderRadius: 0,
              background: "none",
              border: "none",
              borderBottomWidth: 2,
              borderBottomStyle: "solid",
              borderBottomColor: active === tab.id ? "var(--accent)" : "transparent",
              color: active === tab.id ? "var(--accent)" : "var(--text-muted)",
              padding: "8px 16px",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.find(t => t.id === active)?.content}
    </div>
  )
}
