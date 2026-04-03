import { useRef, useEffect } from "react"
import { Application, Container, Graphics, Text, TextStyle } from "pixi.js"

interface GameCanvasProps {
  width?: number
  height?: number
  bgColor?: number
  onApp?: (app: Application) => void
}

/** PixiJS canvas — high-performance 2D rendering.
 *  Get the app instance via onApp callback to add sprites/containers. */
export default function GameCanvas({
  width = 800,
  height = 600,
  bgColor = 0x0a0a1a,
  onApp,
}: GameCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<Application | null>(null)

  useEffect(() => {
    if (!containerRef.current || appRef.current) return

    const app = new Application()
    const init = async () => {
      await app.init({
        width,
        height,
        backgroundColor: bgColor,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      })

      containerRef.current?.appendChild(app.canvas as HTMLCanvasElement)
      appRef.current = app
      onApp?.(app)
    }

    init()

    return () => {
      app.destroy(true)
      appRef.current = null
    }
  }, [])

  return <div ref={containerRef} style={{ display: "inline-block" }} />
}

/** Helper: create a colored rectangle sprite */
export function createRect(
  x: number, y: number, w: number, h: number,
  color: number = 0x44aaff
): Graphics {
  const g = new Graphics()
  g.rect(0, 0, w, h).fill(color)
  g.position.set(x, y)
  return g
}

/** Helper: create a circle sprite */
export function createCircle(
  x: number, y: number, radius: number,
  color: number = 0xff4488
): Graphics {
  const g = new Graphics()
  g.circle(0, 0, radius).fill(color)
  g.position.set(x, y)
  return g
}

/** Helper: create text */
export function createText(
  content: string, x: number, y: number,
  style?: Partial<TextStyle>
): Text {
  const text = new Text({
    text: content,
    style: {
      fontFamily: "Rajdhani, sans-serif",
      fontSize: 24,
      fill: 0x4a9eff,
      ...style,
    },
  })
  text.position.set(x, y)
  return text
}
