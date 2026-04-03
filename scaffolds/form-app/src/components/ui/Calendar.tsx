import { useState, useMemo } from "react"

interface CalendarEvent {
  date: string // YYYY-MM-DD
  label: string
  color?: string
}

interface CalendarProps {
  value?: Date
  onChange?: (date: Date) => void
  events?: CalendarEvent[]
  rangeStart?: Date
  rangeEnd?: Date
}

const DAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

function formatDate(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function Calendar({ value, onChange, events = [], rangeStart, rangeEnd }: CalendarProps) {
  const today = new Date()
  const [viewYear, setViewYear] = useState(value?.getFullYear() ?? today.getFullYear())
  const [viewMonth, setViewMonth] = useState(value?.getMonth() ?? today.getMonth())

  const daysInMonth = getDaysInMonth(viewYear, viewMonth)
  const firstDay = getFirstDayOfMonth(viewYear, viewMonth)

  const eventMap = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const e of events) {
      if (!map[e.date]) map[e.date] = []
      map[e.date].push(e)
    }
    return map
  }, [events])

  const prev = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(y => y - 1) }
    else setViewMonth(m => m - 1)
  }
  const next = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(y => y + 1) }
    else setViewMonth(m => m + 1)
  }

  const isInRange = (d: Date) => {
    if (!rangeStart || !rangeEnd) return false
    return d >= rangeStart && d <= rangeEnd
  }

  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div style={{
      width: 280, background: 'var(--bg-secondary, #111827)',
      border: '1px solid var(--border, rgba(255,255,255,0.08))',
      borderRadius: 'var(--radius-md, 8px)', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 12px', background: 'var(--bg-tertiary, #1a2332)',
      }}>
        <button onClick={prev} style={{ background: 'none', border: 'none', color: 'var(--text-secondary, #94a3b8)', cursor: 'pointer', fontSize: 16 }}>‹</button>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary, #e2e8f0)' }}>
          {MONTHS[viewMonth]} {viewYear}
        </span>
        <button onClick={next} style={{ background: 'none', border: 'none', color: 'var(--text-secondary, #94a3b8)', cursor: 'pointer', fontSize: 16 }}>›</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', padding: '4px 8px' }}>
        {DAYS.map(d => (
          <div key={d} style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-dim, #4a4f5e)', padding: '4px 0', fontWeight: 600 }}>{d}</div>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <div key={`e${i}`} />
          const date = new Date(viewYear, viewMonth, day)
          const dateStr = formatDate(date)
          const isToday = dateStr === formatDate(today)
          const isSelected = value && dateStr === formatDate(value)
          const inRange = isInRange(date)
          const dayEvents = eventMap[dateStr] || []

          return (
            <div
              key={i}
              onClick={() => onChange?.(date)}
              style={{
                textAlign: 'center', padding: '6px 2px', cursor: 'pointer',
                borderRadius: 6, fontSize: 13, position: 'relative',
                background: isSelected ? 'var(--accent, #4a9eff)' : inRange ? 'rgba(74, 158, 255, 0.1)' : 'transparent',
                color: isSelected ? '#fff' : isToday ? 'var(--accent, #4a9eff)' : 'var(--text-primary, #e2e8f0)',
                fontWeight: isToday || isSelected ? 700 : 400,
                transition: 'background 100ms',
              }}
            >
              {day}
              {dayEvents.length > 0 && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: 2, marginTop: 2 }}>
                  {dayEvents.slice(0, 3).map((e, j) => (
                    <div key={j} style={{ width: 4, height: 4, borderRadius: '50%', background: e.color || 'var(--accent, #4a9eff)' }} />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
