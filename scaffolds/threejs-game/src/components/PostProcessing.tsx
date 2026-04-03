import { useRef, useMemo, useEffect } from "react"
import { useThree, useFrame, extend } from "@react-three/fiber"
import { EffectComposer, Bloom, DepthOfField, SSAO, Vignette, ChromaticAberration } from "@react-three/postprocessing"
import * as THREE from "three"

interface PostProcessingProps {
  bloom?: boolean | { intensity?: number; luminanceThreshold?: number; radius?: number }
  dof?: boolean | { focusDistance?: number; focalLength?: number; bokehScale?: number }
  ssao?: boolean | { radius?: number; intensity?: number }
  vignette?: boolean | { offset?: number; darkness?: number }
  chromaticAberration?: boolean | { offset?: [number, number] }
}

export default function PostProcessing({
  bloom = false,
  dof = false,
  ssao = false,
  vignette = false,
  chromaticAberration = false,
}: PostProcessingProps) {
  const bloomOpts = typeof bloom === "object" ? bloom : {}
  const dofOpts = typeof dof === "object" ? dof : {}
  const ssaoOpts = typeof ssao === "object" ? ssao : {}
  const vignetteOpts = typeof vignette === "object" ? vignette : {}
  const caOpts = typeof chromaticAberration === "object" ? chromaticAberration : {}

  return (
    <EffectComposer>
      {bloom && (
        <Bloom
          intensity={bloomOpts.intensity ?? 1}
          luminanceThreshold={bloomOpts.luminanceThreshold ?? 0.9}
          radius={bloomOpts.radius ?? 0.4}
        />
      )}
      {dof && (
        <DepthOfField
          focusDistance={dofOpts.focusDistance ?? 0.01}
          focalLength={dofOpts.focalLength ?? 0.02}
          bokehScale={dofOpts.bokehScale ?? 2}
        />
      )}
      {vignette && (
        <Vignette
          offset={vignetteOpts.offset ?? 0.3}
          darkness={vignetteOpts.darkness ?? 0.7}
        />
      )}
    </EffectComposer>
  )
}

export type { PostProcessingProps }
