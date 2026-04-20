import { useState, useRef, ReactNode } from "react"

interface TooltipProps {
  text?: string
  content?: ReactNode  // shadcn/radix alias for `text`
  children: ReactNode
  position?: "top" | "bottom" | "left" | "right"
  placement?: "top" | "bottom" | "left" | "right"  // popper-style alias
  delay?: number  // ms — delay before show
}

const positions = {
  top:    { bottom: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
  bottom: { top: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
  left:   { right: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
  right:  { left: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
} as const

export function Tooltip({ text, content, children, position, placement, delay = 0 }: TooltipProps) {
  const [show, setShow] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const pos = placement ?? position ?? "top"
  const body = content ?? text

  const onEnter = () => {
    if (delay > 0) {
      timer.current = setTimeout(() => setShow(true), delay)
    } else {
      setShow(true)
    }
  }
  const onLeave = () => {
    clearTimeout(timer.current)
    setShow(false)
  }

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      {children}
      {show && body != null && (
        <div style={{
          position: 'absolute',
          ...positions[pos],
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
          {body}
        </div>
      )}
    </div>
  )
}

export default Tooltip
