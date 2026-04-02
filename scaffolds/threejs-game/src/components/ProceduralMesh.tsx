import { useMemo, useRef } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

/** Procedural terrain — generates height map from noise */
export function ProceduralTerrain({
  size = 20,
  segments = 64,
  height = 3,
  color = "#2a4a2a",
  wireframe = false,
}: {
  size?: number
  segments?: number
  height?: number
  color?: string
  wireframe?: boolean
}) {
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(size, size, segments, segments)
    const pos = g.attributes.position
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i) / size
      const y = pos.getY(i) / size
      const h = Math.sin(x * 10) * Math.cos(y * 10) * 0.3
        + Math.sin(x * 20 + 1) * Math.cos(y * 15 + 2) * 0.15
        + Math.sin(x * 40) * Math.cos(y * 35) * 0.05
      pos.setZ(i, h * height)
    }
    g.computeVertexNormals()
    return g
  }, [size, segments, height])

  return (
    <mesh geometry={geo} rotation-x={-Math.PI / 2} receiveShadow>
      <meshStandardMaterial color={color} wireframe={wireframe} side={THREE.DoubleSide} />
    </mesh>
  )
}

/** Procedural sphere with displaced vertices */
export function ProceduralPlanet({
  radius = 2,
  detail = 32,
  displacement = 0.3,
  color = "#4488aa",
  animate = true,
}: {
  radius?: number
  detail?: number
  displacement?: number
  color?: string
  animate?: boolean
}) {
  const ref = useRef<THREE.Mesh>(null)

  const geo = useMemo(() => {
    const g = new THREE.IcosahedronGeometry(radius, detail)
    const pos = g.attributes.position
    for (let i = 0; i < pos.count; i++) {
      const v = new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i))
      const n = v.clone().normalize()
      const noise = Math.sin(v.x * 5) * Math.cos(v.y * 5) * Math.sin(v.z * 5)
      v.add(n.multiplyScalar(noise * displacement))
      pos.setXYZ(i, v.x, v.y, v.z)
    }
    g.computeVertexNormals()
    return g
  }, [radius, detail, displacement])

  useFrame((_, dt) => {
    if (ref.current && animate) ref.current.rotation.y += dt * 0.2
  })

  return (
    <mesh ref={ref} geometry={geo} castShadow>
      <meshStandardMaterial color={color} flatShading />
    </mesh>
  )
}
