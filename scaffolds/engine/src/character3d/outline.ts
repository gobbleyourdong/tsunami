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
  ambient:      vec4f, // rgb = ambient color, a = intensity (applied everywhere)
  lights:       array<DirLight, 2>,  // [0] key (cel-quantized), [1] fill (half-lambert wrap)
  leftEye:      vec4f, // (screenX, screenY, ndcDepth, _) — per-point projected
  rightEye:     vec4f, //   from world-space eye/mouth positions so rotation
  mouth:        vec4f, //   (incl. upside-down) moves the paint with the head.
  pupilHalf:    vec4f, // (halfW, halfH, _, _) in pixels  (legacy, unused by stylised path)
  whiteHalf:    vec4f, // (halfW, halfH, _, _) in pixels  (legacy)
  mouthHalf:    vec4f, // (halfW, halfH, _, _) in pixels  (legacy)
  eyeColor:     vec4f, // pupil color (rgb + enable in .a)
  whiteColor:   vec4f, // eye-white color (rgb + enable in .a)
  mouthColor:   vec4f, // mouth color (rgb + enable in .a)
  viewForward:  vec4f, // camera forward (world) — extra front-face gate
  // Style-enum + per-frame state for the face pixel-stamp system.
  //   x = eyeStyleId   (0 mario, 1 dot, 2 round, 3 goggles, 4 glowing, 5 closed)
  //   y = mouthStyleId (0 off,   1 line, 2 smile, 3 open_o, 4 frown, 5 pout)
  //   z = blinkAmount  [0..1]  — when >= 0.5 the eye forces closed
  //   w = glowAmount   [0..1]  — glowing style pulses with this
  faceFlags:    vec4f,
  // Inverse view-projection matrix — used to reconstruct world position
  // from (ndc.xy, depth) for point-light evaluation. Demo updates each
  // frame from the camera. Identity (default) makes point lights useless
  // but doesn't crash.
  invViewProj:  mat4x4<f32>,
  // Active point-light count (0..MAX_POINT_LIGHTS). Loop bound in shader.
  numPointLights: u32,
  _padPL0: u32,
  _padPL1: u32,
  _padPL2: u32,
  // Up to 4 point lights — each is two vec4f packed:
  //   [2k+0] position.xyz, falloffRadius   (radius in metres; quadratic
  //                                         attenuation = 1 / (1 + (d/r)²))
  //   [2k+1] color.rgb, intensity
  pointLights: array<vec4f, 8>,
  // Face-pixel data — replaces the hardcoded mario/dot/round/goggles
  // switch in the eye/mouth stamp code with a data-driven loop. The
  // editor widget paints cells, bakes to this layout, uploads once.
  // Per pixel = vec4i: (dx, dy, paletteSlot, flags). flags lower bit
  // marks "glow_pulse" so the glowing eye style still pulses.
  // Per style = vec4i: (startIdx, count, _, _). Eye styles occupy
  // entries 0..6; mouth styles occupy 7..12. Both arrays use vec4i
  // (signed) — some Tint validator builds reject dynamic indexing
  // into uniform array<vec4u> while accepting array<vec4i>.
  faceStyles: array<vec4i, 16>,
  facePixels: array<vec4i, 64>,
  // Optional secondary palette colours used by stylised eyes (goggles frame,
  // glowing inner core). rgb + enable in .a.
  eyeAccent:    vec4f,
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
  // (Note: modeler_demo.ts has its own lit pass that overrides this for
  // screenshotView; this branch only fires for outline.ts's lit pipeline.)
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
  // Albedo passed forward to the final multiply. Defaults to the raw
  // raymarch tint; the cel pass below substitutes a saturation-boosted
  // version on the shadow side (color-burn vibe — deeper, richer
  // shadows that pull the underlying colour rather than just dimming).
  var useAlbedo = me.rgb;
  // Per-primitive unlit flag (depth.g) — pixels marked unlit by the
  // raymarch pass skip ALL lighting and render with their authored
  // palette colour unchanged. For VFX (flames, lightning, beams,
  // magic glow) which carry their own emissive tones.
  let unlitFlag = textureLoad(depthTex, pxClamp, 0).g > 0.5;
  // u.lighting modes: 0 = off (flat unlit), 1 = on (ambient + key
  // directional + active point lights, all summed). Two-tone cel:
  // lit pixels get ambient + key, shadow pixels get just ambient.
  // Point lights are transient (spawned by VFX for muzzle flashes etc.)
  // and add their contribution on top of directional.
  if (u.lighting > 0.5 && me.a > 0.5 && !unlitFlag) {
    // Two-tone cel. ambient + key, that's it.
    //   shadow: ambient                 (cool baseline)
    //   lit:    ambient + keyContrib    (warm bright when n·keyDir > 0)
    // No fill, no specular by default. Point lights add transient
    // contribution on top when VFX spawns them.
    let normalSample = textureLoad(normalTex, pxClamp, 0);
    let n = normalize(normalSample.xyz * 2.0 - 1.0);
    let isShiny = normalSample.a > 0.5;     // per-primitive flag, packed by raymarch

    let ambColor = u.ambient.rgb * u.ambient.a;

    let keyDir = u.lights[0].dirI.xyz;
    let keyInt = u.lights[0].dirI.w;
    let keyCol = u.lights[0].color.rgb;
    let keyDot = dot(n, keyDir);
    let keyContrib = select(vec3f(0.0), keyCol * keyInt, keyDot > 0.0);

    // Color-burn-style saturation boost on the shadow side. Extrapolate
    // the albedo away from its grayscale luminance so each colour pulls
    // deeper toward its hue instead of just dimming flatly. mix(gray,
    // albedo, t > 1.0) past-1 amounts gives an out-of-gamut bias that
    // we clamp into [0, 1] — most albedos stay in range; pure-saturated
    // ones clamp at their max which is fine.
    let lumaGray = vec3f(dot(me.rgb, vec3f(0.299, 0.587, 0.114)));
    let satAlbedo = clamp(mix(lumaGray, me.rgb, 1.2), vec3f(0.0), vec3f(1.0));
    useAlbedo = select(satAlbedo, me.rgb, keyDot > 0.0);

    var pointContrib = vec3f(0.0);
    // Point lights — transient sources spawned by VFX (muzzle flashes,
    // flares, explosion bursts). Loop runs whenever any are active.
    if (u.numPointLights > 0u) {
      // World-pos reconstruction. The depth buffer packs t/totalDist
      // (LINEAR ray fraction from raymarch) — NOT NDC z. So we cannot
      // feed it to invViewProj as the z coordinate.
      //
      // Same near/far interpolation the raymarch already uses:
      //   ro    = invViewProj × (ndc, 0, 1)   → camera near point
      //   farW  = invViewProj × (ndc, 1, 1)   → camera far point
      //   rdRaw = farW - ro                   → world span across this ray
      //   worldPos = ro + rdRaw × (t/totalDist)
      // Because the raymarch's totalDist == length(rdRaw), multiplying
      // by the linear fraction recovers the exact hit position.
      let ndcX = uv.x * 2.0 - 1.0;
      let ndcY = (1.0 - uv.y) * 2.0 - 1.0;
      let depthLinear = textureLoad(depthTex, pxClamp, 0).r;
      let nearW = u.invViewProj * vec4f(ndcX, ndcY, 0.0, 1.0);
      let farW  = u.invViewProj * vec4f(ndcX, ndcY, 1.0, 1.0);
      let ro    = nearW.xyz / nearW.w;
      let rdRaw = farW.xyz / farW.w - ro;
      let worldPos = ro + rdRaw * depthLinear;

      for (var i = 0u; i < u.numPointLights; i = i + 1u) {
        let pl0 = u.pointLights[i * 2u + 0u];
        let pl1 = u.pointLights[i * 2u + 1u];
        let lightPos = pl0.xyz;
        let radius   = max(pl0.w, 0.001);
        let lightCol = pl1.rgb;
        let lightInt = pl1.a;
        let toLight  = lightPos - worldPos;
        let dist     = length(toLight);
        let lightDir = toLight / max(dist, 0.001);
        // Cel-quantized falloff: hard cutoff at the radius (one ring),
        // cel-quantized n·l (one terminator line). Result is at most
        // two clean transition lines on the body — no smooth gradient,
        // no per-pixel falloff blur. Matches the cel-shading discipline
        // of the rest of the pipeline.
        let inRange = dist < radius;
        let nDotL   = dot(n, lightDir) > 0.0;
        let cellOn  = inRange && nDotL;
        pointContrib = pointContrib + select(vec3f(0.0), lightCol * lightInt, cellOn);
      }
    }

    // Selective specular: shiny primitives get a tight hot-spot from the
    // key light when n·keyDir crosses 0.85. Tinted by key colour. Matte
    // primitives skip this entirely. Single binary per-primitive choice
    // — replaces the old roughness scalar with simpler authoring.
    var specContrib = vec3f(0.0);
    if (isShiny && keyDot > 0.85) {
      specContrib = keyCol * keyInt * 0.9;
    }

    lit = ambColor + keyContrib + pointContrib + specContrib;
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

  // Stylised eye stamp. Each eye has an anchor in screen pixels + a
  // local (dx, dy) offset from that anchor. Blink forces "closed" when
  // faceFlags.z >= 0.5. Styles encoded in faceFlags.x:
  //   0 mario    — 2×3, outer white column, inner W/B/B pupil pillar
  //   1 dot      — single black pixel at anchor
  //   2 round    — 2×2 solid pupil
  //   3 goggles  — 3×3, outline rim (accent), inner white, tiny pupil
  //   4 glowing  — 2×2 accent glow + 1×1 bright core (pulses on faceFlags.w)
  //   5 closed   — 2×1 horizontal line (also the forced blink pose)
  //   6 crying   — closed line + 2-px cyan tear stream on the inner column
  //
  // The demo places left and right anchors symmetrically along the
  // head-right screen axis; per-eye isRight lets a style draw mirrored
  // patterns when they're asymmetric. dx convention for the MARIO case:
  // left eye block extends to the right of anchor (dx in 0..+1); right
  // eye block extends to the left (dx in -1..0). Other styles are
  // symmetric and ignore the mirror.
  // Data-driven face stamp. Each style is a list of (dx, dy, slot)
  // pixels stored in u.facePixels. u.faceStyles[styleId] holds the
  // (start, count) into that array. The editor widget bakes pixel
  // grids into this layout. Existing styles (mario / dot / round /
  // goggles / glowing / closed / crying) are pre-loaded as data —
  // identical visual output.
  //
  // Slot semantics inside the stamp:
  //   0 = pupil     → u.eyeColor.rgb
  //   1 = eyewhite  → u.whiteColor.rgb
  //   2 = accent    → u.eyeAccent.rgb
  //   3 = tear      → cyan (0.35, 0.70, 1.0)
  //   4 = glow_core → mix(accent, white, glow)  (pulses with faceFlags.w)
  //   5 = mouth     → u.mouthColor.rgb
  if (frontFacing && u.eyeColor.a > 0.5) {
    var eyeStyle = u32(u.faceFlags.x);
    if (u.faceFlags.z >= 0.5) { eyeStyle = 5u; }   // blink override → CLOSED
    let leftPx  = vec2i(i32(round(u.leftEye.x)),  i32(round(u.leftEye.y)));
    let rightPx = vec2i(i32(round(u.rightEye.x)), i32(round(u.rightEye.y)));
    let lInDepth = abs(pixelDepth - u.leftEye.z)  < depthTol;
    let rInDepth = abs(pixelDepth - u.rightEye.z) < depthTol;
    let glow = clamp(u.faceFlags.w, 0.0, 1.0);
    // Variable named eMeta — WGSL reserves the bare word "meta".
    let eMeta = u.faceStyles[eyeStyle];
    let startIdx = u32(eMeta.x);
    let count = u32(eMeta.y);

    for (var side = 0u; side < 2u; side = side + 1u) {
      let isLeft = side == 0u;
      let anchor = select(rightPx, leftPx, isLeft);
      let inDepth = select(rInDepth, lInDepth, isLeft);
      if (!inDepth) { continue; }
      let dx = px.x - anchor.x;
      let dy = px.y - anchor.y;
      for (var i = 0u; i < count; i = i + 1u) {
        let pixel = u.facePixels[startIdx + i];
        // Right-eye mirror: negate the authored dx so a style whose
        // outer column is at dx=+1 (left eye) becomes dx=-1 (right eye).
        let pdx = select(-pixel.x, pixel.x, isLeft);
        let pdy = pixel.y;
        if (dx == pdx && dy == pdy) {
          let slot = u32(pixel.z);
          if      (slot == 0u) { return vec4f(u.eyeColor.rgb, 1.0); }
          else if (slot == 1u) { return vec4f(u.whiteColor.rgb, 1.0); }
          else if (slot == 2u) { return vec4f(u.eyeAccent.rgb, 1.0); }
          else if (slot == 3u) { return vec4f(0.35, 0.70, 1.0, 1.0); }
          else if (slot == 4u) { return vec4f(mix(u.eyeAccent.rgb, vec3f(1.0), glow), 1.0); }
          else if (slot == 5u) { return vec4f(u.mouthColor.rgb, 1.0); }
        }
      }
    }
  }

  // Mouth style stamp — screen-space pixel pattern at the mouth anchor.
  // Styles (faceFlags.y):
  //   0 off      — no mouth drawn
  //   1 line     — 3×1 horizontal line
  //   2 smile    — 3×1 line with dip at center (3×2 half-smile curve)
  //   3 open_o   — 2×2 filled square (surprise / wide mouth)
  //   4 frown    — 3×1 line with rise at center (upside-down smile)
  //   5 pout     — 1×1 dot
  if (frontFacing && u.mouthColor.a > 0.5) {
    let style = u32(u.faceFlags.y);
    // Mouth styles also data-driven. Stored at faceStyles[7..12] with
    // styleId offset by NUM_EYE_STYLES (= 7).
    if (style != 0u) {
      let mPx = vec2i(i32(round(u.mouth.x)), i32(round(u.mouth.y)));
      let mInDepth = abs(pixelDepth - u.mouth.z) < depthTol;
      if (mInDepth) {
        let dx = px.x - mPx.x;
        let dy = px.y - mPx.y;
        let mMeta = u.faceStyles[7u + style];
        let mStart = u32(mMeta.x);
        let mCount = u32(mMeta.y);
        for (var i = 0u; i < mCount; i = i + 1u) {
          let pixel = u.facePixels[mStart + i];
          if (dx == pixel.x && dy == pixel.y) {
            let slot = u32(pixel.z);
            if      (slot == 0u) { return vec4f(u.eyeColor.rgb, 1.0); }
            else if (slot == 5u) { return vec4f(u.mouthColor.rgb, 1.0); }
            else                 { return vec4f(u.mouthColor.rgb, 1.0); }
          }
        }
      }
    }
  }

  return vec4f(useAlbedo * lit, 1.0);
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
  /** Face style + state. eyeStyle/mouthStyle are enum IDs matching the
   *  shader switch (see U.faceFlags in the WGSL). blink in [0..1] — when
   *  >=0.5 all eye styles snap to the closed pose. glow in [0..1] —
   *  used by glowing/animated styles to pulse. */
  setFaceStyle(
    eyeStyle: number,
    mouthStyle: number,
    blink: number,
    glow: number,
  ): void
  /** Accent colour for stylised eyes (goggles rim, glowing outer).
   *  rgb + enable(.a > 0.5). */
  setEyeAccent(color: [number, number, number, number]): void
  /** Camera inverse-view-projection (column-major mat4). Required for
   *  point lights — used to reconstruct world position from depth. */
  setInvViewProj(m: Float32Array): void
  /** Configure a point light. idx in [0, 4). Pass intensity = 0 to
   *  disable that slot. Falloff is quadratic: atten = 1 / (1 + (d/radius)²). */
  setPointLight(
    idx: number,
    pos: [number, number, number],
    color: [number, number, number],
    intensity: number,
    radius: number,
  ): void
  /** Active point-light count [0..4]. Above this index, slots are skipped. */
  setNumPointLights(n: number): void
  /** Upload face-pixel data for the data-driven eye/mouth stamp.
   *  styles: per-style (startIdx, count) — eye styles at 0..6, mouth at 7..12.
   *  pixels: flat array of (dx, dy, slotId, flags) tuples.
   *  Bake button in the editor calls this to push edits to GPU. */
  setFacePixelData(styles: Int32Array, pixels: Int32Array): void
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
    size: 1808,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(452)
  const uniformDataU32 = new Uint32Array(uniformData.buffer)
  const uniformDataI32 = new Int32Array(uniformData.buffer)
  let currentViewMode: ViewMode = 'color'
  let currentDepthOutline = true    // single depth-based outline is THE outline now
  let currentDepthThresh = 0.025
  // 0 = off, 1 = MRT normal (authoritative), 2 = reconstructed from depth
  let currentLightingMode: 0 | 1 = 0
  let currentW = sceneW
  let currentH = sceneH
  // Default rig: cool ambient + warm key (3/4 front) + cool fill (back).
  // Directions are TO the light source (what the shader dots against).
  // Key directional is pure white — no hue shift on the lit side. Ambient
  // keeps a faint cool bias as a subtle atmospheric baseline; can flip
  // to fully neutral or sunrise-warm later when the day/night cycle
  // lands and colored lights matter for time-of-day mood.
  let ambient = { r: 0.85, g: 0.86, b: 0.90, intensity: 0.55 }
  let lights: { dir: [number, number, number]; intensity: number; color: [number, number, number] }[] = [
    { dir: normalize([0.6, 0.7, 0.3]),   intensity: 0.55, color: [1.00, 1.00, 1.00] },
    { dir: normalize([-0.4, 0.3, -0.6]), intensity: 0.0,  color: [1.00, 1.00, 1.00] },  // fill: unused, reserved for layout
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
  // Face style state. faceFlags = (eyeStyleId, mouthStyleId, blink01, glow01)
  let faceFlags:  [number, number, number, number] = [0, 0, 0, 0]
  // Secondary palette colour used by goggles rim / glowing outer glow.
  let eyeAccent:  [number, number, number, number] = [0.2, 0.6, 1.0, 0]
  // Camera invViewProj, set by demo each frame for point-light world-pos
  // reconstruction. Default = identity (point lights inert until set).
  const invViewProj = new Float32Array(16)
  invViewProj[0] = 1; invViewProj[5] = 1; invViewProj[10] = 1; invViewProj[15] = 1
  // Point lights: up to 4. Each = (pos.xyz, radius), (color.rgb, intensity).
  const MAX_POINT_LIGHTS = 4
  let numPointLights = 0
  const pointLights = new Float32Array(MAX_POINT_LIGHTS * 8)
  // Face-pixel data (data-driven eye/mouth stamps). Editor populates this.
  // faceStyles[i] = (startIdx, count, _, _) for style i (eye 0..6, mouth 7..12).
  // facePixels[k] = (dx, dy, slot, flags) for pixel k.
  const MAX_FACE_PIXELS = 64
  const MAX_FACE_STYLES = 16
  const faceStyles = new Int32Array(MAX_FACE_STYLES * 4)   // u32 in shader; using i32 view for write
  const facePixels = new Int32Array(MAX_FACE_PIXELS * 4)

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
    // [72..75] faceFlags (eyeStyleId, mouthStyleId, blink01, glow01)
    uniformData[72] = faceFlags[0]; uniformData[73] = faceFlags[1]
    uniformData[74] = faceFlags[2]; uniformData[75] = faceFlags[3]
    // Layout MUST match the WGSL U struct after faceFlags:
    //   invViewProj   (mat4, 16 floats) → bytes 304-368, slots 76-91
    //   numPointLights (u32, 1 word)    → byte 368, slot 92
    //   _padPL[3]     (3×u32 align pad) → bytes 372-384, slots 93-95
    //   pointLights   (8×vec4f, 32f)    → bytes 384-512, slots 96-127
    //   eyeAccent     (vec4f, 4 floats) → bytes 512-528, slots 128-131
    // Earlier layout had eyeAccent at slot 76 — that broke when point
    // lights pushed it to the END of the struct. Fixing now.
    // Layout (post-faceStyles/facePixels expansion):
    //   invViewProj   (mat4, 16f) → slots 76-91, bytes 304-368
    //   numPointLights u32        → slot 92, byte 368
    //   _padPL[3]                 → slots 93-95
    //   pointLights   (8×vec4)    → slots 96-127, bytes 384-512
    //   faceStyles    (16×vec4i)  → slots 128-191, bytes 512-768
    //   facePixels    (64×vec4i)  → slots 192-447, bytes 768-1792
    //   eyeAccent     (vec4f)     → slots 448-451, bytes 1792-1808
    uniformData.set(invViewProj, 76)
    uniformDataU32[92] = numPointLights
    uniformData[93] = 0; uniformData[94] = 0; uniformData[95] = 0
    uniformData.set(pointLights, 96)
    // faceStyles is i32 in shader (vec4i). The runtime Int32Array view
    // is its native type — write through uniformDataI32. Values stay
    // positive in practice (start/count are non-negative) so the
    // signed/unsigned bit pattern is identical.
    for (let i = 0; i < faceStyles.length; i++) uniformDataI32[128 + i] = faceStyles[i]
    // facePixels is i32 (signed dx/dy can be negative).
    for (let i = 0; i < facePixels.length; i++) uniformDataI32[192 + i] = facePixels[i]
    uniformData[448] = eyeAccent[0]; uniformData[449] = eyeAccent[1]
    uniformData[450] = eyeAccent[2]; uniformData[451] = eyeAccent[3]
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
    setFaceStyle(eyeStyle, mouthStyle, blink, glow) {
      faceFlags[0] = eyeStyle
      faceFlags[1] = mouthStyle
      faceFlags[2] = blink
      faceFlags[3] = glow
      writeUniform(currentW, currentH)
    },
    setEyeAccent(color) {
      eyeAccent[0] = color[0]; eyeAccent[1] = color[1]
      eyeAccent[2] = color[2]; eyeAccent[3] = color[3]
      writeUniform(currentW, currentH)
    },
    setInvViewProj(m) {
      invViewProj.set(m)
      writeUniform(currentW, currentH)
    },
    setPointLight(idx, pos, color, intensity, radius) {
      if (idx < 0 || idx >= MAX_POINT_LIGHTS) return
      const off = idx * 8
      pointLights[off + 0] = pos[0]
      pointLights[off + 1] = pos[1]
      pointLights[off + 2] = pos[2]
      pointLights[off + 3] = radius
      pointLights[off + 4] = color[0]
      pointLights[off + 5] = color[1]
      pointLights[off + 6] = color[2]
      pointLights[off + 7] = intensity
      writeUniform(currentW, currentH)
    },
    setNumPointLights(n) {
      numPointLights = Math.max(0, Math.min(MAX_POINT_LIGHTS, n))
      writeUniform(currentW, currentH)
    },
    setFacePixelData(styles, pixels) {
      // Copy into the persistent buffers, padding the rest with zeros so
      // stale tail-data from a previous style set doesn't bleed into the
      // shader (zero `count` skips that style's loop entirely).
      faceStyles.fill(0)
      facePixels.fill(0)
      faceStyles.set(styles.subarray(0, Math.min(styles.length, faceStyles.length)))
      facePixels.set(pixels.subarray(0, Math.min(pixels.length, facePixels.length)))
      writeUniform(currentW, currentH)
    },
  }
}

function normalize(v: [number, number, number]): [number, number, number] {
  const len = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / len, v[1] / len, v[2] / len]
}
