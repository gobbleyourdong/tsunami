import { useEffect, useRef } from "react"

/**
 * Declarative setInterval. Callback always sees latest props/state without
 * resubscribing the timer. Pass delay=null to pause.
 */
export function useInterval(callback: () => void, delay: number | null): void {
  const saved = useRef(callback)

  useEffect(() => {
    saved.current = callback
  }, [callback])

  useEffect(() => {
    if (delay === null) return
    const id = setInterval(() => saved.current(), delay)
    return () => clearInterval(id)
  }, [delay])
}
