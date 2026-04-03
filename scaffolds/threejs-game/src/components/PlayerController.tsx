import { useRef, useEffect } from "react"
import { useFrame } from "@react-three/fiber"
import { RigidBody, RapierRigidBody } from "@react-three/rapier"
import { Vector3 } from "three"

interface PlayerControllerProps {
  position?: [number, number, number]
  speed?: number
  jumpForce?: number
  color?: string
  size?: [number, number, number]
}

/** WASD + Space player controller with physics.
 *  Drop in Scene alongside Ground for instant playable character. */
export default function PlayerController({
  position = [0, 2, 0],
  speed = 5,
  jumpForce = 5,
  color = "#00ffcc",
  size = [0.8, 1.6, 0.8],
}: PlayerControllerProps) {
  const body = useRef<RapierRigidBody>(null)
  const keys = useRef<Record<string, boolean>>({})

  useEffect(() => {
    const down = (e: KeyboardEvent) => { keys.current[e.code] = true }
    const up = (e: KeyboardEvent) => { keys.current[e.code] = false }
    window.addEventListener("keydown", down)
    window.addEventListener("keyup", up)
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up) }
  }, [])

  useFrame(() => {
    if (!body.current) return
    const vel = body.current.linvel()
    const move = new Vector3(0, 0, 0)

    if (keys.current["KeyW"] || keys.current["ArrowUp"]) move.z -= speed
    if (keys.current["KeyS"] || keys.current["ArrowDown"]) move.z += speed
    if (keys.current["KeyA"] || keys.current["ArrowLeft"]) move.x -= speed
    if (keys.current["KeyD"] || keys.current["ArrowRight"]) move.x += speed

    body.current.setLinvel({ x: move.x, y: vel.y, z: move.z }, true)

    if ((keys.current["Space"] || keys.current["KeyW"]) && Math.abs(vel.y) < 0.1) {
      if (keys.current["Space"]) {
        body.current.applyImpulse({ x: 0, y: jumpForce, z: 0 }, true)
        keys.current["Space"] = false
      }
    }
  })

  return (
    <RigidBody ref={body} position={position} mass={1} lockRotations>
      <mesh castShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial color={color} />
      </mesh>
    </RigidBody>
  )
}
