import { useRef, useEffect, useState, useMemo } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"
import { useGLTF, useAnimations } from "@react-three/drei"

interface GLTFModelProps {
  url: string
  position?: [number, number, number]
  rotation?: [number, number, number]
  scale?: number | [number, number, number]
  animation?: string
  animationSpeed?: number
  loop?: boolean
  autoPlay?: boolean
  castShadow?: boolean
  receiveShadow?: boolean
  onClick?: () => void
  onLoad?: (animations: string[]) => void
}

export default function GLTFModel({
  url,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  scale = 1,
  animation,
  animationSpeed = 1,
  loop = true,
  autoPlay = true,
  castShadow = true,
  receiveShadow = true,
  onClick,
  onLoad,
}: GLTFModelProps) {
  const groupRef = useRef<THREE.Group>(null)
  const { scene, animations } = useGLTF(url)
  const { actions, names } = useAnimations(animations, groupRef)
  const [currentAnimation, setCurrentAnimation] = useState<string | null>(null)

  // Clone scene to allow multiple instances
  const clonedScene = useMemo(() => scene.clone(true), [scene])

  // Report available animations
  useEffect(() => {
    if (onLoad && names.length > 0) onLoad(names)
  }, [names, onLoad])

  // Setup shadows
  useEffect(() => {
    clonedScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        child.castShadow = castShadow
        child.receiveShadow = receiveShadow
      }
    })
  }, [clonedScene, castShadow, receiveShadow])

  // Animation control
  useEffect(() => {
    const target = animation || (autoPlay && names[0]) || null
    if (!target || !actions[target]) return

    // Stop previous
    if (currentAnimation && actions[currentAnimation]) {
      actions[currentAnimation]?.fadeOut(0.3)
    }

    // Play new
    const action = actions[target]!
    action.reset()
    action.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1)
    action.clampWhenFinished = !loop
    action.timeScale = animationSpeed
    action.fadeIn(0.3).play()
    setCurrentAnimation(target)

    return () => { action.fadeOut(0.3) }
  }, [animation, autoPlay, names, actions, loop, animationSpeed])

  const scaleArr: [number, number, number] = Array.isArray(scale)
    ? scale
    : [scale, scale, scale]

  return (
    <group
      ref={groupRef}
      position={position}
      rotation={rotation}
      scale={scaleArr}
      onClick={onClick}
    >
      <primitive object={clonedScene} />
    </group>
  )
}

// Re-export useGLTF preload for caching
export const preloadModel = useGLTF.preload

export type { GLTFModelProps }
