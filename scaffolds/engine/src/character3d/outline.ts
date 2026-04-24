/**
 * 4-conn NAVY outline post-process — ports our canonical outline doctrine
 * (scripts/asset/pixelize.py::dilate_4conn) to a real-time WGSL shader.
 *
 * Pass 1: scene renders to an offscreen rgba8unorm texture with transparent
 *         background (alpha=0) and character alpha=1.
 * Pass 2: this shader samples the scene:
 *         - If pixel is opaque (alpha > threshold): passthrough the color.
 *         - Else if ANY 4-conn neighbor is opaque: output NAVY solid.
 *         - Else: passthrough (stays transparent / background color).
 *
 * 4-conn (N/S/E/W only, no diagonals) per outline_doctrine.md — gives the
 * SNES-LTTP style diagonal-preferring silhouette with no L-corners.
 *
 * NAVY = (36, 27, 59) per pixelize.py constant. Dark-desaturated navy,
 * reads as outline without black's crushing contrast.
 */

const OUTLINE_SHADER = /* wgsl */ `
struct U {
  texelSize: vec2f,
  bgColor:   vec4f,
  viewMode:  f32,    // 0 = color+outline, 1 = normal, 2 = depth
  _pad:      f32,
}

@group(0) @binding(0) var<uniform> u: U;
@group(0) @binding(1) var sceneTex:  texture_2d<f32>;
@group(0) @binding(2) var normalTex: texture_2d<f32>;
@group(0) @binding(3) var depthTex:  texture_2d<f32>;

struct VsOut {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  let c = vec2f(f32((vid << 1u) & 2u), f32(vid & 2u));
  var out: VsOut;
  out.position = vec4f(c * 2.0 - 1.0, 0.0, 1.0);
  out.uv = vec2f(c.x, 1.0 - c.y);
  return out;
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let dim = vec2i(textureDimensions(sceneTex, 0));
  let px = vec2i(uv * vec2f(dim));
  let pxClamp = clamp(px, vec2i(0), dim - vec2i(1));

  // NORMAL VIEW: show the normal map as color (xyz encoded in [0,1]).
  if (u.viewMode > 1.5) {
    // DEPTH VIEW: show depth as grayscale. Background (alpha=0) stays bg.
    let d = textureLoad(depthTex, pxClamp, 0);
    let a = textureLoad(sceneTex, pxClamp, 0).a;
    if (a < 0.5) { return u.bgColor; }
    // Depth values live [0,1] where 0=near, 1=far. Remap so near=bright.
    let g = 1.0 - d.r;
    return vec4f(g, g, g, 1.0);
  }
  if (u.viewMode > 0.5) {
    let n = textureLoad(normalTex, pxClamp, 0);
    let a = textureLoad(sceneTex, pxClamp, 0).a;
    if (a < 0.5) { return u.bgColor; }
    return vec4f(n.rgb, 1.0);
  }

  // DEFAULT: color + 4-conn NAVY outline.
  let me = textureLoad(sceneTex, pxClamp, 0);
  if (me.a > 0.5) {
    return vec4f(me.rgb, 1.0);
  }
  let nA = textureLoad(sceneTex, clamp(px + vec2i( 0, -1), vec2i(0), dim - vec2i(1)), 0).a;
  let sA = textureLoad(sceneTex, clamp(px + vec2i( 0,  1), vec2i(0), dim - vec2i(1)), 0).a;
  let eA = textureLoad(sceneTex, clamp(px + vec2i( 1,  0), vec2i(0), dim - vec2i(1)), 0).a;
  let wA = textureLoad(sceneTex, clamp(px + vec2i(-1,  0), vec2i(0), dim - vec2i(1)), 0).a;
  if (nA > 0.5 || sA > 0.5 || eA > 0.5 || wA > 0.5) {
    return vec4f(0.141, 0.106, 0.231, 1.0);   // NAVY (36, 27, 59) / 255
  }
  return u.bgColor;
}
`

export type ViewMode = 'color' | 'normal' | 'depth'

export interface OutlinePass {
  run(encoder: GPUCommandEncoder, destView: GPUTextureView): void
  rebindSources(
    sceneView: GPUTextureView,
    normalView: GPUTextureView,
    depthView: GPUTextureView,
    width: number,
    height: number
  ): void
  setViewMode(mode: ViewMode): void
}

export function createOutlinePass(
  device: GPUDevice,
  format: GPUTextureFormat,
  initialSceneView: GPUTextureView,
  initialNormalView: GPUTextureView,
  initialDepthView: GPUTextureView,
  sceneW: number,
  sceneH: number,
  bgColor: [number, number, number, number] = [0.04, 0.04, 0.06, 1.0]
): OutlinePass {
  const shader = device.createShaderModule({ code: OUTLINE_SHADER, label: 'outline-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'outline-pipeline',
    layout: 'auto',
    vertex: { module: shader, entryPoint: 'vs_main' },
    fragment: { module: shader, entryPoint: 'fs_main', targets: [{ format }] },
    primitive: { topology: 'triangle-list' },
  })

  // Uniform: 2 floats texelSize + vec4 bgColor + 2 floats (viewMode, pad) = 40 bytes
  // rounded up for alignment: 48 bytes.
  const uniformBuffer = device.createBuffer({
    size: 48,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(12)
  let currentViewMode: ViewMode = 'color'
  let currentW = sceneW
  let currentH = sceneH

  function writeUniform(texW: number, texH: number) {
    currentW = texW
    currentH = texH
    uniformData[0] = 1 / texW
    uniformData[1] = 1 / texH
    uniformData[4] = bgColor[0]
    uniformData[5] = bgColor[1]
    uniformData[6] = bgColor[2]
    uniformData[7] = bgColor[3]
    uniformData[8] = currentViewMode === 'normal' ? 1 : currentViewMode === 'depth' ? 2 : 0
    device.queue.writeBuffer(uniformBuffer, 0, uniformData)
  }
  writeUniform(sceneW, sceneH)

  let bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: uniformBuffer } },
      { binding: 1, resource: initialSceneView },
      { binding: 2, resource: initialNormalView },
      { binding: 3, resource: initialDepthView },
    ],
  })

  return {
    run(encoder, destView) {
      const pass = encoder.beginRenderPass({
        colorAttachments: [
          {
            view: destView,
            loadOp: 'clear',
            storeOp: 'store',
            clearValue: { r: bgColor[0], g: bgColor[1], b: bgColor[2], a: bgColor[3] },
          },
        ],
      })
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.draw(3)
      pass.end()
    },
    rebindSources(sceneView, normalView, depthView, width, height) {
      writeUniform(width, height)
      bindGroup = device.createBindGroup({
        layout: pipeline.getBindGroupLayout(0),
        entries: [
          { binding: 0, resource: { buffer: uniformBuffer } },
          { binding: 1, resource: sceneView },
          { binding: 2, resource: normalView },
          { binding: 3, resource: depthView },
        ],
      })
    },
    setViewMode(mode) {
      currentViewMode = mode
      writeUniform(currentW, currentH)
    },
  }
}
