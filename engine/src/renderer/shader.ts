/**
 * Shader compilation pipeline.
 * Compiles WGSL source to GPUShaderModule with error reporting and caching.
 */

const shaderCache = new Map<string, GPUShaderModule>()

export function compileShader(
  device: GPUDevice,
  source: string,
  label?: string
): GPUShaderModule {
  const key = source
  const cached = shaderCache.get(key)
  if (cached) return cached

  const module = device.createShaderModule({
    code: source,
    label: label ?? 'unnamed-shader',
  })

  // Async compilation info (non-blocking)
  module.getCompilationInfo().then((info) => {
    for (const msg of info.messages) {
      const loc = msg.lineNum ? `:${msg.lineNum}:${msg.linePos}` : ''
      const prefix = msg.type === 'error' ? 'ERROR' : msg.type === 'warning' ? 'WARN' : 'INFO'
      console.warn(`[Shader ${label ?? '?'}${loc}] ${prefix}: ${msg.message}`)
    }
  })

  shaderCache.set(key, module)
  return module
}

export function clearShaderCache(): void {
  shaderCache.clear()
}

// Built-in shaders

export const TRIANGLE_SHADER = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) color: vec3f,
};

@vertex
fn vs_main(@location(0) position: vec3f, @location(1) color: vec3f) -> VertexOutput {
  var out: VertexOutput;
  out.position = vec4f(position, 1.0);
  out.color = color;
  return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4f {
  return vec4f(in.color, 1.0);
}
`

export const MESH_SHADER = /* wgsl */ `
struct Uniforms {
  mvp: mat4x4f,
  model: mat4x4f,
  normalMatrix: mat4x4f,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) worldPos: vec3f,
  @location(1) normal: vec3f,
  @location(2) uv: vec2f,
};

@vertex
fn vs_main(
  @location(0) position: vec3f,
  @location(1) normal: vec3f,
  @location(2) uv: vec2f,
) -> VertexOutput {
  var out: VertexOutput;
  out.position = uniforms.mvp * vec4f(position, 1.0);
  out.worldPos = (uniforms.model * vec4f(position, 1.0)).xyz;
  out.normal = normalize((uniforms.normalMatrix * vec4f(normal, 0.0)).xyz);
  out.uv = uv;
  return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4f {
  let lightDir = normalize(vec3f(1.0, 2.0, 1.5));
  let ambient = vec3f(0.15);
  let diffuse = max(dot(in.normal, lightDir), 0.0);
  let color = ambient + vec3f(0.85) * diffuse;
  return vec4f(color, 1.0);
}
`

export const INSTANCED_SHADER = /* wgsl */ `
struct Camera {
  viewProj: mat4x4f,
};

@group(0) @binding(0) var<uniform> camera: Camera;

struct InstanceData {
  model: mat4x4f,
  color: vec4f,
};

struct Instances {
  data: array<InstanceData>,
};

@group(0) @binding(1) var<storage, read> instances: Instances;

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) normal: vec3f,
  @location(1) color: vec3f,
};

@vertex
fn vs_main(
  @builtin(instance_index) instanceIdx: u32,
  @location(0) position: vec3f,
  @location(1) normal: vec3f,
) -> VertexOutput {
  let inst = instances.data[instanceIdx];
  var out: VertexOutput;
  out.position = camera.viewProj * inst.model * vec4f(position, 1.0);
  out.normal = normalize((inst.model * vec4f(normal, 0.0)).xyz);
  out.color = inst.color.rgb;
  return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4f {
  let lightDir = normalize(vec3f(1.0, 2.0, 1.5));
  let ambient = vec3f(0.12);
  let diffuse = max(dot(in.normal, lightDir), 0.0);
  let color = in.color * (ambient + vec3f(0.88) * diffuse);
  return vec4f(color, 1.0);
}
`
