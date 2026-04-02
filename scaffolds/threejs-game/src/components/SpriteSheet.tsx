import { useRef, useMemo } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

interface SpriteSheetProps {
  texture: string          // path to sprite sheet image
  columns: number          // number of columns in sheet
  rows: number             // number of rows in sheet
  fps?: number             // animation speed
  scale?: [number, number] // billboard size
  position?: [number, number, number]
}

/** Animated sprite from a sprite sheet — 2D character in 3D scene.
 *  Cycles through frames at the given fps. */
export default function SpriteSheet({
  texture,
  columns,
  rows,
  fps = 12,
  scale = [1, 1],
  position = [0, 0, 0],
}: SpriteSheetProps) {
  const ref = useRef<THREE.Mesh>(null)
  const frameRef = useRef(0)
  const timeRef = useRef(0)

  const tex = useMemo(() => {
    const t = new THREE.TextureLoader().load(texture)
    t.repeat.set(1 / columns, 1 / rows)
    t.magFilter = THREE.NearestFilter
    return t
  }, [texture, columns, rows])

  useFrame((_, dt) => {
    timeRef.current += dt
    if (timeRef.current > 1 / fps) {
      timeRef.current = 0
      frameRef.current = (frameRef.current + 1) % (columns * rows)
      const col = frameRef.current % columns
      const row = Math.floor(frameRef.current / columns)
      tex.offset.set(col / columns, 1 - (row + 1) / rows)
    }
    // Billboard: always face camera
    if (ref.current) {
      ref.current.lookAt(ref.current.position.clone().add(new THREE.Vector3(0, 0, 1)))
    }
  })

  return (
    <mesh ref={ref} position={position}>
      <planeGeometry args={scale} />
      <meshBasicMaterial map={tex} transparent alphaTest={0.1} />
    </mesh>
  )
}
