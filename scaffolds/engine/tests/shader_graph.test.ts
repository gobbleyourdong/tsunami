import { describe, it, expect } from 'vitest'
import {
  UVNode, TimeNode, WorldPosNode, NormalNode, ViewDirNode, ConstantNode,
  AddNode, MultiplyNode, LerpNode, StepNode, SmoothStepNode, RemapNode,
  NoiseNode, FBMNode, GradientNode, FresnelNode,
  compileShaderGraph,
} from '../src/vfx/shader_graph'
import { PRESETS } from '../src/vfx/presets'

describe('Shader Graph Nodes', () => {
  it('UV node compiles', () => {
    const uv = new UVNode()
    const lines = uv.compile()
    expect(lines.length).toBe(1)
    expect(lines[0]).toContain('in.uv')
  })

  it('Time node compiles with sin and fract', () => {
    const time = new TimeNode()
    const lines = time.compile()
    expect(lines.length).toBe(3)
    expect(lines[1]).toContain('sin(globals.time)')
    expect(lines[2]).toContain('fract(globals.time)')
  })

  it('Constant float node', () => {
    const c = new ConstantNode(3.14)
    const lines = c.compile()
    expect(lines[0]).toContain('3.140000')
  })

  it('Constant vec3 node', () => {
    const c = new ConstantNode([1, 0.5, 0])
    const lines = c.compile()
    expect(lines[0]).toContain('vec3f')
  })

  it('Add node connects inputs', () => {
    const a = new ConstantNode(1)
    const b = new ConstantNode(2)
    const add = new AddNode()
    add.connect('a', a).connect('b', b)
    const lines = add.compile()
    expect(lines[0]).toContain(a.varName())
    expect(lines[0]).toContain(b.varName())
    expect(lines[0]).toContain('+')
  })

  it('Multiply node', () => {
    const a = new ConstantNode(3)
    const mul = new MultiplyNode()
    mul.connect('a', a)
    const lines = mul.compile()
    expect(lines[0]).toContain('*')
  })

  it('Lerp node uses mix', () => {
    const lerp = new LerpNode()
    const lines = lerp.compile()
    expect(lines[0]).toContain('mix')
  })

  it('Step node', () => {
    const step = new StepNode()
    const lines = step.compile()
    expect(lines[0]).toContain('step')
  })

  it('SmoothStep node', () => {
    const ss = new SmoothStepNode()
    const lines = ss.compile()
    expect(lines[0]).toContain('smoothstep')
  })

  it('Remap node', () => {
    const remap = new RemapNode()
    const lines = remap.compile()
    expect(lines.length).toBe(1)
  })

  it('Noise nodes compile', () => {
    for (const type of ['perlin', 'simplex', 'voronoi', 'worley'] as const) {
      const noise = new NoiseNode(type)
      const lines = noise.compile()
      expect(lines[0]).toContain(`noise_${type}`)
    }
  })

  it('FBM node generates octave loop', () => {
    const fbm = new FBMNode(4, 'perlin')
    fbm.connect('pos', new UVNode())
    const lines = fbm.compile()
    // Should have: var p, var acc, var amp, then 4 octaves * 3 lines + 1 final let
    expect(lines.length).toBe(3 + 4 * 3 + 1)
  })

  it('Gradient node generates smoothstep chain', () => {
    const grad = new GradientNode([
      [0.0, [1, 0, 0]],
      [0.5, [0, 1, 0]],
      [1.0, [0, 0, 1]],
    ])
    const lines = grad.compile()
    // 1 initial var + 2 mix lines (for stops 1 and 2)
    expect(lines.length).toBe(3)
    expect(lines[1]).toContain('smoothstep')
  })

  it('Fresnel node', () => {
    const fresnel = new FresnelNode()
    const lines = fresnel.compile()
    expect(lines.length).toBe(2)
    expect(lines[1]).toContain('pow')
  })
})

describe('Shader Graph Compiler', () => {
  it('compiles minimal graph', () => {
    const albedo = new ConstantNode([0.8, 0.2, 0.1])
    const wgsl = compileShaderGraph({ albedo })
    expect(wgsl).toContain('fn fs_main')
    expect(wgsl).toContain('vec3f(0.800000')
    expect(wgsl).toContain('noise_perlin') // noise lib always included
  })

  it('compiles graph with connected nodes', () => {
    const uv = new UVNode()
    const noise = new NoiseNode('perlin')
    noise.connect('pos', uv)
    const gradient = new GradientNode([
      [0.0, [1, 0, 0]],
      [1.0, [0, 0, 1]],
    ])
    gradient.connect('t', noise)
    const wgsl = compileShaderGraph({ albedo: gradient })

    // Should contain UV, noise, and gradient code in topological order
    expect(wgsl).toContain('in.uv')
    expect(wgsl).toContain('noise_perlin')
    expect(wgsl).toContain('smoothstep')
  })

  it('topological sort respects dependencies', () => {
    const a = new ConstantNode(1)
    const b = new ConstantNode(2)
    const add = new AddNode()
    add.connect('a', a).connect('b', b)

    const wgsl = compileShaderGraph({ roughness: add })
    // a and b must appear before add in the shader
    const aIdx = wgsl.indexOf(a.varName())
    const bIdx = wgsl.indexOf(b.varName())
    const addIdx = wgsl.indexOf(add.varName())
    expect(aIdx).toBeLessThan(addIdx)
    expect(bIdx).toBeLessThan(addIdx)
  })

  it('includes all output channels', () => {
    const wgsl = compileShaderGraph({
      albedo: new ConstantNode([1, 0, 0]),
      roughness: new ConstantNode(0.5),
      emission: new ConstantNode([0, 1, 0]),
    })
    expect(wgsl).toContain('fn fs_main')
  })
})

describe('Shader Graph Presets', () => {
  it('all presets compile without errors', () => {
    for (const [name, factory] of Object.entries(PRESETS)) {
      const output = factory()
      const wgsl = compileShaderGraph(output)
      expect(wgsl, `Preset '${name}' should compile`).toContain('fn fs_main')
      expect(wgsl.length, `Preset '${name}' should produce non-trivial shader`).toBeGreaterThan(500)
    }
  })

  it('lava preset uses FBM and gradient', () => {
    const output = PRESETS.lava()
    const wgsl = compileShaderGraph(output)
    expect(wgsl).toContain('noise_perlin')
    expect(wgsl).toContain('smoothstep')
  })

  it('water preset uses voronoi', () => {
    const output = PRESETS.water()
    const wgsl = compileShaderGraph(output)
    expect(wgsl).toContain('noise_voronoi')
  })

  it('force field preset has fresnel', () => {
    const output = PRESETS.forceField()
    const wgsl = compileShaderGraph(output)
    expect(wgsl).toContain('pow')
    expect(wgsl).toContain('cameraPos')
  })

  it('dissolve preset has smoothstep threshold', () => {
    const output = PRESETS.dissolve()
    const wgsl = compileShaderGraph(output)
    expect(wgsl).toContain('smoothstep')
    expect(wgsl).toContain('noise_perlin')
  })
})
