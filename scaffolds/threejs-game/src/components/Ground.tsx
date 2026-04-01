import { RigidBody } from "@react-three/rapier"

interface GroundProps {
  size?: [number, number]
  color?: string
  position?: [number, number, number]
}

/** Static physics ground plane. Objects fall and land on this. */
export default function Ground({
  size = [50, 50],
  color = "#2a2a3e",
  position = [0, 0, 0],
}: GroundProps) {
  return (
    <RigidBody type="fixed" position={position}>
      <mesh receiveShadow rotation-x={-Math.PI / 2}>
        <planeGeometry args={size} />
        <meshStandardMaterial color={color} />
      </mesh>
    </RigidBody>
  )
}
