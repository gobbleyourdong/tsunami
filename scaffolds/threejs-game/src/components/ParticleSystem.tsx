import { useRef, useMemo, useEffect } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

interface ParticleConfig {
  count?: number
  size?: number
  color?: string | string[]
  lifetime?: number
  speed?: number
  spread?: number
  gravity?: number
  opacity?: number
  fadeOut?: boolean
}

interface ParticleSystemProps {
  position?: [number, number, number]
  config?: ParticleConfig
  preset?: "fire" | "smoke" | "rain" | "snow" | "sparks" | "confetti"
  emitting?: boolean
}

const PRESETS: Record<string, ParticleConfig> = {
  fire: { count: 200, size: 0.15, color: ["#ff4400", "#ff8800", "#ffcc00"], lifetime: 1.5, speed: 2, spread: 0.3, gravity: -1, fadeOut: true },
  smoke: { count: 100, size: 0.4, color: "#666666", lifetime: 3, speed: 0.5, spread: 0.5, gravity: -0.3, opacity: 0.4, fadeOut: true },
  rain: { count: 500, size: 0.02, color: "#88bbff", lifetime: 2, speed: 8, spread: 5, gravity: 10, fadeOut: false },
  snow: { count: 300, size: 0.05, color: "#ffffff", lifetime: 5, speed: 0.5, spread: 4, gravity: 0.5, fadeOut: false },
  sparks: { count: 100, size: 0.08, color: ["#ffaa00", "#ffdd44", "#ffffff"], lifetime: 0.8, speed: 5, spread: 1, gravity: 3, fadeOut: true },
  confetti: { count: 200, size: 0.12, color: ["#ff0066", "#00ccff", "#ffcc00", "#00ff88", "#aa44ff"], lifetime: 3, speed: 3, spread: 2, gravity: 1, fadeOut: false },
}

export default function ParticleSystem({
  position = [0, 0, 0],
  config: userConfig,
  preset,
  emitting = true,
}: ParticleSystemProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const cfg = useMemo(() => ({
    count: 200, size: 0.1, color: "#ffffff", lifetime: 2, speed: 1,
    spread: 1, gravity: 0, opacity: 1, fadeOut: true,
    ...(preset ? PRESETS[preset] : {}),
    ...userConfig,
  }), [preset, userConfig])

  const { count } = cfg
  const dummy = useMemo(() => new THREE.Object3D(), [])

  // Per-particle state
  const state = useMemo(() => ({
    velocities: new Float32Array(count * 3),
    lifetimes: new Float32Array(count),
    maxLifetimes: new Float32Array(count),
    colors: new Float32Array(count * 3),
  }), [count])

  // Initialize particles
  useEffect(() => {
    const colorArr = Array.isArray(cfg.color) ? cfg.color : [cfg.color]
    for (let i = 0; i < count; i++) {
      resetParticle(i)
      // Stagger initial lifetimes so they don't all spawn at once
      state.lifetimes[i] = Math.random() * cfg.lifetime
      // Assign color
      const c = new THREE.Color(colorArr[i % colorArr.length])
      state.colors[i * 3] = c.r
      state.colors[i * 3 + 1] = c.g
      state.colors[i * 3 + 2] = c.b
    }
  }, [count, cfg])

  function resetParticle(i: number) {
    const { speed, spread, lifetime } = cfg
    state.velocities[i * 3] = (Math.random() - 0.5) * spread * speed
    state.velocities[i * 3 + 1] = Math.random() * speed
    state.velocities[i * 3 + 2] = (Math.random() - 0.5) * spread * speed

    // Rain falls down
    if (preset === "rain") {
      state.velocities[i * 3 + 1] = -speed
    }
    // Snow drifts
    if (preset === "snow") {
      state.velocities[i * 3 + 1] = -speed * 0.5
    }

    state.lifetimes[i] = 0
    state.maxLifetimes[i] = lifetime * (0.5 + Math.random() * 0.5)
  }

  useFrame((_, delta) => {
    if (!meshRef.current) return
    const mesh = meshRef.current

    for (let i = 0; i < count; i++) {
      state.lifetimes[i] += delta

      if (state.lifetimes[i] > state.maxLifetimes[i]) {
        if (emitting) resetParticle(i)
        else { state.lifetimes[i] = state.maxLifetimes[i] + 1 }
      }

      const t = state.lifetimes[i] / state.maxLifetimes[i]
      const alive = t <= 1

      // Physics
      state.velocities[i * 3 + 1] -= cfg.gravity * delta

      const px = state.velocities[i * 3] * state.lifetimes[i]
      const py = state.velocities[i * 3 + 1] * state.lifetimes[i]
      const pz = state.velocities[i * 3 + 2] * state.lifetimes[i]

      dummy.position.set(
        position[0] + px,
        position[1] + py,
        position[2] + pz,
      )

      const scale = alive ? (cfg.fadeOut ? cfg.size * (1 - t) : cfg.size) : 0
      dummy.scale.setScalar(scale)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)

      // Color with fade
      const color = new THREE.Color(
        state.colors[i * 3],
        state.colors[i * 3 + 1],
        state.colors[i * 3 + 2],
      )
      if (cfg.fadeOut && alive) color.multiplyScalar(1 - t * 0.5)
      mesh.setColorAt(i, color)
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial transparent opacity={cfg.opacity} />
    </instancedMesh>
  )
}

export { PRESETS as PARTICLE_PRESETS }
export type { ParticleConfig, ParticleSystemProps }
