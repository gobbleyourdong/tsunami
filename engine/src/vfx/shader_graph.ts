/**
 * Shader graph — node-based procedural material system.
 * Compiles a DAG of shader nodes into a single WGSL fragment shader.
 * Each node has typed inputs/outputs and a compile() method that emits WGSL.
 */

export type ValueType = 'float' | 'vec2f' | 'vec3f' | 'vec4f'

export interface ShaderPort {
  name: string
  type: ValueType
  node?: ShaderNode
  portName?: string  // which output port to read from
  defaultValue?: string  // WGSL literal fallback
}

let nodeCounter = 0

export abstract class ShaderNode {
  readonly id: number
  readonly name: string
  inputs: Map<string, ShaderPort> = new Map()
  outputs: Map<string, ValueType> = new Map()

  constructor(name: string) {
    this.id = nodeCounter++
    this.name = name
  }

  /** Connect an input to another node's output. */
  connect(inputName: string, source: ShaderNode, outputName = 'out'): this {
    const port = this.inputs.get(inputName)
    if (!port) throw new Error(`No input '${inputName}' on node '${this.name}'`)
    port.node = source
    port.portName = outputName
    return this
  }

  /** Get the WGSL variable name for an output. */
  varName(output = 'out'): string {
    return `n${this.id}_${output}`
  }

  /** Resolve an input to its WGSL expression. */
  resolveInput(name: string): string {
    const port = this.inputs.get(name)
    if (!port) return '0.0'
    if (port.node) return port.node.varName(port.portName ?? 'out')
    return port.defaultValue ?? '0.0'
  }

  /** Emit WGSL code for this node. Returns lines of WGSL. */
  abstract compile(): string[]
}

// --- Input nodes ---

export class UVNode extends ShaderNode {
  constructor() {
    super('UV')
    this.outputs.set('out', 'vec2f')
  }
  compile(): string[] {
    return [`let ${this.varName()} = in.uv;`]
  }
}

export class TimeNode extends ShaderNode {
  constructor() {
    super('Time')
    this.outputs.set('out', 'float')
    this.outputs.set('sin', 'float')
    this.outputs.set('fract', 'float')
  }
  compile(): string[] {
    return [
      `let ${this.varName()} = globals.time;`,
      `let ${this.varName('sin')} = sin(globals.time);`,
      `let ${this.varName('fract')} = fract(globals.time);`,
    ]
  }
}

export class WorldPosNode extends ShaderNode {
  constructor() {
    super('WorldPos')
    this.outputs.set('out', 'vec3f')
  }
  compile(): string[] {
    return [`let ${this.varName()} = in.worldPos;`]
  }
}

export class NormalNode extends ShaderNode {
  constructor() {
    super('Normal')
    this.outputs.set('out', 'vec3f')
  }
  compile(): string[] {
    return [`let ${this.varName()} = in.normal;`]
  }
}

export class ViewDirNode extends ShaderNode {
  constructor() {
    super('ViewDir')
    this.outputs.set('out', 'vec3f')
  }
  compile(): string[] {
    return [`let ${this.varName()} = normalize(globals.cameraPos - in.worldPos);`]
  }
}

export class ConstantNode extends ShaderNode {
  constructor(public value: number | number[]) {
    super('Constant')
    if (typeof value === 'number') {
      this.outputs.set('out', 'float')
    } else if (value.length === 2) {
      this.outputs.set('out', 'vec2f')
    } else if (value.length === 3) {
      this.outputs.set('out', 'vec3f')
    } else {
      this.outputs.set('out', 'vec4f')
    }
  }
  compile(): string[] {
    const v = this.value
    if (typeof v === 'number') return [`let ${this.varName()} = ${v.toFixed(6)};`]
    if (v.length === 2) return [`let ${this.varName()} = vec2f(${v.map(n => n.toFixed(6)).join(', ')});`]
    if (v.length === 3) return [`let ${this.varName()} = vec3f(${v.map(n => n.toFixed(6)).join(', ')});`]
    return [`let ${this.varName()} = vec4f(${v.map(n => n.toFixed(6)).join(', ')});`]
  }
}

// --- Math nodes ---

export class AddNode extends ShaderNode {
  constructor() {
    super('Add')
    this.inputs.set('a', { name: 'a', type: 'float', defaultValue: '0.0' })
    this.inputs.set('b', { name: 'b', type: 'float', defaultValue: '0.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    return [`let ${this.varName()} = ${this.resolveInput('a')} + ${this.resolveInput('b')};`]
  }
}

export class MultiplyNode extends ShaderNode {
  constructor() {
    super('Multiply')
    this.inputs.set('a', { name: 'a', type: 'float', defaultValue: '1.0' })
    this.inputs.set('b', { name: 'b', type: 'float', defaultValue: '1.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    return [`let ${this.varName()} = ${this.resolveInput('a')} * ${this.resolveInput('b')};`]
  }
}

export class LerpNode extends ShaderNode {
  constructor() {
    super('Lerp')
    this.inputs.set('a', { name: 'a', type: 'vec3f', defaultValue: 'vec3f(0.0)' })
    this.inputs.set('b', { name: 'b', type: 'vec3f', defaultValue: 'vec3f(1.0)' })
    this.inputs.set('t', { name: 't', type: 'float', defaultValue: '0.5' })
    this.outputs.set('out', 'vec3f')
  }
  compile(): string[] {
    return [`let ${this.varName()} = mix(${this.resolveInput('a')}, ${this.resolveInput('b')}, ${this.resolveInput('t')});`]
  }
}

export class StepNode extends ShaderNode {
  constructor() {
    super('Step')
    this.inputs.set('edge', { name: 'edge', type: 'float', defaultValue: '0.5' })
    this.inputs.set('x', { name: 'x', type: 'float', defaultValue: '0.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    return [`let ${this.varName()} = step(${this.resolveInput('edge')}, ${this.resolveInput('x')});`]
  }
}

export class SmoothStepNode extends ShaderNode {
  constructor() {
    super('SmoothStep')
    this.inputs.set('lo', { name: 'lo', type: 'float', defaultValue: '0.0' })
    this.inputs.set('hi', { name: 'hi', type: 'float', defaultValue: '1.0' })
    this.inputs.set('x', { name: 'x', type: 'float', defaultValue: '0.5' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    return [`let ${this.varName()} = smoothstep(${this.resolveInput('lo')}, ${this.resolveInput('hi')}, ${this.resolveInput('x')});`]
  }
}

export class RemapNode extends ShaderNode {
  constructor() {
    super('Remap')
    this.inputs.set('value', { name: 'value', type: 'float', defaultValue: '0.0' })
    this.inputs.set('inMin', { name: 'inMin', type: 'float', defaultValue: '0.0' })
    this.inputs.set('inMax', { name: 'inMax', type: 'float', defaultValue: '1.0' })
    this.inputs.set('outMin', { name: 'outMin', type: 'float', defaultValue: '0.0' })
    this.inputs.set('outMax', { name: 'outMax', type: 'float', defaultValue: '1.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    const v = this.resolveInput('value')
    const iMin = this.resolveInput('inMin')
    const iMax = this.resolveInput('inMax')
    const oMin = this.resolveInput('outMin')
    const oMax = this.resolveInput('outMax')
    return [`let ${this.varName()} = ${oMin} + (${v} - ${iMin}) / (${iMax} - ${iMin}) * (${oMax} - ${oMin});`]
  }
}

// --- Noise nodes ---

export class NoiseNode extends ShaderNode {
  constructor(public noiseType: 'perlin' | 'simplex' | 'voronoi' | 'worley' = 'perlin') {
    super(`Noise_${noiseType}`)
    this.inputs.set('pos', { name: 'pos', type: 'vec2f', defaultValue: 'in.uv' })
    this.inputs.set('scale', { name: 'scale', type: 'float', defaultValue: '4.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    const p = this.resolveInput('pos')
    const s = this.resolveInput('scale')
    const fn = `noise_${this.noiseType}`
    return [`let ${this.varName()} = ${fn}(${p} * ${s});`]
  }
}

export class FBMNode extends ShaderNode {
  constructor(public octaves = 4, public noiseType: 'perlin' | 'simplex' = 'perlin') {
    super('FBM')
    this.inputs.set('pos', { name: 'pos', type: 'vec2f', defaultValue: 'in.uv' })
    this.inputs.set('scale', { name: 'scale', type: 'float', defaultValue: '4.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    const p = this.resolveInput('pos')
    const s = this.resolveInput('scale')
    const fn = `noise_${this.noiseType}`
    const varP = `${this.varName()}_p`
    const lines = [
      `var ${varP} = ${p} * ${s};`,
      `var ${this.varName()}_acc = 0.0;`,
      `var ${this.varName()}_amp = 0.5;`,
    ]
    for (let i = 0; i < this.octaves; i++) {
      lines.push(`${this.varName()}_acc += ${fn}(${varP}) * ${this.varName()}_amp;`)
      lines.push(`${varP} *= 2.0;`)
      lines.push(`${this.varName()}_amp *= 0.5;`)
    }
    lines.push(`let ${this.varName()} = ${this.varName()}_acc;`)
    return lines
  }
}

// --- Color nodes ---

export class GradientNode extends ShaderNode {
  /** Gradient with N color stops: [[position, [r,g,b]], ...] sorted by position */
  constructor(public stops: [number, [number, number, number]][]) {
    super('Gradient')
    this.inputs.set('t', { name: 't', type: 'float', defaultValue: '0.5' })
    this.outputs.set('out', 'vec3f')
  }
  compile(): string[] {
    if (this.stops.length === 0) return [`let ${this.varName()} = vec3f(0.0);`]
    if (this.stops.length === 1) {
      const [, c] = this.stops[0]
      return [`let ${this.varName()} = vec3f(${c[0].toFixed(4)}, ${c[1].toFixed(4)}, ${c[2].toFixed(4)});`]
    }
    const t = this.resolveInput('t')
    const lines: string[] = []
    const first = this.stops[0]
    lines.push(`var ${this.varName()} = vec3f(${first[1][0].toFixed(4)}, ${first[1][1].toFixed(4)}, ${first[1][2].toFixed(4)});`)
    for (let i = 1; i < this.stops.length; i++) {
      const prev = this.stops[i - 1]
      const curr = this.stops[i]
      const lo = prev[0].toFixed(4)
      const hi = curr[0].toFixed(4)
      const c = curr[1]
      lines.push(`${this.varName()} = mix(${this.varName()}, vec3f(${c[0].toFixed(4)}, ${c[1].toFixed(4)}, ${c[2].toFixed(4)}), smoothstep(${lo}, ${hi}, ${t}));`)
    }
    return lines
  }
}

export class FresnelNode extends ShaderNode {
  constructor() {
    super('Fresnel')
    this.inputs.set('power', { name: 'power', type: 'float', defaultValue: '5.0' })
    this.outputs.set('out', 'float')
  }
  compile(): string[] {
    const power = this.resolveInput('power')
    return [
      `let ${this.varName()}_vd = normalize(globals.cameraPos - in.worldPos);`,
      `let ${this.varName()} = pow(1.0 - max(dot(in.normal, ${this.varName()}_vd), 0.0), ${power});`,
    ]
  }
}

// --- Output node ---

export interface MaterialOutput {
  albedo?: ShaderNode
  normal?: ShaderNode
  roughness?: ShaderNode
  metallic?: ShaderNode
  emission?: ShaderNode
  alpha?: ShaderNode
  vertexOffset?: ShaderNode
}

/**
 * Compile a shader graph into a complete WGSL shader.
 * Topological sort → inline node outputs → emit final shader.
 */
export function compileShaderGraph(output: MaterialOutput): string {
  // Collect all nodes reachable from outputs
  const visited = new Set<number>()
  const sorted: ShaderNode[] = []

  function visit(node: ShaderNode | undefined) {
    if (!node || visited.has(node.id)) return
    visited.add(node.id)
    for (const [, port] of node.inputs) {
      if (port.node) visit(port.node)
    }
    sorted.push(node)
  }

  visit(output.albedo)
  visit(output.normal)
  visit(output.roughness)
  visit(output.metallic)
  visit(output.emission)
  visit(output.alpha)
  visit(output.vertexOffset)

  // Emit node code
  const nodeCode = sorted.flatMap((n) => n.compile())

  // Final outputs
  const albedo = output.albedo ? output.albedo.varName() : 'vec3f(0.8)'
  const roughness = output.roughness ? output.roughness.varName() : '0.5'
  const metallic = output.metallic ? output.metallic.varName() : '0.0'
  const emission = output.emission ? output.emission.varName() : 'vec3f(0.0)'
  const alpha = output.alpha ? output.alpha.varName() : '1.0'

  return `
// Auto-generated by Tsunami Shader Graph
struct Globals {
  time: f32,
  cameraPos: vec3f,
};

@group(0) @binding(0) var<uniform> globals: Globals;

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) worldPos: vec3f,
  @location(1) normal: vec3f,
  @location(2) uv: vec2f,
};

${NOISE_LIBRARY}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4f {
${nodeCode.map(l => '  ' + l).join('\n')}

  let lightDir = normalize(vec3f(1.0, 2.0, 1.5));
  let ambient = vec3f(0.12);
  let diffuse = max(dot(in.normal, lightDir), 0.0);
  let lit = ${albedo} * (ambient + vec3f(0.88) * diffuse) + ${emission};
  return vec4f(lit, ${alpha});
}
`.trim()
}

// WGSL noise functions embedded in every shader graph output
const NOISE_LIBRARY = `
// --- Noise Library ---
fn hash2(p: vec2f) -> f32 {
  var p3 = fract(vec3f(p.x, p.y, p.x) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

fn hash2v(p: vec2f) -> vec2f {
  let k = vec2f(dot(p, vec2f(127.1, 311.7)), dot(p, vec2f(269.5, 183.3)));
  return fract(sin(k) * 43758.5453) * 2.0 - 1.0;
}

fn noise_perlin(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  let a = dot(hash2v(i + vec2f(0.0, 0.0)), f - vec2f(0.0, 0.0));
  let b = dot(hash2v(i + vec2f(1.0, 0.0)), f - vec2f(1.0, 0.0));
  let c = dot(hash2v(i + vec2f(0.0, 1.0)), f - vec2f(0.0, 1.0));
  let d = dot(hash2v(i + vec2f(1.0, 1.0)), f - vec2f(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 0.5 + 0.5;
}

fn noise_simplex(p: vec2f) -> f32 {
  let C = vec2f(0.211324865, 0.366025404);
  let i = floor(p + dot(p, vec2f(C.y)));
  let x0 = p - i + dot(i, vec2f(C.x));
  let i1 = select(vec2f(0.0, 1.0), vec2f(1.0, 0.0), x0.x > x0.y);
  let x1 = x0 - i1 + C.x;
  let x2 = x0 - 1.0 + 2.0 * C.x;
  var n = vec3f(0.0);
  var t = vec3f(0.5) - vec3f(dot(x0, x0), dot(x1, x1), dot(x2, x2));
  t = max(t, vec3f(0.0));
  t = t * t * t * t;
  n.x = dot(hash2v(i), x0);
  n.y = dot(hash2v(i + i1), x1);
  n.z = dot(hash2v(i + 1.0), x2);
  return dot(t, n) * 70.0 * 0.5 + 0.5;
}

fn noise_voronoi(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  var minDist = 1.0;
  for (var y = -1; y <= 1; y++) {
    for (var x = -1; x <= 1; x++) {
      let neighbor = vec2f(f32(x), f32(y));
      let point = vec2f(hash2(i + neighbor), hash2(i + neighbor + 100.0));
      let diff = neighbor + point - f;
      let dist = dot(diff, diff);
      minDist = min(minDist, dist);
    }
  }
  return sqrt(minDist);
}

fn noise_worley(p: vec2f) -> f32 {
  return 1.0 - noise_voronoi(p);
}
`

export { NOISE_LIBRARY }
