import { Canvas } from "@react-three/fiber"
import { OrbitControls, Environment, Grid } from "@react-three/drei"
import { Physics } from "@react-three/rapier"
import { Suspense, ReactNode } from "react"

interface SceneProps {
  children: ReactNode
  bgColor?: string
  gravity?: [number, number, number]
  debug?: boolean
  camera?: { position: [number, number, number]; fov?: number }
}

/** Ready-to-use 3D scene with camera, lighting, physics, and controls.
 *  Just drop game objects as children. */
export default function Scene({
  children,
  bgColor = "#1a1a2e",
  gravity = [0, -9.81, 0],
  debug = false,
  camera = { position: [0, 8, 12], fov: 50 },
}: SceneProps) {
  return (
    <Canvas camera={camera} shadows style={{ background: bgColor }}>
      <Suspense fallback={null}>
        <Lighting />
        <Physics gravity={gravity} debug={debug}>
          {children}
        </Physics>
        <OrbitControls makeDefault />
        {debug && <Grid infiniteGrid fadeDistance={50} />}
      </Suspense>
    </Canvas>
  )
}

function Lighting() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight
        position={[10, 15, 10]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      <pointLight position={[-5, 8, -5]} intensity={0.6} color="#4488ff" />
    </>
  )
}
