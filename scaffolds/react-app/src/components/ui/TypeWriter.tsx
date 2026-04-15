import { useState, useEffect } from "react"

interface TypeWriterProps {
  texts: string[]       // strings to cycle through
  speed?: number        // ms per character
  pause?: number        // ms pause between strings
  cursor?: boolean
  style?: React.CSSProperties
}

/** Typewriter effect — cycles through text strings. */
export function TypeWriter({ texts, speed = 60, pause = 2000, cursor = true, style }: TypeWriterProps) {
  const [textIndex, setTextIndex] = useState(0)
  const [charIndex, setCharIndex] = useState(0)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const current = texts[textIndex]
    if (!deleting && charIndex === current.length) {
      const t = setTimeout(() => setDeleting(true), pause)
      return () => clearTimeout(t)
    }
    if (deleting && charIndex === 0) {
      setDeleting(false)
      setTextIndex(i => (i + 1) % texts.length)
      return
    }
    const t = setTimeout(() => {
      setCharIndex(i => deleting ? i - 1 : i + 1)
    }, deleting ? speed / 2 : speed)
    return () => clearTimeout(t)
  }, [charIndex, deleting, textIndex, texts, speed, pause])

  return (
    <span style={style}>
      {texts[textIndex].slice(0, charIndex)}
      {cursor && <span style={{ borderRight: "2px solid var(--accent)", marginLeft: 2, animation: "blink 1s infinite" }}>
        <style>{`@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }`}</style>
      </span>}
    </span>
  )
}

export default TypeWriter
