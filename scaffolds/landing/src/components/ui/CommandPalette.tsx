import { useState, useEffect, useCallback, useRef, useMemo } from "react"

interface Command {
  id: string
  label: string
  description?: string
  shortcut?: string
  action: () => void
  category?: string
}

interface CommandPaletteProps {
  commands: Command[]
  placeholder?: string
  trigger?: string
}

function fuzzyMatch(query: string, text: string): boolean {
  let qi = 0
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++
  }
  return qi === q.length
}

export default function CommandPalette({ commands, placeholder = "Type a command...", trigger = "k" }: CommandPaletteProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const filtered = useMemo(() => {
    if (!query) return commands
    return commands.filter(c => fuzzyMatch(query, c.label) || fuzzyMatch(query, c.description || ""))
  }, [commands, query])

  const grouped = useMemo(() => {
    const groups: Record<string, Command[]> = {}
    for (const cmd of filtered) {
      const cat = cmd.category || "Actions"
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(cmd)
    }
    return groups
  }, [filtered])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === trigger) {
        e.preventDefault()
        setOpen(v => !v)
        setQuery("")
        setSelected(0)
      }
      if (e.key === "Escape" && open) setOpen(false)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open, trigger])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)) }
    if (e.key === "ArrowUp") { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)) }
    if (e.key === "Enter" && filtered[selected]) {
      filtered[selected].action()
      setOpen(false)
    }
  }, [filtered, selected])

  if (!open) return null

  return (
    <div
      onClick={() => setOpen(false)}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(8, 9, 13, 0.7)', backdropFilter: 'blur(4px)',
        display: 'flex', justifyContent: 'center', paddingTop: '15vh',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 560, maxHeight: '60vh',
          background: 'var(--bg-secondary, #111827)',
          border: '1px solid var(--border, rgba(255,255,255,0.08))',
          borderRadius: 'var(--radius-lg, 12px)',
          overflow: 'hidden', boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border, rgba(255,255,255,0.08))' }}>
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0) }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            style={{
              width: '100%', background: 'none', border: 'none', outline: 'none',
              color: 'var(--text-primary, #e2e8f0)', fontSize: 16,
            }}
          />
        </div>
        <div style={{ maxHeight: 'calc(60vh - 56px)', overflow: 'auto', padding: '4px 0' }}>
          {Object.entries(grouped).map(([category, cmds]) => (
            <div key={category}>
              <div style={{
                padding: '8px 16px 4px', fontSize: 11, fontWeight: 600,
                color: 'var(--text-dim, #4a4f5e)', textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                {category}
              </div>
              {cmds.map(cmd => {
                const idx = filtered.indexOf(cmd)
                return (
                  <div
                    key={cmd.id}
                    onClick={() => { cmd.action(); setOpen(false) }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 16px', cursor: 'pointer',
                      background: idx === selected ? 'var(--bg-tertiary, #1a2332)' : 'transparent',
                    }}
                    onMouseEnter={() => setSelected(idx)}
                  >
                    <div>
                      <div style={{ fontSize: 14, color: 'var(--text-primary, #e2e8f0)' }}>{cmd.label}</div>
                      {cmd.description && <div style={{ fontSize: 12, color: 'var(--text-dim, #4a4f5e)', marginTop: 2 }}>{cmd.description}</div>}
                    </div>
                    {cmd.shortcut && (
                      <kbd style={{
                        fontSize: 11, padding: '2px 6px', borderRadius: 4,
                        background: 'var(--bg-primary, #0a0e17)',
                        border: '1px solid var(--border, rgba(255,255,255,0.08))',
                        color: 'var(--text-dim, #4a4f5e)',
                      }}>
                        {cmd.shortcut}
                      </kbd>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim, #4a4f5e)' }}>No commands found</div>
          )}
        </div>
      </div>
    </div>
  )
}
