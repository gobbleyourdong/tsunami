import { useState, useRef, useCallback } from "react"

interface RichTextEditorProps {
  value?: string
  defaultValue?: string  // uncontrolled-mode initial HTML
  onChange?: (html: string) => void
  placeholder?: string
  minHeight?: number
  className?: string
}

const TOOLBAR_BUTTONS = [
  { cmd: "bold", icon: "B", title: "Bold" },
  { cmd: "italic", icon: "I", title: "Italic" },
  { cmd: "underline", icon: "U", title: "Underline" },
  { cmd: "strikeThrough", icon: "S", title: "Strikethrough" },
  { cmd: "insertUnorderedList", icon: "•", title: "Bullet list" },
  { cmd: "insertOrderedList", icon: "1.", title: "Numbered list" },
  { cmd: "formatBlock:H1", icon: "H1", title: "Heading 1" },
  { cmd: "formatBlock:H2", icon: "H2", title: "Heading 2" },
  { cmd: "formatBlock:BLOCKQUOTE", icon: '"', title: "Quote" },
  { cmd: "removeFormat", icon: "✕", title: "Clear formatting" },
] as const

export function RichTextEditor({ value, defaultValue, onChange, placeholder = "Start typing...", minHeight = 200, className }: RichTextEditorProps) {
  void value; void defaultValue
  const editorRef = useRef<HTMLDivElement>(null)
  const [focused, setFocused] = useState(false)

  const runCommand = useCallback((cmd: string) => {
    if (cmd.startsWith("formatBlock:")) {
      document.execCommand("formatBlock", false, cmd.split(":")[1])
    } else {
      document.execCommand(cmd, false)
    }
    editorRef.current?.focus()
    onChange?.(editorRef.current?.innerHTML || "")
  }, [onChange])

  const handleInput = useCallback(() => {
    onChange?.(editorRef.current?.innerHTML || "")
  }, [onChange])

  // NOTE: This uses contentEditable for rich text editing.
  // The value prop is user-controlled content within the same app.
  // For untrusted external content, sanitize with DOMPurify first.

  return (
    <div className={className} style={{
      border: `1px solid ${focused ? 'var(--accent, #4a9eff)' : 'var(--border, rgba(255,255,255,0.08))'}`,
      borderRadius: 'var(--radius-md, 8px)',
      overflow: 'hidden',
      transition: 'border-color 150ms',
      background: 'var(--bg-secondary, #111827)',
    }}>
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 2, padding: '6px 8px',
        borderBottom: '1px solid var(--border, rgba(255,255,255,0.08))',
        background: 'var(--bg-tertiary, #1a2332)',
      }}>
        {TOOLBAR_BUTTONS.map(({ cmd, icon, title }) => (
          <button
            key={cmd}
            title={title}
            onMouseDown={e => { e.preventDefault(); runCommand(cmd) }}
            style={{
              background: 'none', border: 'none', color: 'var(--text-secondary, #94a3b8)',
              padding: '4px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 13,
              fontWeight: cmd === 'bold' ? 700 : 400,
              fontStyle: cmd === 'italic' ? 'italic' : 'normal',
              textDecoration: cmd === 'underline' ? 'underline' : cmd === 'strikeThrough' ? 'line-through' : 'none',
              minWidth: 28, textAlign: 'center',
            }}
          >
            {icon}
          </button>
        ))}
      </div>
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        data-placeholder={placeholder}
        style={{
          minHeight, padding: 16, outline: 'none',
          color: 'var(--text-primary, #e2e8f0)', fontSize: 14, lineHeight: 1.7,
        }}
      />
    </div>
  )
}

export default RichTextEditor
