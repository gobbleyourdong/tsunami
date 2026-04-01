import { RigidBody } from "@react-three/rapier"
import { useRef } from "react"
import { Mesh } from "three"

interface SphereProps {
  position?: [number, number, number]
  radius?: number
  color?: string
  mass?: number
}

/** A physics-enabled sphere. Rolls, bounces, collides. */
export default function Sphere({
  position = [0, 5, 0],
  radius = 0.5,
  color = "#44aaff",
  mass = 1,
}: SphereProps) {
  const ref = useRef<Mesh>(null)

  return (
    <RigidBody position={position} mass={mass} colliders="ball">
      <mesh ref={ref} castShadow>
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial color={color} />
      </mesh>
    </RigidBody>
  )
}
