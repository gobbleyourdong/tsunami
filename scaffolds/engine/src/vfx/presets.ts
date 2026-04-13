/**
 * Shader graph presets — common materials built from nodes.
 * Each returns a MaterialOutput that can be compiled to WGSL.
 */

import {
  UVNode, TimeNode, WorldPosNode, ConstantNode,
  NoiseNode, FBMNode, GradientNode, FresnelNode,
  AddNode, MultiplyNode, RemapNode, SmoothStepNode,
  MaterialOutput,
} from './shader_graph'

export function lavaPreset(): MaterialOutput {
  const uv = new UVNode()
  const time = new TimeNode()
  const scale = new ConstantNode(3)
  const scrollSpeed = new ConstantNode(0.2)

  const scroll = new MultiplyNode()
  scroll.connect('a', time).connect('b', scrollSpeed)

  const offset = new AddNode()
  offset.connect('a', new FBMNode(4, 'perlin')).connect('b', scroll)
  // Connect FBM to UV
  const fbm = offset.inputs.get('a')!.node as FBMNode
  fbm.connect('pos', uv).connect('scale', scale)

  const gradient = new GradientNode([
    [0.0, [0.1, 0.0, 0.0]],
    [0.4, [1.0, 0.27, 0.0]],
    [1.0, [1.0, 0.8, 0.0]],
  ])
  gradient.connect('t', fbm)

  const emissionMul = new MultiplyNode()
  emissionMul.connect('a', new ConstantNode(2)).connect('b', fbm)

  return {
    albedo: gradient,
    emission: gradient,
    roughness: new ConstantNode(0.8),
    metallic: new ConstantNode(0.0),
  }
}

export function waterPreset(): MaterialOutput {
  const uv = new UVNode()
  const time = new TimeNode()

  const noise1 = new NoiseNode('voronoi')
  noise1.connect('pos', uv).connect('scale', new ConstantNode(8))

  const noise2 = new NoiseNode('perlin')
  noise2.connect('pos', uv).connect('scale', new ConstantNode(12))

  const combined = new AddNode()
  combined.connect('a', noise1).connect('b', noise2)

  const waterColor = new GradientNode([
    [0.0, [0.0, 0.15, 0.3]],
    [0.5, [0.0, 0.3, 0.5]],
    [1.0, [0.2, 0.6, 0.8]],
  ])
  waterColor.connect('t', combined)

  const fresnel = new FresnelNode()

  return {
    albedo: waterColor,
    roughness: new ConstantNode(0.1),
    metallic: new ConstantNode(0.0),
    alpha: fresnel,
  }
}

export function forceFieldPreset(): MaterialOutput {
  const uv = new UVNode()
  const time = new TimeNode()

  const noise = new NoiseNode('simplex')
  noise.connect('pos', uv).connect('scale', new ConstantNode(6))

  const fresnel = new FresnelNode()

  const glow = new GradientNode([
    [0.0, [0.0, 0.2, 1.0]],
    [0.5, [0.0, 0.5, 1.0]],
    [1.0, [0.5, 0.8, 1.0]],
  ])
  glow.connect('t', fresnel)

  return {
    albedo: new ConstantNode([0, 0, 0]),
    emission: glow,
    alpha: fresnel,
    roughness: new ConstantNode(0.0),
    metallic: new ConstantNode(1.0),
  }
}

export function hologramPreset(): MaterialOutput {
  const uv = new UVNode()
  const time = new TimeNode()

  const scanlines = new NoiseNode('perlin')
  scanlines.connect('pos', uv).connect('scale', new ConstantNode(50))

  const fresnel = new FresnelNode()

  const color = new GradientNode([
    [0.0, [0.0, 0.8, 1.0]],
    [1.0, [0.0, 0.3, 0.6]],
  ])
  color.connect('t', fresnel)

  return {
    albedo: new ConstantNode([0, 0, 0]),
    emission: color,
    alpha: fresnel,
    roughness: new ConstantNode(0.0),
    metallic: new ConstantNode(0.5),
  }
}

export function dissolvePreset(): MaterialOutput {
  const uv = new UVNode()
  const time = new TimeNode()

  const noise = new FBMNode(3, 'perlin')
  noise.connect('pos', uv).connect('scale', new ConstantNode(5))

  const threshold = new SmoothStepNode()
  threshold.connect('lo', time).connect('x', noise)
  // hi = time + 0.05 (edge width)
  const edgeWidth = new AddNode()
  edgeWidth.connect('a', time).connect('b', new ConstantNode(0.05))
  threshold.connect('hi', edgeWidth)

  const edgeColor = new GradientNode([
    [0.0, [1.0, 0.5, 0.0]],
    [1.0, [1.0, 0.0, 0.0]],
  ])
  edgeColor.connect('t', noise)

  return {
    albedo: new ConstantNode([0.8, 0.8, 0.8]),
    emission: edgeColor,
    alpha: threshold,
  }
}

export const PRESETS = {
  lava: lavaPreset,
  water: waterPreset,
  forceField: forceFieldPreset,
  hologram: hologramPreset,
  dissolve: dissolvePreset,
} as const
