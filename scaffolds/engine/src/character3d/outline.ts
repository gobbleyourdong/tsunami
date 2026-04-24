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
  leftEye:      vec4f, // (screenX, screenY, ndcDepth, _) — per-point projected
  rightEye:     vec4f, //   from world-space eye/mouth positions so rotation
  mouth:        vec4f, //   (incl. upside-down) moves the paint with the head.
  pupilHalf:    vec4f, // (halfW, halfH, _, _) in pixels
  whiteHalf:    vec4f, // (halfW, halfH, _, _) in pixels
  mouthHalf:    vec4f, // (halfW, halfH, _, _) in pixels
  eyeColor:     vec4f, // pupil color (rgb + enable in .a)
  whiteColor:   vec4f, // eye-white color (rgb + enable in .a)
  mouthColor:   vec4f, // mouth color (rgb + enable in .a)
  viewForward:  vec4f, // camera forward (world) — extra front-face gate
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

  // SINGLE depth-based outline — catches both silhouette and interior
  // creases in one test. Rule: a pixel is NAVY if any 4-conn neighbor
  // is SIGNIFICANTLY CLOSER (smaller depth). That covers:
  //
  //   silhouette: bg pixel (depth=1.0) beside character pixel (~0.5)
  //               → neighbor is much closer → NAVY on the bg side, one
  //               pixel ring around the character.
  //   interior:   far-limb pixel (0.55) beside near-limb (0.45) →
  //               neighbor closer by 0.10 → NAVY on the far side of
  //               the arm/body seam.
  //
  // A pixel whose neighbors are all farther or equal is NOT an outline
  // (character's near edge paints colour, not NAVY). One sidedness
  // keeps the line 1-pixel wide instead of doubling up on both sides.
  if (u.depthOutline > 0.5) {
    let d  = textureLoad(depthTex, pxClamp, 0).r;
    let dN = textureLoad(depthTex, clamp(px + vec2i( 0, -1), vec2i(0), dim - vec2i(1)), 0).r;
    let dS = textureLoad(depthTex, clamp(px + vec2i( 0,  1), vec2i(0), dim - vec2i(1)), 0).r;
    let dE = textureLoad(depthTex, clamp(px + vec2i( 1,  0), vec2i(0), dim - vec2i(1)), 0).r;
    let dW = textureLoad(depthTex, clamp(px + vec2i(-1,  0), vec2i(0), dim - vec2i(1)), 0).r;
    let closestDelta = max(max(d - dN, d - dS), max(d - dE, d - dW));
    if (closestDelta > u.depthThresh) { return NAVY; }
  }

  if (me.a < 0.5) { return checker; }

  // Face paint-on: per-point projected eyes + mouth. Each one has its
  // own screen pixel position + NDC depth, so when the head rotates
  // (including upside-down) the paint follows the actual 3D eye/mouth
  // surface. Pass-band gate uses each point's own depth, tighter than
  // a single shared face anchor — reduces flicker at marginal angles.
  let faceN = normalize(textureLoad(normalTex, pxClamp, 0).xyz * 2.0 - 1.0);
  let frontFacing = dot(faceN, u.viewForward.xyz) < 0.0;
  let pixelDepth = textureLoad(depthTex, pxClamp, 0).r;
  let depthTol = 0.02;
  let pxF = vec2f(f32(px.x), f32(px.y));

  // Mario eye stamp. Each eye = 2 px wide × 3 px tall pattern.
  // The demo places each anchor exactly 1 px from face-center along the
  // head-right screen axis, so leftEye anchor sits on the INNER column of
  // the left eye block and rightEye anchor sits on the INNER column of
  // the right eye block. Blocks extend outward from their anchors; a
  // single unpainted column between them falls out automatically.
  //
  //   LEFT eye block (dxL in {0, +1}):    RIGHT eye block (dxR in {-1, 0}):
  //     [inner] [outer]                     [outer] [inner]
  //       W       W                           W       W
  //       B       W                           W       B
  //       B       W                           W       B
  //   pupil pillar (W top + B bottom pair) at dx=0 for both eyes.
  //
  // pupilHalf / whiteHalf are ignored on this path — pattern is fixed.
  if (frontFacing && u.eyeColor.a > 0.5) {
    // LEFT eye (character's left = projects to screen-right). Block
    // extends to the right of the anchor; inner column is the anchor.
    let lAx = i32(round(u.leftEye.x));
    let lAy = i32(round(u.leftEye.y));
    if (abs(pixelDepth - u.leftEye.z) < depthTol) {
      let dxL = px.x - lAx;
      let dyL = px.y - lAy;
      if (dyL >= -1 && dyL <= 1 && dxL >= 0 && dxL <= 1) {
        if (dxL == 0 && dyL >= 0) { return vec4f(u.eyeColor.rgb, 1.0); }
        return vec4f(u.whiteColor.rgb, 1.0);
      }
    }
    // RIGHT eye (character's right = projects to screen-left). Block
    // extends to the left of the anchor; inner column is the anchor.
    let rAx = i32(round(u.rightEye.x));
    let rAy = i32(round(u.rightEye.y));
    if (abs(pixelDepth - u.rightEye.z) < depthTol) {
      let dxR = px.x - rAx;
      let dyR = px.y - rAy;
      if (dyR >= -1 && dyR <= 1 && dxR >= -1 && dxR <= 0) {
        if (dxR == 0 && dyR >= 0) { return vec4f(u.eyeColor.rgb, 1.0); }
        return vec4f(u.whiteColor.rgb, 1.0);
      }
    }
  }
  if (frontFacing && u.mouthColor.a > 0.5) {
    let mOff = pxF - u.mouth.xy;
    let mInDepth = abs(pixelDepth - u.mouth.z) < depthTol;
    if (mInDepth && abs(mOff.x) <= u.mouthHalf.x && abs(mOff.y) <= u.mouthHalf.y) {
      return vec4f(u.mouthColor.rgb, 1.0);
    }
  }

  return vec4f(me.rgb * lit, 1.0);
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
  /** Stamp nested-rect eye pixels onto the rendered sprite. Inner rect
   *  is the pupil, outer is the eye-white. All coords in screen pixels
   *  from the CPU-projected head position.
   *   - glyph: (eyeGap, eyeYOff, pupilHalfW, pupilHalfH)
   *   - white: (whiteHalfW, whiteHalfH, _, _)  — must be >= pupil
   *   - pupil / white color: rgb + enable(.a > 0.5). Pupil enable=0
   *     kills the whole overlay; white enable=0 skips just the white
   *     layer (pupil alone renders as bare dot on skin). */
  setFacePaint(
    leftEye: [number, number, number],
    rightEye: [number, number, number],
    mouth: [number, number, number],
    pupilHalf: [number, number],
    whiteHalf: [number, number],
    mouthHalf: [number, number],
    pupilColor: [number, number, number, number],
    whiteColor: [number, number, number, number],
    mouthColor: [number, number, number, number],
  ): void
  /** World-space normalized camera forward vector. Used to front-face-
   *  gate the eye/mouth paint so overlay pixels don't show through
   *  the back of the head. */
  setViewForward(vx: number, vy: number, vz: number): void
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
    size: 288,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(72)
  let currentViewMode: ViewMode = 'color'
  let currentDepthOutline = true    // single depth-based outline is THE outline now
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
  // Face paint-on state: eye dots at screen-pixel offsets from the
  // (CPU-projected) head position. NOT geometry — a color override
  // inside the outline shader. Disabled when eyeEnable = 0.
  // Per-point projected positions (screen X, screen Y, NDC depth, _).
  // Demo fills them each frame from Head joint matrix + local offsets.
  let leftEye:  [number, number, number, number] = [0, 0, 0.5, 0]
  let rightEye: [number, number, number, number] = [0, 0, 0.5, 0]
  let mouth:    [number, number, number, number] = [0, 0, 0.5, 0]
  // Glyph half-extents in screen pixels (same per-eye).
  let pupilHalf: [number, number] = [0.4, 1.0]
  let whiteHalf: [number, number] = [0, 0]
  let mouthHalf: [number, number] = [1, 0.5]
  let eyeColor:   [number, number, number, number] = [0.10, 0.08, 0.20, 0]
  let whiteColor: [number, number, number, number] = [0.95, 0.92, 0.88, 0]
  let mouthColor: [number, number, number, number] = [0.55, 0.20, 0.25, 0]
  let viewForward: [number, number, number] = [0, 0, -1]

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
    // [32..35] leftEye (screenX, screenY, ndcDepth, _)
    uniformData[32] = leftEye[0];  uniformData[33] = leftEye[1]
    uniformData[34] = leftEye[2];  uniformData[35] = 0
    // [36..39] rightEye
    uniformData[36] = rightEye[0]; uniformData[37] = rightEye[1]
    uniformData[38] = rightEye[2]; uniformData[39] = 0
    // [40..43] mouth
    uniformData[40] = mouth[0];    uniformData[41] = mouth[1]
    uniformData[42] = mouth[2];    uniformData[43] = 0
    // [44..47] pupilHalf (halfW, halfH, _, _)
    uniformData[44] = pupilHalf[0]; uniformData[45] = pupilHalf[1]
    uniformData[46] = 0;            uniformData[47] = 0
    // [48..51] whiteHalf
    uniformData[48] = whiteHalf[0]; uniformData[49] = whiteHalf[1]
    uniformData[50] = 0;            uniformData[51] = 0
    // [52..55] mouthHalf
    uniformData[52] = mouthHalf[0]; uniformData[53] = mouthHalf[1]
    uniformData[54] = 0;            uniformData[55] = 0
    // [56..59] eyeColor (pupil rgb + enable)
    uniformData[56] = eyeColor[0]; uniformData[57] = eyeColor[1]
    uniformData[58] = eyeColor[2]; uniformData[59] = eyeColor[3]
    // [60..63] whiteColor
    uniformData[60] = whiteColor[0]; uniformData[61] = whiteColor[1]
    uniformData[62] = whiteColor[2]; uniformData[63] = whiteColor[3]
    // [64..67] mouthColor
    uniformData[64] = mouthColor[0]; uniformData[65] = mouthColor[1]
    uniformData[66] = mouthColor[2]; uniformData[67] = mouthColor[3]
    // [68..71] viewForward
    uniformData[68] = viewForward[0]; uniformData[69] = viewForward[1]
    uniformData[70] = viewForward[2]; uniformData[71] = 0
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
    setViewForward(vx, vy, vz) {
      viewForward[0] = vx; viewForward[1] = vy; viewForward[2] = vz
      writeUniform(currentW, currentH)
    },
    setFacePaint(lEye, rEye, mth, pHalf, wHalf, mHalf, pCol, wCol, mCol) {
      leftEye[0] = lEye[0];  leftEye[1] = lEye[1];  leftEye[2] = lEye[2];  leftEye[3] = 0
      rightEye[0] = rEye[0]; rightEye[1] = rEye[1]; rightEye[2] = rEye[2]; rightEye[3] = 0
      mouth[0] = mth[0];     mouth[1] = mth[1];     mouth[2] = mth[2];     mouth[3] = 0
      pupilHalf[0] = pHalf[0]; pupilHalf[1] = pHalf[1]
      whiteHalf[0] = wHalf[0]; whiteHalf[1] = wHalf[1]
      mouthHalf[0] = mHalf[0]; mouthHalf[1] = mHalf[1]
      eyeColor[0] = pCol[0];   eyeColor[1] = pCol[1]
      eyeColor[2] = pCol[2];   eyeColor[3] = pCol[3]
      whiteColor[0] = wCol[0]; whiteColor[1] = wCol[1]
      whiteColor[2] = wCol[2]; whiteColor[3] = wCol[3]
      mouthColor[0] = mCol[0]; mouthColor[1] = mCol[1]
      mouthColor[2] = mCol[2]; mouthColor[3] = mCol[3]
      writeUniform(currentW, currentH)
    },
  }
}

function normalize(v: [number, number, number]): [number, number, number] {
  const len = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / len, v[1] / len, v[2] / len]
}
