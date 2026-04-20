import { useState, useEffect } from "react"

interface TypeWriterProps {
  texts?: string[]       // strings to cycle through
  words?: string[]       // alias drones reach for
  speed?: number        // ms per character
  pause?: number        // ms pause between strings
  cursor?: boolean
  loop?: boolean        // implied true today; explicit prop for future single-pass
  style?: React.CSSProperties
}

/** Typewriter effect — cycles through text strings. */
export function TypeWriter({ texts, words, speed = 60, pause = 2000, cursor = true, loop = true, style }: TypeWriterProps) {
  void loop
  const list = (texts ?? words ?? [""]) as string[]
  const [textIndex, setTextIndex] = useState(0)
  const [charIndex, setCharIndex] = useState(0)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const current = list[textIndex]
    if (!deleting && charIndex === current.length) {
      const t = setTimeout(() => setDeleting(true), pause)
      return () => clearTimeout(t)
    }
    if (deleting && charIndex === 0) {
      setDeleting(false)
      setTextIndex(i => (i + 1) % list.length)
      return
    }
    const t = setTimeout(() => {
      setCharIndex(i => deleting ? i - 1 : i + 1)
    }, deleting ? speed / 2 : speed)
    return () => clearTimeout(t)
  }, [charIndex, deleting, textIndex, list, speed, pause])

  return (
    <span style={style}>
      {list[textIndex].slice(0, charIndex)}
      {cursor && <span style={{ borderRight: "2px solid var(--accent)", marginLeft: 2, animation: "blink 1s infinite" }}>
        <style>{`@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }`}</style>
      </span>}
    </span>
  )
}

export default TypeWriter
