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
struct DirLight {
  dirI:  vec4f,   // xyz = unit direction TO light, w = intensity
  color: vec4f,   // rgb = color, a = unused
}

struct U {
  texelSize:    vec2f,
  _pad0:        vec2f,
  bgColor:      vec4f,
  viewMode:     f32,   // 0 = color+outline, 1 = normal, 2 = depth
  depthOutline: f32,   // 0 off, 1 on — adds interior depth-step outlines
  depthThresh:  f32,   // depth-delta threshold for edge detection
  lighting:     f32,   // 0 off, 1 on — 2-tone cel via MRT normal
  ambient:      vec4f, // rgb = ambient color, a = intensity (reserved; unused in 2-tone path)
  lights:       array<DirLight, 2>,  // key + fill; only [0] used in 2-tone path
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

  // Shared checkerboard helper — all view modes use it for transparent
  // background pixels so the silhouette always reads against the same
  // backdrop regardless of which view we're debugging.
  let cellView = ((px.x >> 1) ^ (px.y >> 1)) & 1;
  let shadeView = select(0.12, 0.20, cellView == 1);
  let checker = vec4f(shadeView, shadeView, shadeView, 1.0);

  // NORMAL VIEW: show the normal map as color (xyz encoded in [0,1]).
  if (u.viewMode > 1.5) {
    let d = textureLoad(depthTex, pxClamp, 0);
    let a = textureLoad(sceneTex, pxClamp, 0).a;
    if (a < 0.5) { return checker; }
    let g = 1.0 - d.r;
    return vec4f(g, g, g, 1.0);
  }
  if (u.viewMode > 0.5) {
    let n = textureLoad(normalTex, pxClamp, 0);
    let a = textureLoad(sceneTex, pxClamp, 0).a;
    if (a < 0.5) { return checker; }
    return vec4f(n.rgb, 1.0);
  }

  // DEFAULT: color + 4-conn NAVY outline + optional cel lighting.
  let me = textureLoad(sceneTex, pxClamp, 0);
  let NAVY = vec4f(0.141, 0.106, 0.231, 1.0);

  // Quantized-Lambert (cel) shading. Normal buffer stores world-space
  // normals encoded to [0,1] via n*0.5+0.5 — decode back to [-1,1].
  // Three bands per light: shadow (0.35×), mid (0.7×), full (1.0×). The
  // bands apply as a brightness multiplier on the light's color, then
  // all contributions are summed with ambient and MIN'd to 1.0 so heavy
  // lights don't blow past the palette.
  var lit = vec3f(1.0, 1.0, 1.0);
  if (u.lighting > 0.5 && me.a > 0.5) {
    // Minimal 2-tone cel: color × (lit or shadow) based on the key light
    // dotted against the MRT world-space normal. No fill, no ambient,
    // no AO. Classic SNES pixel-art — two brightness states per palette
    // colour, hard transition at the shadow line. Raymarch renderer is
    // a pure G-buffer (color + normal + depth); shading lives here.
    let n = normalize(textureLoad(normalTex, pxClamp, 0).xyz * 2.0 - 1.0);
    let keyDir = u.lights[0].dirI.xyz;
    let d = dot(n, keyDir);
    let shadowTone = 0.55;
    lit = vec3f(select(shadowTone, 1.0, d > 0.0));
  }

  // Interior depth outline: opaque pixels only, compared against OPAQUE
  // neighbors only. Skipping transparent neighbors prevents the depth
  // test from re-firing on the silhouette (where character depth ~0.5
  // vs. background clear depth 1.0 is a huge step that would paint a
  // second outline inside the exterior ring). Result: D draws outlines
  // only at interior depth discontinuities — arm over body, weapon in
  // front of torso, elbow crook — leaving the silhouette to the 4-conn
  // alpha dilation below.
  if (me.a > 0.5) {
    if (u.depthOutline > 0.5) {
      let d  = textureLoad(depthTex, pxClamp, 0).r;
      let pN = clamp(px + vec2i( 0, -1), vec2i(0), dim - vec2i(1));
      let pS = clamp(px + vec2i( 0,  1), vec2i(0), dim - vec2i(1));
      let pE = clamp(px + vec2i( 1,  0), vec2i(0), dim - vec2i(1));
      let pW = clamp(px + vec2i(-1,  0), vec2i(0), dim - vec2i(1));
      let aN = textureLoad(sceneTex, pN, 0).a;
      let aS = textureLoad(sceneTex, pS, 0).a;
      let aE = textureLoad(sceneTex, pE, 0).a;
      let aW = textureLoad(sceneTex, pW, 0).a;
      let dn = select(d, textureLoad(depthTex, pN, 0).r, aN > 0.5);
      let ds = select(d, textureLoad(depthTex, pS, 0).r, aS > 0.5);
      let de = select(d, textureLoad(depthTex, pE, 0).r, aE > 0.5);
      let dw = select(d, textureLoad(depthTex, pW, 0).r, aW > 0.5);
      let gap = max(max(abs(d - dn), abs(d - ds)), max(abs(d - de), abs(d - dw)));
      if (gap > u.depthThresh) { return NAVY; }
    }
    return vec4f(me.rgb * lit, 1.0);
  }

  // Silhouette outline: transparent pixel with any opaque 4-conn neighbor.
  let nA = textureLoad(sceneTex, clamp(px + vec2i( 0, -1), vec2i(0), dim - vec2i(1)), 0).a;
  let sA = textureLoad(sceneTex, clamp(px + vec2i( 0,  1), vec2i(0), dim - vec2i(1)), 0).a;
  let eA = textureLoad(sceneTex, clamp(px + vec2i( 1,  0), vec2i(0), dim - vec2i(1)), 0).a;
  let wA = textureLoad(sceneTex, clamp(px + vec2i(-1,  0), vec2i(0), dim - vec2i(1)), 0).a;
  if (nA > 0.5 || sA > 0.5 || eA > 0.5 || wA > 0.5) {
    return NAVY;
  }
  // Checkerboard alpha background (see 'checker' computed at top of
  // fs_main). 2×2 integer-pixel cells → pixel-perfect at every tier.
  return checker;
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
  setDepthOutline(on: boolean): void
  setDepthThreshold(t: number): void
  setLighting(mode: 0 | 1): void
  setLightDirection(idx: number, dir: [number, number, number]): void
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

  // Uniform layout: see U struct in shader. 128 bytes = 32 floats.
  //   [0..1]  texelSize (vec2 + vec2 pad = 4 slots)
  //   [4..7]  bgColor
  //   [8..11] viewMode, depthOutline, depthThresh, lighting
  //   [12..15] ambient (rgb + intensity)
  //   [16..23] light[0] (dirI vec4 + color vec4)
  //   [24..31] light[1] (dirI vec4 + color vec4)
  const uniformBuffer = device.createBuffer({
    size: 128,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(32)
  let currentViewMode: ViewMode = 'color'
  let currentDepthOutline = false
  let currentDepthThresh = 0.025
  // 0 = off, 1 = MRT normal (authoritative), 2 = reconstructed from depth
  let currentLightingMode: 0 | 1 | 2 = 0
  let currentW = sceneW
  let currentH = sceneH
  // Default rig: cool ambient + warm key (3/4 front) + cool fill (back).
  // Directions are TO the light source (what the shader dots against).
  let ambient = { r: 0.5, g: 0.55, b: 0.65, intensity: 0.4 }
  let lights: { dir: [number, number, number]; intensity: number; color: [number, number, number] }[] = [
    { dir: normalize([0.6, 0.7, 0.3]),   intensity: 0.8,  color: [1.0, 0.95, 0.85] },
    { dir: normalize([-0.4, 0.3, -0.6]), intensity: 0.35, color: [0.75, 0.85, 1.0] },
  ]

  function writeUniform(texW: number, texH: number) {
    currentW = texW
    currentH = texH
    uniformData[0] = 1 / texW
    uniformData[1] = 1 / texH
    uniformData[4] = bgColor[0]
    uniformData[5] = bgColor[1]
    uniformData[6] = bgColor[2]
    uniformData[7] = bgColor[3]
    uniformData[8]  = currentViewMode === 'normal' ? 1 : currentViewMode === 'depth' ? 2 : 0
    uniformData[9]  = currentDepthOutline ? 1 : 0
    uniformData[10] = currentDepthThresh
    uniformData[11] = currentLightingMode
    uniformData[12] = ambient.r
    uniformData[13] = ambient.g
    uniformData[14] = ambient.b
    uniformData[15] = ambient.intensity
    for (let i = 0; i < 2; i++) {
      const L = lights[i]
      const off = 16 + i * 8
      uniformData[off + 0] = L.dir[0]
      uniformData[off + 1] = L.dir[1]
      uniformData[off + 2] = L.dir[2]
      uniformData[off + 3] = L.intensity
      uniformData[off + 4] = L.color[0]
      uniformData[off + 5] = L.color[1]
      uniformData[off + 6] = L.color[2]
      uniformData[off + 7] = 0
    }
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
    setDepthOutline(on) {
      currentDepthOutline = on
      writeUniform(currentW, currentH)
    },
    setDepthThreshold(t) {
      currentDepthThresh = t
      writeUniform(currentW, currentH)
    },
    setLighting(mode) {
      currentLightingMode = mode
      writeUniform(currentW, currentH)
    },
    setLightDirection(idx, dir) {
      if (idx >= 0 && idx < lights.length) {
        lights[idx].dir = normalize(dir)
        writeUniform(currentW, currentH)
      }
    },
  }
}

function normalize(v: [number, number, number]): [number, number, number] {
  const len = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / len, v[1] / len, v[2] / len]
}
