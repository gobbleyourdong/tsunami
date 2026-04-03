import { useState, useEffect } from "react"

/** React hook for CSS media queries. Returns true when the query matches. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined") return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    mql.addEventListener("change", handler)
    setMatches(mql.matches)
    return () => mql.removeEventListener("change", handler)
  }, [query])

  return matches
}

/** Convenience: true when viewport ≤ 768px */
export function useMobile(): boolean {
  return useMediaQuery("(max-width: 768px)")
}
