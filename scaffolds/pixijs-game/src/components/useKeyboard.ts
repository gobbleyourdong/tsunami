import { useEffect, useRef } from "react"

type KeyMap = Record<string, boolean>

/** Track which keys are currently pressed. Updates every frame.
 *
 * Usage:
 *   const keys = useKeyboard()
 *   // in game loop: if (keys.current["ArrowLeft"]) player.x -= 5
 */
export function useKeyboard(): React.MutableRefObject<KeyMap> {
  const keys = useRef<KeyMap>({})

  useEffect(() => {
    const down = (e: KeyboardEvent) => { keys.current[e.code] = true }
    const up = (e: KeyboardEvent) => { keys.current[e.code] = false }
    window.addEventListener("keydown", down)
    window.addEventListener("keyup", up)
    return () => {
      window.removeEventListener("keydown", down)
      window.removeEventListener("keyup", up)
    }
  }, [])

  return keys
}

/** Check if a specific key is pressed right now */
export function isPressed(keys: React.MutableRefObject<KeyMap>, code: string): boolean {
  return !!keys.current[code]
}
