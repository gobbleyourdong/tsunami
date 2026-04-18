/**
 * UI primitives — 2D quad batcher for rects, rounded-rects, borders.
 *
 * Screen-space pixel coords (top-left origin), instanced WebGPU draw
 * with SDF-based rounded corners + anti-aliased borders. Companion to
 * the text renderer for non-text UI surfaces (panels, buttons, bars).
 *
 * # Status
 *   Public interface           ✓ scaffold
 *   RectStyle type              ✓ scaffold (fill / border / radius)
 *   StubPrimitiveRenderer       ✓ scaffold (no-GPU; records calls for test)
 *   WebGPUPrimitiveRenderer     ✓ scaffold (pipeline + instance batcher)
 *   Shader — rounded-rect SDF   ✓ scaffold (in primitives_shader.ts)
 *   Drop shadow                 TODO v1.2 (second pass, blurred SDF)
 *   Gradient fill               TODO v1.2
 *   Nine-slice rendering        TODO v1.2
 *
 * Follows `text.ts` pattern: public interface + stub + real impl + factory.
 */

import type { GPUContext } from '../renderer/gpu'
import type { RGBA } from './theme'
import { PRIMITIVES_SHADER_WGSL } from './primitives_shader'

// ── Style + call types ───────────────────────────────────────────

export interface RectStyle {
  /** Fill RGBA 0..1. */
  fill?: RGBA
  /** Border color RGBA 0..1. */
  border?: RGBA
  /** Border width in pixels; 0 = no border. */
  border_width?: number
  /** Corner radius in pixels; 0 = sharp corners. */
  radius?: number
}

export interface PrimitivesViewport {
  width: number
  height: number
}

// ── Public interface ────────────────────────────────────────────

export interface PrimitiveRenderer {
  /** Start a primitives pass. Call once per frame. */
  begin(pass: GPURenderPassEncoder, viewport: PrimitivesViewport): void

  /** Solid-fill rectangle. */
  rect(x: number, y: number, w: number, h: number, style: RectStyle): void

  /** Rounded rectangle (convenience: sets radius). */
  rounded_rect(
    x: number, y: number, w: number, h: number,
    radius: number, style: RectStyle,
  ): void

  /** Border-only (hollow) rect. Convenience that sets fill alpha 0. */
  border(
    x: number, y: number, w: number, h: number,
    color: RGBA, width: number, radius?: number,
  ): void

  /** Flush any queued instances. Call once per frame. */
  end(): void

  /** Free GPU resources. */
  destroy(): void
}

// ── Instance buffer layout (matches WGSL Instance struct) ────────
// 64 bytes per instance:
//   pos.xy (8) | size.xy (8) | color.rgba (16) | border_color.rgba (16)
//   | radius (4) | border_width (4) | _pad (8)

const INSTANCE_STRIDE_BYTES = 64
const MAX_INSTANCES = 8192
const UNIFORM_SIZE_BYTES = 16   // viewport.xy + 8 bytes pad

// ── Stub implementation ─────────────────────────────────────────

/**
 * Non-GPU renderer. Records every call into an in-memory log that
 * tests can assert over. Used for unit tests, DOM preview passes,
 * and environments without WebGPU.
 */
export class StubPrimitiveRenderer implements PrimitiveRenderer {
  public readonly calls: Array<{
    kind: 'rect' | 'rounded_rect' | 'border'
    x: number; y: number; w: number; h: number
    style: RectStyle
  }> = []

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_gpu?: GPUContext) {}

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  begin(_pass: GPURenderPassEncoder, _viewport: PrimitivesViewport): void {
    this.calls.length = 0
  }

  rect(x: number, y: number, w: number, h: number, style: RectStyle): void {
    this.calls.push({ kind: 'rect', x, y, w, h, style })
  }

  rounded_rect(
    x: number, y: number, w: number, h: number,
    radius: number, style: RectStyle,
  ): void {
    this.calls.push({
      kind: 'rounded_rect', x, y, w, h,
      style: { ...style, radius },
    })
  }

  border(
    x: number, y: number, w: number, h: number,
    color: RGBA, width: number, radius = 0,
  ): void {
    this.calls.push({
      kind: 'border', x, y, w, h,
      style: { border: color, border_width: width, radius, fill: [0, 0, 0, 0] },
    })
  }

  end(): void { /* flush: noop */ }
  destroy(): void { /* noop */ }
}

// ── Real WebGPU implementation ──────────────────────────────────

export class WebGPUPrimitiveRenderer implements PrimitiveRenderer {
  private gpu: GPUContext
  private pipeline: GPURenderPipeline | null = null
  private bind_layout: GPUBindGroupLayout | null = null

  // Per-frame state
  private pass: GPURenderPassEncoder | null = null
  private viewport: PrimitivesViewport = { width: 1, height: 1 }

  // Instance + uniform buffers
  private instance_buf: GPUBuffer
  private instance_arr: ArrayBuffer
  private instance_view: DataView
  private instance_count = 0

  private uniform_buf: GPUBuffer

  constructor(gpu: GPUContext) {
    this.gpu = gpu

    this.instance_buf = gpu.device.createBuffer({
      size: MAX_INSTANCES * INSTANCE_STRIDE_BYTES,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      label: 'primitives:instances',
    })
    this.instance_arr = new ArrayBuffer(MAX_INSTANCES * INSTANCE_STRIDE_BYTES)
    this.instance_view = new DataView(this.instance_arr)

    this.uniform_buf = gpu.device.createBuffer({
      size: UNIFORM_SIZE_BYTES,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      label: 'primitives:uniforms',
    })

    this.build_pipeline()
  }

  private build_pipeline(): void {
    const device = this.gpu.device

    this.bind_layout = device.createBindGroupLayout({
      label: 'primitives:bind-layout',
      entries: [
        {
          binding: 0,
          visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
          buffer: { type: 'uniform' },
        },
        {
          binding: 1,
          visibility: GPUShaderStage.VERTEX | GPUShaderStage.FRAGMENT,
          buffer: { type: 'read-only-storage' },
        },
      ],
    })

    const pipeline_layout = device.createPipelineLayout({
      label: 'primitives:pipeline-layout',
      bindGroupLayouts: [this.bind_layout],
    })

    const module = device.createShaderModule({
      label: 'primitives:shader',
      code: PRIMITIVES_SHADER_WGSL,
    })

    this.pipeline = device.createRenderPipeline({
      label: 'primitives:pipeline',
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
    })
  }

  begin(pass: GPURenderPassEncoder, viewport: PrimitivesViewport): void {
    this.pass = pass
    this.viewport = viewport
    this.instance_count = 0
  }

  rect(x: number, y: number, w: number, h: number, style: RectStyle): void {
    this.push_instance(x, y, w, h, style)
  }

  rounded_rect(
    x: number, y: number, w: number, h: number,
    radius: number, style: RectStyle,
  ): void {
    this.push_instance(x, y, w, h, { ...style, radius })
  }

  border(
    x: number, y: number, w: number, h: number,
    color: RGBA, width: number, radius = 0,
  ): void {
    this.push_instance(x, y, w, h, {
      fill: [0, 0, 0, 0],
      border: color,
      border_width: width,
      radius,
    })
  }

  private push_instance(
    x: number, y: number, w: number, h: number, style: RectStyle,
  ): void {
    if (!this.pass) return
    if (this.instance_count >= MAX_INSTANCES) {
      console.warn('WebGPUPrimitiveRenderer: instance buffer full')
      return
    }
    const off = this.instance_count * INSTANCE_STRIDE_BYTES
    const v = this.instance_view

    const fill = style.fill ?? [0, 0, 0, 0]
    const bord = style.border ?? [0, 0, 0, 0]

    // pos.xy
    v.setFloat32(off + 0, x, true)
    v.setFloat32(off + 4, y, true)
    // size.xy
    v.setFloat32(off + 8, w, true)
    v.setFloat32(off + 12, h, true)
    // color.rgba
    v.setFloat32(off + 16, fill[0], true)
    v.setFloat32(off + 20, fill[1], true)
    v.setFloat32(off + 24, fill[2], true)
    v.setFloat32(off + 28, fill[3], true)
    // border_color.rgba
    v.setFloat32(off + 32, bord[0], true)
    v.setFloat32(off + 36, bord[1], true)
    v.setFloat32(off + 40, bord[2], true)
    v.setFloat32(off + 44, bord[3], true)
    // radius
    v.setFloat32(off + 48, style.radius ?? 0, true)
    // border_width
    v.setFloat32(off + 52, style.border_width ?? 0, true)
    // _pad (8 bytes)
    v.setFloat32(off + 56, 0, true)
    v.setFloat32(off + 60, 0, true)

    this.instance_count++
  }

  end(): void {
    if (!this.pass || !this.pipeline || !this.bind_layout) return
    if (this.instance_count === 0) {
      this.pass = null
      return
    }

    const device = this.gpu.device

    // Uniforms: viewport size.
    const uniforms = new ArrayBuffer(UNIFORM_SIZE_BYTES)
    const uv = new DataView(uniforms)
    uv.setFloat32(0, this.viewport.width, true)
    uv.setFloat32(4, this.viewport.height, true)
    device.queue.writeBuffer(this.uniform_buf, 0, uniforms)

    // Upload populated instance slice.
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
        { binding: 1, resource: { buffer: this.instance_buf } },
      ],
    })

    this.pass.setPipeline(this.pipeline)
    this.pass.setBindGroup(0, bind_group)
    this.pass.draw(4, this.instance_count, 0, 0)

    this.pass = null
  }

  destroy(): void {
    this.instance_buf.destroy()
    this.uniform_buf.destroy()
    this.pipeline = null
  }
}

// ── Factory ─────────────────────────────────────────────────────

export function createPrimitiveRenderer(gpu: GPUContext): PrimitiveRenderer {
  return new WebGPUPrimitiveRenderer(gpu)
}

export function createStubPrimitiveRenderer(gpu?: GPUContext): PrimitiveRenderer {
  return new StubPrimitiveRenderer(gpu)
}
