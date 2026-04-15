import { useState, ReactNode } from "react"

interface TooltipProps {
  text: string
  children: ReactNode
  position?: "top" | "bottom" | "left" | "right"
}

const positions = {
  top:    { bottom: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
  bottom: { top: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
  left:   { right: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
  right:  { left: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
} as const

export function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const [show, setShow] = useState(false)

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div style={{
          position: 'absolute',
          ...positions[position],
          background: 'var(--bg-3, #21252f)',
          border: '1px solid var(--border-hover, rgba(255,255,255,0.12))',
          borderRadius: 8,
          padding: '6px 12px',
          fontSize: 'var(--text-xs, 0.75rem)',
          fontWeight: 500,
          color: 'var(--text, #e2e4e9)',
          whiteSpace: 'nowrap',
          zIndex: 200,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          animation: 'scale-in 150ms cubic-bezier(0.22, 1.2, 0.36, 1)',
          pointerEvents: 'none',
        }}>
          {text}
        </div>
      )}
    </div>
  )
}

export default Tooltip
