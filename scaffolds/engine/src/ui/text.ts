/**
 * Text renderer — public interface + StubTextRenderer (fallback) +
 * HermiteTextRenderer (real WebGPU implementation, Sample Newton).
 *
 * # Status — full pipeline landed; awaiting hardware validation
 *   Public interface            ✓ stable (additive extensions only)
 *   StubTextRenderer            ✓ fallback for non-GPU paths
 *   HermiteTextRenderer         ✓ atlas upload + quad batcher (fire 2)
 *   loadFontAtlas helper        ✓ fetches .bin + .json + contour_breaks
 *   Shader — outline polyline   ✓ fire 3 (superseded by fire 4)
 *   Shader — contour breaks     ✓ fire 4 (storage buffer binding 3)
 *   Shader — Sample Newton      ✓ fire 4 (5-sample init + 4 Newton steps)
 *   Shader — signed distance    ✓ fire 4 (tangent-perp cross-product sign)
 *   Shader — interior fill + AA ✓ fire 4 (fwidth(signed_dist) smoothstep)
 *   Demo                        ✓ fire 5 (`demos/text_demo.{ts,html}`)
 *
 * # Awaiting hardware validation
 *   - Winding-sign convention: if glyphs render inverted, flip
 *     `cross_z > 0.0` → `< 0.0` in text_shader.ts fs_main.
 *   - Newton convergence at cusps / T-junctions (watch edges for flicker).
 *   - fwidth AA band: may need tuning if the edge looks too wide / narrow.
 *   - Perf target: 60 FPS with 200+ glyphs.
 *
 * Zero-dep runtime (pure WebGPU + TS). Build-time baker lives at
 * `tools/font_bake.py`.
 */

import type { Vec2 } from '../math/vec'
import type { GPUContext } from '../renderer/gpu'
import { TEXT_SHADER_WGSL } from './text_shader'

// ═════════════════════════════════════════════════════════════════
// PUBLIC INTERFACE (stable — extensions are additive / optional)
// ═════════════════════════════════════════════════════════════════

/**
 * Atlas produced by the font baker (`tools/font_bake.py`). One texture
 * + per-codepoint metrics. Variant atlases (bold / italic / display)
 * are loaded under distinct names via `load_atlas(name, atlas)`.
 */
export interface FontAtlas {
  /** Atlas texture. For Sample Newton baker: rgba32float, row-per-glyph,
   * each texel = (anchor.x, anchor.y, tangent.x, tangent.y) in em units.
   */
  texture: GPUTexture
  /** Per-codepoint metrics. */
  metrics: GlyphMetricsTable
  /** Distance-field pixel range baked into the atlas (MSDF-style).
   * Reserved; unused by Sample Newton. Default 4 if present. */
  distance_range: number
  /** Font-level metrics in em units. */
  ascent: number
  descent: number
  line_gap: number
  /** Pixels per em in the baked atlas. */
  em_size: number
  /** Flat u32 storage buffer: all glyphs' contour_breaks concatenated.
   * Indexed per-glyph via GlyphMetrics.cb_start + cb_count. */
  contour_breaks_buf?: GPUBuffer
}

export interface GlyphMetrics {
  /** Atlas UV rect: [u0, v0, u1, v1] in 0..1 (MSDF-style).
   * For Sample Newton, may be [0,0,0,0] — use row + handle_count instead. */
  uv: [number, number, number, number]
  /** Plane rect in em units: [left, top, right, bottom]. */
  plane: [number, number, number, number]
  /** Horizontal advance in em units. */
  advance: number

  // ── Sample Newton additions (optional; produced by tools/font_bake.py) ──
  /** Atlas row for this glyph's handle strip. */
  row?: number
  /** Number of Hermite handles in this glyph's strip. */
  handle_count?: number
  /** Indices in handles[] where one contour ends + next begins.
   * Multi-contour glyphs (O, B, 8) have non-empty lists. */
  contour_breaks?: number[]
  /** Offset into atlas's flat contour_breaks buffer (GPU-side). */
  cb_start?: number
  /** Number of breaks for this glyph in the flat buffer. */
  cb_count?: number
}

/** Codepoint → metrics. */
export type GlyphMetricsTable = Record<number, GlyphMetrics>

// ── Text style ───────────────────────────────────────────────────

export interface TextStyle {
  /** RGBA 0..1. */
  color: [number, number, number, number]
  /** Pixel size (atlas em scales to this). */
  size: number
  /** Select an atlas variant (must be pre-loaded). Default 'regular'. */
  atlas?: string
  /** Extra horizontal spacing in pixels. Default 0. */
  letter_spacing?: number
  /** Line height as multiplier of size. Default 1.2. */
  line_height?: number
}

export interface TextMeasurement {
  width: number
  height: number
  line_count: number
}

export interface TextRenderer {
  load_atlas(name: string, atlas: FontAtlas): void
  begin(pass: GPURenderPassEncoder, viewport: { width: number; height: number }): void
  draw(text: string, pos: Vec2, style: TextStyle): void
  measure(text: string, style: TextStyle): TextMeasurement
  end(): void
  destroy(): void
}

// ═════════════════════════════════════════════════════════════════
// StubTextRenderer — fallback, non-drawing
// ═════════════════════════════════════════════════════════════════

export class StubTextRenderer implements TextRenderer {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_gpu: GPUContext) {}
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  load_atlas(_name: string, _atlas: FontAtlas): void {}
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  begin(_pass: GPURenderPassEncoder, _viewport: { width: number; height: number }): void {}
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  draw(_text: string, _pos: Vec2, _style: TextStyle): void {}
  measure(text: string, style: TextStyle): TextMeasurement {
    const per_glyph = style.size * 0.55 + (style.letter_spacing ?? 0)
    const line_height = style.size * (style.line_height ?? 1.2)
    const lines = text.split('\n')
    const width = lines.reduce((m, l) => Math.max(m, l.length * per_glyph), 0)
    return { width, height: lines.length * line_height, line_count: lines.length }
  }
  end(): void {}
  destroy(): void {}
}

// ═════════════════════════════════════════════════════════════════
// HermiteTextRenderer — real WebGPU implementation
// ═════════════════════════════════════════════════════════════════

// Per-instance buffer layout, matches `Instance` struct in text_shader.ts.
// 16 floats = 64 bytes:
//   pos.xy (8) + size (4) + _pad0 (4) + color.rgba (16) + plane.ltrb (16)
//   + atlas_row (u32, 4) + handle_count (u32, 4) + _pad1 (u32,u32 = 8)
const INSTANCE_STRIDE_BYTES = 64
const MAX_INSTANCES = 4096  // 256 KiB — ample for any single-frame text load

// Uniforms layout:
//   viewport.xy (8) + em_size (4) + distance_range (4) = 16 bytes
const UNIFORM_SIZE_BYTES = 16

export class HermiteTextRenderer implements TextRenderer {
  private gpu: GPUContext
  private atlases = new Map<string, FontAtlas>()
  private pipeline: GPURenderPipeline | null = null
  private bind_layout: GPUBindGroupLayout | null = null

  // Per-frame state
  private pass: GPURenderPassEncoder | null = null
  private viewport: { width: number; height: number } = { width: 1, height: 1 }
  private current_atlas_name = 'regular'

  // Instance buffer (CPU-staged, uploaded per-frame)
  private instance_buf: GPUBuffer
  private instance_arr: ArrayBuffer
  private instance_view: DataView
  private instance_count = 0

  // Uniforms
  private uniform_buf: GPUBuffer

  constructor(gpu: GPUContext) {
    this.gpu = gpu

    this.instance_buf = gpu.device.createBuffer({
      size: MAX_INSTANCES * INSTANCE_STRIDE_BYTES,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      label: 'text:instances',
    })
    this.instance_arr = new ArrayBuffer(MAX_INSTANCES * INSTANCE_STRIDE_BYTES)
    this.instance_view = new DataView(this.instance_arr)

    this.uniform_buf = gpu.device.createBuffer({
      size: UNIFORM_SIZE_BYTES,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      label: 'text:uniforms',
    })

    this.build_pipeline()
  }

  private build_pipeline(): void {
    const device = this.gpu.device

    this.bind_layout = device.createBindGroupLayout({
      label: 'text:bind-layout',
      entries: [
        {
          binding: 0,
          visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
          buffer: { type: 'uniform' },
        },
        // rgba32float is non-filterable; we use textureLoad (exact texel fetch).
        {
          binding: 1,
          visibility: GPUShaderStage.FRAGMENT,
          texture: { sampleType: 'unfilterable-float', viewDimension: '2d' },
        },
        // Per-frame instance data (vertex + fragment both read cb_start/cb_count).
        {
          binding: 2,
          visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
          buffer: { type: 'read-only-storage' },
        },
        // Flat contour_breaks u32 array for the currently-active atlas.
        {
          binding: 3,
          visibility: GPUShaderStage.FRAGMENT,
          buffer: { type: 'read-only-storage' },
        },
      ],
    })

    const pipeline_layout = device.createPipelineLayout({
      label: 'text:pipeline-layout',
      bindGroupLayouts: [this.bind_layout],
    })

    const module = device.createShaderModule({
      label: 'text:shader',
      code: TEXT_SHADER_WGSL,
    })

    this.pipeline = device.createRenderPipeline({
      label: 'text:pipeline',
      layout: pipeline_layout,
      vertex: { module, entryPoint: 'vs_main' },
      fragment: {
        module,
        entryPoint: 'fs_main',
        targets: [
          {
            format: this.gpu.format,
            blend: {
              color: {
                srcFactor: 'src-alpha',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
              alpha: {
                srcFactor: 'one',
                dstFactor: 'one-minus-src-alpha',
                operation: 'add',
              },
            },
          },
        ],
      },
      primitive: { topology: 'triangle-strip', stripIndexFormat: 'uint32' },
      // No depth: text is an overlay pass.
    })
  }

  load_atlas(name: string, atlas: FontAtlas): void {
    this.atlases.set(name, atlas)
  }

  begin(pass: GPURenderPassEncoder, viewport: { width: number; height: number }): void {
    this.pass = pass
    this.viewport = viewport
    this.instance_count = 0
    this.current_atlas_name = 'regular'
  }

  draw(text: string, pos: Vec2, style: TextStyle): void {
    if (!this.pass) {
      console.warn('HermiteTextRenderer.draw called outside begin/end')
      return
    }
    const atlas_name = style.atlas ?? 'regular'
    const atlas = this.atlases.get(atlas_name)
    if (!atlas) {
      console.warn(`text: atlas '${atlas_name}' not loaded`)
      return
    }

    const color = style.color
    const size = style.size
    const line_height = style.size * (style.line_height ?? 1.2)
    const letter_spacing = style.letter_spacing ?? 0

    let cursor_x = pos[0]
    let cursor_y = pos[1]

    for (let i = 0; i < text.length; i++) {
      const code = text.codePointAt(i)!
      if (code >= 0x10000) i++  // advance past low surrogate

      if (code === 0x0A /* \n */) {
        cursor_x = pos[0]
        cursor_y += line_height
        continue
      }

      const g = atlas.metrics[code]
      if (!g) {
        cursor_x += size * 0.3  // missing-glyph stride
        continue
      }

      // Require Sample Newton metadata to draw. Advance-only for the rest.
      if (g.row === undefined || g.handle_count === undefined || g.handle_count === 0) {
        cursor_x += g.advance * size + letter_spacing
        continue
      }

      if (this.instance_count >= MAX_INSTANCES) {
        console.warn('HermiteTextRenderer: instance buffer full')
        break
      }

      this.write_instance(
        this.instance_count,
        cursor_x, cursor_y,
        size,
        color,
        g.plane,
        g.row,
        g.handle_count,
        g.cb_start ?? 0,
        g.cb_count ?? 0,
      )
      this.instance_count++

      cursor_x += g.advance * size + letter_spacing
      this.current_atlas_name = atlas_name
    }
  }

  private write_instance(
    idx: number,
    px: number, py: number,
    size: number,
    color: [number, number, number, number],
    plane: [number, number, number, number],
    row: number,
    handle_count: number,
    cb_start: number,
    cb_count: number,
  ): void {
    const off = idx * INSTANCE_STRIDE_BYTES
    const v = this.instance_view
    // pos.xy
    v.setFloat32(off + 0, px, true)
    v.setFloat32(off + 4, py, true)
    // size
    v.setFloat32(off + 8, size, true)
    // _pad0
    v.setFloat32(off + 12, 0, true)
    // color.rgba
    v.setFloat32(off + 16, color[0], true)
    v.setFloat32(off + 20, color[1], true)
    v.setFloat32(off + 24, color[2], true)
    v.setFloat32(off + 28, color[3], true)
    // plane.ltrb
    v.setFloat32(off + 32, plane[0], true)
    v.setFloat32(off + 36, plane[1], true)
    v.setFloat32(off + 40, plane[2], true)
    v.setFloat32(off + 44, plane[3], true)
    // atlas_row (u32)
    v.setUint32(off + 48, row, true)
    // handle_count (u32)
    v.setUint32(off + 52, handle_count, true)
    // cb_start (u32)  — offset into atlas contour_breaks buffer
    v.setUint32(off + 56, cb_start, true)
    // cb_count (u32)  — # breaks for this glyph
    v.setUint32(off + 60, cb_count, true)
  }

  end(): void {
    if (!this.pass || !this.pipeline || !this.bind_layout) return
    if (this.instance_count === 0) {
      this.pass = null
      return
    }

    const device = this.gpu.device
    const atlas = this.atlases.get(this.current_atlas_name)
    if (!atlas) {
      this.pass = null
      return
    }

    // Uniforms
    const uniforms = new ArrayBuffer(UNIFORM_SIZE_BYTES)
    const uview = new DataView(uniforms)
    uview.setFloat32(0, this.viewport.width, true)
    uview.setFloat32(4, this.viewport.height, true)
    uview.setFloat32(8, atlas.em_size, true)
    uview.setFloat32(12, atlas.distance_range, true)
    device.queue.writeBuffer(this.uniform_buf, 0, uniforms)

    // Instance slice
    device.queue.writeBuffer(
      this.instance_buf,
      0,
      this.instance_arr,
      0,
      this.instance_count * INSTANCE_STRIDE_BYTES,
    )

    const bind_group = device.createBindGroup({
      layout: this.bind_layout,
      entries: [
        { binding: 0, resource: { buffer: this.uniform_buf } },
        { binding: 1, resource: atlas.texture.createView() },
        { binding: 2, resource: { buffer: this.instance_buf } },
        { binding: 3, resource: { buffer: atlas.contour_breaks_buf! } },
      ],
    })

    this.pass.setPipeline(this.pipeline)
    this.pass.setBindGroup(0, bind_group)
    // Quad: 4 verts, triangle-strip (0,0 → 1,0 → 0,1 → 1,1)
    this.pass.draw(4, this.instance_count, 0, 0)

    this.pass = null
  }

  measure(text: string, style: TextStyle): TextMeasurement {
    const atlas = this.atlases.get(style.atlas ?? 'regular')
    if (!atlas) {
      // Fall back to stub heuristic before atlas arrives.
      return new StubTextRenderer(this.gpu).measure(text, style)
    }
    const letter_spacing = style.letter_spacing ?? 0
    const line_height = style.size * (style.line_height ?? 1.2)
    const lines = text.split('\n')
    let max_w = 0
    for (const line of lines) {
      let w = 0
      for (let i = 0; i < line.length; i++) {
        const code = line.codePointAt(i)!
        if (code >= 0x10000) i++
        const g = atlas.metrics[code]
        w += (g?.advance ?? 0.3) * style.size + letter_spacing
      }
      if (w > max_w) max_w = w
    }
    return { width: max_w, height: lines.length * line_height, line_count: lines.length }
  }

  destroy(): void {
    this.instance_buf.destroy()
    this.uniform_buf.destroy()
    for (const atlas of this.atlases.values()) {
      atlas.contour_breaks_buf?.destroy()
    }
    this.atlases.clear()
    this.pipeline = null
  }
}

// ═════════════════════════════════════════════════════════════════
// loadFontAtlas — fetch .atlas.bin + .atlas.json, upload to GPU
// ═════════════════════════════════════════════════════════════════

/**
 * Loads a baked atlas (produced by `tools/font_bake.py`) from a URL
 * prefix. Expects:
 *   {prefix}.atlas.bin   RGBA32F raw texels, row-per-glyph
 *   {prefix}.atlas.json  metadata
 *
 * Example:
 *   const atlas = await loadFontAtlas(gpu, '/fonts/inter-regular')
 *   renderer.load_atlas('regular', atlas)
 */
export async function loadFontAtlas(
  gpu: GPUContext,
  prefix: string,
): Promise<FontAtlas> {
  const [bin_buf, meta] = await Promise.all([
    fetch(`${prefix}.atlas.bin`).then(r => r.arrayBuffer()),
    fetch(`${prefix}.atlas.json`).then(r => r.json()),
  ])

  const W = meta.atlas_width as number
  const H = meta.atlas_height as number

  const texture = gpu.device.createTexture({
    label: `font:${prefix}`,
    size: { width: W, height: H, depthOrArrayLayers: 1 },
    format: 'rgba32float',
    usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
  })

  const bytes_per_row = W * 16  // rgba32float = 16 bytes per texel
  gpu.device.queue.writeTexture(
    { texture },
    bin_buf,
    { offset: 0, bytesPerRow: bytes_per_row, rowsPerImage: H },
    { width: W, height: H, depthOrArrayLayers: 1 },
  )

  // Assemble flat contour_breaks buffer across all glyphs. Per-glyph
  // metadata gets (cb_start, cb_count) indices into this buffer.
  const breaks_flat: number[] = []
  const metrics: GlyphMetricsTable = {}
  for (const [cp_str, g] of Object.entries(meta.glyphs as Record<string, any>)) {
    const cp = Number(cp_str)
    const breaks: number[] = (g.contour_breaks as number[]) ?? []
    const cb_start = breaks_flat.length
    for (const b of breaks) breaks_flat.push(b)
    metrics[cp] = {
      uv: [0, 0, 0, 0],                    // Sample Newton doesn't use uv
      plane: g.plane as [number, number, number, number],
      advance: g.advance as number,
      row: g.row as number,
      handle_count: g.handle_count as number,
      contour_breaks: breaks,
      cb_start,
      cb_count: breaks.length,
    }
  }

  // Storage buffer min size 16 bytes; pad if empty.
  const cb_array = new Uint32Array(Math.max(breaks_flat.length, 4))
  cb_array.set(breaks_flat)
  const contour_breaks_buf = gpu.device.createBuffer({
    label: `font:${prefix}:breaks`,
    size: cb_array.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  gpu.device.queue.writeBuffer(contour_breaks_buf, 0, cb_array)

  return {
    texture,
    metrics,
    distance_range: 4,
    ascent: meta.ascent as number,
    descent: meta.descent as number,
    line_gap: meta.line_gap as number,
    em_size: meta.em_size as number,
    contour_breaks_buf,
  }
}

// ═════════════════════════════════════════════════════════════════
// Factory — returns the real renderer; stub kept for callers that
// need a non-GPU code path (server-side measure, tests).
// ═════════════════════════════════════════════════════════════════

export function createTextRenderer(gpu: GPUContext): TextRenderer {
  return new HermiteTextRenderer(gpu)
}

export function createStubTextRenderer(gpu: GPUContext): TextRenderer {
  return new StubTextRenderer(gpu)
}
