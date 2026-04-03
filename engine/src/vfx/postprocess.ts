/**
 * Post-processing — full-screen compute passes.
 * Bloom, SSAO, tone mapping, color grading.
 */

// --- Fullscreen quad vertex shader (shared by all post-proc) ---
export const FULLSCREEN_VERT = /* wgsl */ `
struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
};

@vertex
fn vs_main(@builtin(vertex_index) idx: u32) -> VertexOutput {
  var pos = array<vec2f, 3>(
    vec2f(-1.0, -1.0),
    vec2f( 3.0, -1.0),
    vec2f(-1.0,  3.0),
  );
  var uv = array<vec2f, 3>(
    vec2f(0.0, 1.0),
    vec2f(2.0, 1.0),
    vec2f(0.0, -1.0),
  );
  var out: VertexOutput;
  out.position = vec4f(pos[idx], 0.0, 1.0);
  out.uv = uv[idx];
  return out;
}
`

// --- Bloom ---
const BLOOM_THRESHOLD_FRAG = /* wgsl */ `
@group(0) @binding(0) var inputTex: texture_2d<f32>;
@group(0) @binding(1) var inputSampler: sampler;

struct Params { threshold: f32, softKnee: f32, };
@group(0) @binding(2) var<uniform> params: Params;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let color = textureSample(inputTex, inputSampler, uv);
  let brightness = dot(color.rgb, vec3f(0.2126, 0.7152, 0.0722));
  let soft = clamp(brightness - params.threshold + params.softKnee, 0.0, 2.0 * params.softKnee);
  let contribution = max(soft * soft / (4.0 * params.softKnee + 0.0001), brightness - params.threshold);
  let weight = max(contribution / max(brightness, 0.0001), 0.0);
  return vec4f(color.rgb * weight, 1.0);
}
`

const BLUR_FRAG = /* wgsl */ `
@group(0) @binding(0) var inputTex: texture_2d<f32>;
@group(0) @binding(1) var inputSampler: sampler;

struct BlurParams { direction: vec2f, };
@group(0) @binding(2) var<uniform> params: BlurParams;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let texSize = vec2f(textureDimensions(inputTex));
  let texelSize = params.direction / texSize;
  var result = vec4f(0.0);
  let weights = array<f32, 5>(0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
  result += textureSample(inputTex, inputSampler, uv) * weights[0];
  for (var i = 1; i < 5; i++) {
    let offset = texelSize * f32(i);
    result += textureSample(inputTex, inputSampler, uv + offset) * weights[i];
    result += textureSample(inputTex, inputSampler, uv - offset) * weights[i];
  }
  return result;
}
`

const COMPOSITE_FRAG = /* wgsl */ `
@group(0) @binding(0) var sceneTex: texture_2d<f32>;
@group(0) @binding(1) var bloomTex: texture_2d<f32>;
@group(0) @binding(2) var inputSampler: sampler;

struct Params { bloomStrength: f32, exposure: f32, };
@group(0) @binding(3) var<uniform> params: Params;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let scene = textureSample(sceneTex, inputSampler, uv).rgb;
  let bloom = textureSample(bloomTex, inputSampler, uv).rgb;
  var color = scene + bloom * params.bloomStrength;

  // ACES filmic tone mapping
  color *= params.exposure;
  let a = color * (color * 2.51 + 0.03);
  let b = color * (color * 2.43 + 0.59) + 0.14;
  color = a / b;

  // sRGB gamma
  color = pow(clamp(color, vec3f(0.0), vec3f(1.0)), vec3f(1.0 / 2.2));
  return vec4f(color, 1.0);
}
`

export interface BloomConfig {
  threshold: number
  softKnee: number
  strength: number
  exposure: number
  passes: number  // number of blur iterations
}

export const DEFAULT_BLOOM: BloomConfig = {
  threshold: 0.8,
  softKnee: 0.5,
  strength: 0.5,
  exposure: 1.0,
  passes: 3,
}

export interface PostProcessPipelines {
  thresholdPipeline: GPURenderPipeline
  blurPipeline: GPURenderPipeline
  compositePipeline: GPURenderPipeline
  sampler: GPUSampler
}

export function createPostProcessPipelines(
  device: GPUDevice,
  format: GPUTextureFormat
): PostProcessPipelines {
  const vertModule = device.createShaderModule({ code: FULLSCREEN_VERT, label: 'pp-vert' })

  const createPP = (fragCode: string, label: string, extraBindings: GPUBindGroupLayoutEntry[] = []) => {
    const fragModule = device.createShaderModule({ code: fragCode, label })
    return device.createRenderPipeline({
      label,
      layout: 'auto',
      vertex: { module: vertModule, entryPoint: 'vs_main' },
      fragment: {
        module: fragModule,
        entryPoint: 'fs_main',
        targets: [{ format }],
      },
    })
  }

  return {
    thresholdPipeline: createPP(BLOOM_THRESHOLD_FRAG, 'bloom-threshold'),
    blurPipeline: createPP(BLUR_FRAG, 'bloom-blur'),
    compositePipeline: createPP(COMPOSITE_FRAG, 'bloom-composite'),
    sampler: device.createSampler({ minFilter: 'linear', magFilter: 'linear' }),
  }
}

// --- Tone mapping standalone ---
const TONEMAP_FRAG = /* wgsl */ `
@group(0) @binding(0) var inputTex: texture_2d<f32>;
@group(0) @binding(1) var inputSampler: sampler;

struct Params { exposure: f32, mode: u32, }; // 0=ACES, 1=Reinhard, 2=Linear
@group(0) @binding(2) var<uniform> params: Params;

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  var color = textureSample(inputTex, inputSampler, uv).rgb * params.exposure;
  if (params.mode == 0u) {
    // ACES filmic
    let a = color * (color * 2.51 + 0.03);
    let b = color * (color * 2.43 + 0.59) + 0.14;
    color = a / b;
  } else if (params.mode == 1u) {
    // Reinhard
    color = color / (color + 1.0);
  }
  color = pow(clamp(color, vec3f(0.0), vec3f(1.0)), vec3f(1.0 / 2.2));
  return vec4f(color, 1.0);
}
`

export { BLOOM_THRESHOLD_FRAG, BLUR_FRAG, COMPOSITE_FRAG, TONEMAP_FRAG }
