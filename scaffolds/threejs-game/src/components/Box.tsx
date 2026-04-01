import { RigidBody } from "@react-three/rapier"
import { useRef } from "react"
import { Mesh } from "three"

interface BoxProps {
  position?: [number, number, number]
  size?: [number, number, number]
  color?: string
  mass?: number
}

/** A physics-enabled box. Drop it in the scene and it falls. */
export default function Box({
  position = [0, 5, 0],
  size = [1, 1, 1],
  color = "#ff6644",
  mass = 1,
}: BoxProps) {
  const ref = useRef<Mesh>(null)

  return (
    <RigidBody position={position} mass={mass}>
      <mesh ref={ref} castShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial color={color} />
      </mesh>
    </RigidBody>
  )
}
