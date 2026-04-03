import { useRef, useMemo } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

interface CustomShaderProps {
  vertexShader?: string
  fragmentShader?: string
  uniforms?: Record<string, { value: any }>
  transparent?: boolean
  side?: "front" | "back" | "double"
  children?: React.ReactNode
}

// === Built-in shaders ===

export const VOLUMETRIC_FOG_FRAG = `
uniform float uTime;
uniform float uDensity;
uniform vec3 uColor;
varying vec3 vWorldPosition;
varying vec3 vNormal;

void main() {
  float depth = length(vWorldPosition - cameraPosition);
  float fog = 1.0 - exp(-uDensity * depth * depth);

  // Noise-based variation
  float noise = fract(sin(dot(vWorldPosition.xz * 0.1, vec2(12.9898, 78.233))) * 43758.5453);
  fog *= 0.7 + 0.3 * noise;

  // Light scattering approximation
  vec3 lightDir = normalize(vec3(1.0, 0.5, 0.3));
  float scatter = max(0.0, dot(normalize(vWorldPosition - cameraPosition), lightDir));
  scatter = pow(scatter, 4.0);

  vec3 color = mix(uColor, vec3(1.0, 0.9, 0.7), scatter * 0.3);
  gl_FragColor = vec4(color, fog * 0.6);
}
`

export const OCEAN_FRAG = `
uniform float uTime;
uniform vec3 uDeepColor;
uniform vec3 uShallowColor;
uniform float uFoamThreshold;
varying vec2 vUv;
varying vec3 vWorldPosition;
varying float vElevation;

void main() {
  // Wave-based color mixing
  float depth = smoothstep(-0.5, 0.5, vElevation);
  vec3 color = mix(uDeepColor, uShallowColor, depth);

  // Foam on wave peaks
  float foam = smoothstep(uFoamThreshold, uFoamThreshold + 0.05, vElevation);
  color = mix(color, vec3(1.0), foam * 0.8);

  // Fresnel edge highlight
  vec3 viewDir = normalize(cameraPosition - vWorldPosition);
  vec3 normal = normalize(cross(dFdx(vWorldPosition), dFdy(vWorldPosition)));
  float fresnel = pow(1.0 - max(0.0, dot(viewDir, normal)), 3.0);
  color += vec3(0.1, 0.2, 0.3) * fresnel;

  gl_FragColor = vec4(color, 0.9);
}
`

export const OCEAN_VERT = `
uniform float uTime;
uniform float uWaveHeight;
uniform float uWaveFrequency;
varying vec2 vUv;
varying vec3 vWorldPosition;
varying float vElevation;

void main() {
  vUv = uv;
  vec3 pos = position;

  // Multi-octave waves (FFT approximation)
  float wave1 = sin(pos.x * uWaveFrequency + uTime * 1.5) * cos(pos.z * uWaveFrequency * 0.7 + uTime);
  float wave2 = sin(pos.x * uWaveFrequency * 2.3 + uTime * 2.0) * 0.5;
  float wave3 = cos(pos.z * uWaveFrequency * 1.8 + uTime * 0.8) * 0.3;

  pos.y += (wave1 + wave2 + wave3) * uWaveHeight;
  vElevation = pos.y;

  vec4 worldPos = modelMatrix * vec4(pos, 1.0);
  vWorldPosition = worldPos.xyz;

  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`

const DEFAULT_VERT = `
varying vec3 vWorldPosition;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vUv = uv;
  vNormal = normalize(normalMatrix * normal);
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPosition = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`

const DEFAULT_FRAG = `
varying vec3 vWorldPosition;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec3 lightDir = normalize(vec3(1.0, 1.0, 0.5));
  float diff = max(dot(vNormal, lightDir), 0.2);
  gl_FragColor = vec4(vec3(diff), 1.0);
}
`

export default function CustomShader({
  vertexShader = DEFAULT_VERT,
  fragmentShader = DEFAULT_FRAG,
  uniforms: userUniforms = {},
  transparent = false,
  side = "front",
  children,
}: CustomShaderProps) {
  const materialRef = useRef<THREE.ShaderMaterial>(null)

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    ...userUniforms,
  }), [])

  const sideMap = { front: THREE.FrontSide, back: THREE.BackSide, double: THREE.DoubleSide }

  useFrame((_, delta) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value += delta
    }
  })

  return (
    <shaderMaterial
      ref={materialRef}
      vertexShader={vertexShader}
      fragmentShader={fragmentShader}
      uniforms={uniforms}
      transparent={transparent}
      side={sideMap[side]}
    />
  )
}

export type { CustomShaderProps }
