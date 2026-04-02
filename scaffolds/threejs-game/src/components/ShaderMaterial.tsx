import { useRef, useMemo } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

interface ShaderMaterialProps {
  vertexShader?: string
  fragmentShader?: string
  uniforms?: Record<string, { value: any }>
  transparent?: boolean
}

/** Custom shader material — pass GLSL vertex/fragment shaders.
 *  Uniforms auto-update with time. */
export function CustomShaderMaterial({
  vertexShader = DEFAULT_VERT,
  fragmentShader = DEFAULT_FRAG,
  uniforms = {},
  transparent = false,
}: ShaderMaterialProps) {
  const ref = useRef<THREE.ShaderMaterial>(null)

  const mergedUniforms = useMemo(() => ({
    uTime: { value: 0 },
    uResolution: { value: new THREE.Vector2(1, 1) },
    ...uniforms,
  }), [])

  useFrame(({ clock }) => {
    if (ref.current) ref.current.uniforms.uTime.value = clock.getElapsedTime()
  })

  return <shaderMaterial ref={ref} vertexShader={vertexShader} fragmentShader={fragmentShader} uniforms={mergedUniforms} transparent={transparent} />
}

// Default shaders — iridescent glow
const DEFAULT_VERT = `
varying vec2 vUv;
varying vec3 vPosition;
void main() {
  vUv = uv;
  vPosition = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const DEFAULT_FRAG = `
uniform float uTime;
varying vec2 vUv;
varying vec3 vPosition;
void main() {
  vec3 color = 0.5 + 0.5 * cos(uTime + vUv.xyx * 3.0 + vec3(0, 2, 4));
  gl_FragColor = vec4(color, 1.0);
}
`

/** Neon glow shader — pulsing with time */
export const NEON_FRAG = `
uniform float uTime;
varying vec2 vUv;
void main() {
  float glow = sin(uTime * 2.0 + vUv.x * 10.0) * 0.5 + 0.5;
  vec3 color = mix(vec3(0.0, 0.8, 0.8), vec3(0.8, 0.0, 0.8), vUv.y);
  gl_FragColor = vec4(color * (0.5 + glow * 0.5), 1.0);
}
`

/** Noise/smoke shader */
export const NOISE_FRAG = `
uniform float uTime;
varying vec2 vUv;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1, 0)), f.x),
    mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x),
    f.y
  );
}

void main() {
  float n = noise(vUv * 5.0 + uTime * 0.3);
  n += noise(vUv * 10.0 - uTime * 0.2) * 0.5;
  vec3 color = mix(vec3(0.05, 0.05, 0.1), vec3(0.1, 0.3, 0.4), n);
  gl_FragColor = vec4(color, n * 0.8);
}
`

/** Water/ocean shader */
export const WATER_FRAG = `
uniform float uTime;
varying vec2 vUv;

void main() {
  vec2 uv = vUv * 8.0;
  float wave1 = sin(uv.x + uTime) * cos(uv.y + uTime * 0.7) * 0.5 + 0.5;
  float wave2 = sin(uv.x * 1.3 - uTime * 0.8) * cos(uv.y * 0.9 + uTime) * 0.5 + 0.5;
  float wave = (wave1 + wave2) * 0.5;
  vec3 deep = vec3(0.0, 0.1, 0.3);
  vec3 surface = vec3(0.1, 0.4, 0.6);
  vec3 foam = vec3(0.8, 0.9, 1.0);
  vec3 color = mix(deep, surface, wave);
  color = mix(color, foam, smoothstep(0.7, 0.9, wave));
  gl_FragColor = vec4(color, 0.9);
}
`
