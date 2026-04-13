/**
 * GPU Particles — compute-driven, no CPU readback.
 * Emit, update, sort, and render particles entirely on the GPU.
 */

export interface ParticleEmitterConfig {
  maxParticles: number
  emitRate: number           // particles per second
  lifetime: [number, number] // min/max seconds
  speed: [number, number]    // min/max initial speed
  size: [number, number]     // start/end size
  color: [number, number, number, number]  // RGBA start
  colorEnd: [number, number, number, number] // RGBA end
  gravity: [number, number, number]
  emitterShape: 'point' | 'sphere' | 'cone' | 'box'
  emitterRadius: number
  coneAngle: number // degrees, for cone shape
}

const DEFAULT_CONFIG: ParticleEmitterConfig = {
  maxParticles: 10000,
  emitRate: 100,
  lifetime: [1, 3],
  speed: [1, 5],
  size: [0.1, 0.01],
  color: [1, 1, 1, 1],
  colorEnd: [1, 1, 1, 0],
  gravity: [0, -9.81, 0],
  emitterShape: 'point',
  emitterRadius: 1,
  coneAngle: 30,
}

// Particle struct: position(3) + velocity(3) + life(1) + maxLife(1) + size(1) + pad(1) = 10 floats = 40 bytes
const PARTICLE_STRIDE = 10
const PARTICLE_BYTES = PARTICLE_STRIDE * 4

const EMIT_SHADER = /* wgsl */ `
struct Params {
  emitterPos: vec3f,
  emitCount: u32,
  minLife: f32,
  maxLife: f32,
  minSpeed: f32,
  maxSpeed: f32,
  startSize: f32,
  endSize: f32,
  time: f32,
  shape: u32,  // 0=point, 1=sphere, 2=cone, 3=box
  radius: f32,
  coneAngle: f32,
  _pad: f32,
};

struct Particle {
  pos: vec3f,
  vel: vec3f,
  life: f32,
  maxLife: f32,
  size: f32,
  _pad: f32,
};

@group(0) @binding(0) var<uniform> params: Params;
@group(0) @binding(1) var<storage, read_write> particles: array<Particle>;
@group(0) @binding(2) var<storage, read_write> counter: atomic<u32>;

fn rand(seed: u32) -> f32 {
  var s = seed;
  s = s ^ (s << 13u); s = s ^ (s >> 17u); s = s ^ (s << 5u);
  return f32(s & 0x7FFFFFFFu) / f32(0x7FFFFFFF);
}

fn randVec3(seed: u32) -> vec3f {
  return normalize(vec3f(
    rand(seed) * 2.0 - 1.0,
    rand(seed + 1u) * 2.0 - 1.0,
    rand(seed + 2u) * 2.0 - 1.0,
  ));
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3u) {
  if (gid.x >= params.emitCount) { return; }

  // Find a dead particle to reuse
  let maxP = arrayLength(&particles);
  for (var i = 0u; i < maxP; i++) {
    let idx = (gid.x * 97u + i) % maxP; // pseudo-random scan
    if (particles[idx].life <= 0.0) {
      let seed = gid.x * 1000u + u32(params.time * 1000.0) + i;
      let dir = randVec3(seed);
      let speed = mix(params.minSpeed, params.maxSpeed, rand(seed + 10u));
      particles[idx].pos = params.emitterPos;
      particles[idx].vel = dir * speed;
      particles[idx].life = mix(params.minLife, params.maxLife, rand(seed + 20u));
      particles[idx].maxLife = particles[idx].life;
      particles[idx].size = params.startSize;
      return;
    }
  }
}
`

const UPDATE_SHADER = /* wgsl */ `
struct UpdateParams {
  dt: f32,
  gravity: vec3f,
  startSize: f32,
  endSize: f32,
  _pad: vec2f,
};

struct Particle {
  pos: vec3f,
  vel: vec3f,
  life: f32,
  maxLife: f32,
  size: f32,
  _pad: f32,
};

@group(0) @binding(0) var<uniform> params: UpdateParams;
@group(0) @binding(1) var<storage, read_write> particles: array<Particle>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3u) {
  let idx = gid.x;
  if (idx >= arrayLength(&particles)) { return; }
  if (particles[idx].life <= 0.0) { return; }

  // Integrate
  particles[idx].vel += params.gravity * params.dt;
  particles[idx].pos += particles[idx].vel * params.dt;
  particles[idx].life -= params.dt;

  // Size over lifetime
  let t = 1.0 - particles[idx].life / particles[idx].maxLife;
  particles[idx].size = mix(params.startSize, params.endSize, t);
}
`

export class ParticleSystem {
  config: ParticleEmitterConfig
  particleBuffer: GPUBuffer
  counterBuffer: GPUBuffer

  private device: GPUDevice
  private emitPipeline: GPUComputePipeline
  private updatePipeline: GPUComputePipeline
  private emitParamsBuffer: GPUBuffer
  private updateParamsBuffer: GPUBuffer
  private emitBindGroup: GPUBindGroup
  private updateBindGroup: GPUBindGroup
  private emitAccum = 0

  constructor(device: GPUDevice, config?: Partial<ParticleEmitterConfig>) {
    this.device = device
    this.config = { ...DEFAULT_CONFIG, ...config }

    const maxP = this.config.maxParticles
    this.particleBuffer = device.createBuffer({
      size: maxP * PARTICLE_BYTES,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
      label: 'particles',
    })

    this.counterBuffer = device.createBuffer({
      size: 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      label: 'particle-counter',
    })

    // Emit pipeline
    const emitModule = device.createShaderModule({ code: EMIT_SHADER, label: 'particle-emit' })
    const emitLayout = device.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
        { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
      ],
    })
    this.emitPipeline = device.createComputePipeline({
      layout: device.createPipelineLayout({ bindGroupLayouts: [emitLayout] }),
      compute: { module: emitModule, entryPoint: 'main' },
    })

    this.emitParamsBuffer = device.createBuffer({
      size: 64, // padded to 16-byte alignment
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    })

    this.emitBindGroup = device.createBindGroup({
      layout: emitLayout,
      entries: [
        { binding: 0, resource: { buffer: this.emitParamsBuffer } },
        { binding: 1, resource: { buffer: this.particleBuffer } },
        { binding: 2, resource: { buffer: this.counterBuffer } },
      ],
    })

    // Update pipeline
    const updateModule = device.createShaderModule({ code: UPDATE_SHADER, label: 'particle-update' })
    const updateLayout = device.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
      ],
    })
    this.updatePipeline = device.createComputePipeline({
      layout: device.createPipelineLayout({ bindGroupLayouts: [updateLayout] }),
      compute: { module: updateModule, entryPoint: 'main' },
    })

    this.updateParamsBuffer = device.createBuffer({
      size: 32,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    })

    this.updateBindGroup = device.createBindGroup({
      layout: updateLayout,
      entries: [
        { binding: 0, resource: { buffer: this.updateParamsBuffer } },
        { binding: 1, resource: { buffer: this.particleBuffer } },
      ],
    })
  }

  /** Dispatch emit + update compute passes. */
  update(encoder: GPUCommandEncoder, dt: number, time: number, emitterPos: [number, number, number]): void {
    const c = this.config

    // Emit
    this.emitAccum += c.emitRate * dt
    const emitCount = Math.floor(this.emitAccum)
    this.emitAccum -= emitCount

    if (emitCount > 0) {
      const emitParams = new Float32Array(16)
      emitParams[0] = emitterPos[0]; emitParams[1] = emitterPos[1]; emitParams[2] = emitterPos[2]
      new Uint32Array(emitParams.buffer)[3] = emitCount
      emitParams[4] = c.lifetime[0]; emitParams[5] = c.lifetime[1]
      emitParams[6] = c.speed[0]; emitParams[7] = c.speed[1]
      emitParams[8] = c.size[0]; emitParams[9] = c.size[1]
      emitParams[10] = time
      new Uint32Array(emitParams.buffer)[11] = ['point', 'sphere', 'cone', 'box'].indexOf(c.emitterShape)
      emitParams[12] = c.emitterRadius
      emitParams[13] = c.coneAngle * Math.PI / 180
      this.device.queue.writeBuffer(this.emitParamsBuffer, 0, emitParams)

      const pass = encoder.beginComputePass({ label: 'particle-emit' })
      pass.setPipeline(this.emitPipeline)
      pass.setBindGroup(0, this.emitBindGroup)
      pass.dispatchWorkgroups(Math.ceil(emitCount / 64))
      pass.end()
    }

    // Update
    const updateParams = new Float32Array(8)
    updateParams[0] = dt
    updateParams[1] = c.gravity[0]; updateParams[2] = c.gravity[1]; updateParams[3] = c.gravity[2]
    updateParams[4] = c.size[0]; updateParams[5] = c.size[1]
    this.device.queue.writeBuffer(this.updateParamsBuffer, 0, updateParams)

    const pass = encoder.beginComputePass({ label: 'particle-update' })
    pass.setPipeline(this.updatePipeline)
    pass.setBindGroup(0, this.updateBindGroup)
    pass.dispatchWorkgroups(Math.ceil(c.maxParticles / 64))
    pass.end()
  }

  destroy(): void {
    this.particleBuffer.destroy()
    this.counterBuffer.destroy()
    this.emitParamsBuffer.destroy()
    this.updateParamsBuffer.destroy()
  }
}
