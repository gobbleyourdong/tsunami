/**
 * GPU skinning via compute shader.
 * Transforms vertices by joint matrices on the GPU — no CPU readback.
 */

const SKINNING_SHADER = /* wgsl */ `
struct JointMatrices {
  matrices: array<mat4x4f>,
};

struct VertexIn {
  position: vec3f,
  normal: vec3f,
  joints: vec4u,    // bone indices
  weights: vec4f,   // blend weights
};

struct VertexOut {
  position: vec3f,
  normal: vec3f,
};

@group(0) @binding(0) var<storage, read> joints: JointMatrices;
@group(0) @binding(1) var<storage, read> verticesIn: array<VertexIn>;
@group(0) @binding(2) var<storage, read_write> verticesOut: array<VertexOut>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3u) {
  let idx = gid.x;
  if (idx >= arrayLength(&verticesIn)) { return; }

  let v = verticesIn[idx];
  var pos = vec3f(0.0);
  var nrm = vec3f(0.0);

  for (var i = 0u; i < 4u; i++) {
    let jointIdx = v.joints[i];
    let weight = v.weights[i];
    if (weight <= 0.0) { continue; }

    let m = joints.matrices[jointIdx];
    pos += (m * vec4f(v.position, 1.0)).xyz * weight;
    nrm += (m * vec4f(v.normal, 0.0)).xyz * weight;
  }

  verticesOut[idx].position = pos;
  verticesOut[idx].normal = normalize(nrm);
}
`

export interface SkinningPipeline {
  pipeline: GPUComputePipeline
  bindGroupLayout: GPUBindGroupLayout
}

let cachedPipeline: SkinningPipeline | null = null

export function getSkinningPipeline(device: GPUDevice): SkinningPipeline {
  if (cachedPipeline) return cachedPipeline

  const module = device.createShaderModule({
    code: SKINNING_SHADER,
    label: 'gpu-skinning',
  })

  const bindGroupLayout = device.createBindGroupLayout({
    entries: [
      { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
      { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
      { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
    ],
  })

  const pipeline = device.createComputePipeline({
    label: 'gpu-skinning-pipeline',
    layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout] }),
    compute: { module, entryPoint: 'main' },
  })

  cachedPipeline = { pipeline, bindGroupLayout }
  return cachedPipeline
}

export interface SkinningBuffers {
  jointBuffer: GPUBuffer
  inputBuffer: GPUBuffer
  outputBuffer: GPUBuffer
  bindGroup: GPUBindGroup
  vertexCount: number
}

/**
 * Create GPU buffers for skinned mesh.
 * Input: interleaved [pos.xyz, normal.xyz, joints.xyzw, weights.xyzw] per vertex.
 */
export function createSkinningBuffers(
  device: GPUDevice,
  vertexCount: number,
  maxBones: number
): SkinningBuffers {
  const { pipeline, bindGroupLayout } = getSkinningPipeline(device)

  const jointBuffer = device.createBuffer({
    size: maxBones * 64, // mat4 = 64 bytes
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    label: 'joint-matrices',
  })

  // Input: pos(3) + normal(3) + joints(4u) + weights(4f) = 56 bytes per vertex
  const inputBuffer = device.createBuffer({
    size: vertexCount * 56,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    label: 'skinning-input',
  })

  // Output: pos(3) + normal(3) = 24 bytes per vertex
  const outputBuffer = device.createBuffer({
    size: vertexCount * 24,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.VERTEX,
    label: 'skinning-output',
  })

  const bindGroup = device.createBindGroup({
    layout: bindGroupLayout,
    entries: [
      { binding: 0, resource: { buffer: jointBuffer } },
      { binding: 1, resource: { buffer: inputBuffer } },
      { binding: 2, resource: { buffer: outputBuffer } },
    ],
  })

  return { jointBuffer, inputBuffer, outputBuffer, bindGroup, vertexCount }
}

/**
 * Dispatch the skinning compute shader.
 */
export function dispatchSkinning(
  encoder: GPUCommandEncoder,
  device: GPUDevice,
  buffers: SkinningBuffers
): void {
  const { pipeline } = getSkinningPipeline(device)
  const pass = encoder.beginComputePass({ label: 'skinning-pass' })
  pass.setPipeline(pipeline)
  pass.setBindGroup(0, buffers.bindGroup)
  pass.dispatchWorkgroups(Math.ceil(buffers.vertexCount / 64))
  pass.end()
}
