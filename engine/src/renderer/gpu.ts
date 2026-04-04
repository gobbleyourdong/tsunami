/**
 * WebGPU device initialization and canvas management.
 * Handles adapter/device acquisition, surface configuration, and resize.
 */

export interface GPUContext {
  device: GPUDevice
  context: GPUCanvasContext
  format: GPUTextureFormat
  canvas: HTMLCanvasElement
  depthTexture: GPUTexture
  depthView: GPUTextureView
}

export async function initGPU(canvas: HTMLCanvasElement): Promise<GPUContext> {
  if (!navigator.gpu) {
    throw new Error('WebGPU not supported in this browser')
  }

  const adapter = await navigator.gpu.requestAdapter({
    powerPreference: 'high-performance',
  })
  if (!adapter) {
    throw new Error('No WebGPU adapter found')
  }

  const device = await adapter.requestDevice({
    requiredFeatures: [],
    requiredLimits: {},
  })

  device.lost.then((info) => {
    console.error(`WebGPU device lost: ${info.message}`)
    if (info.reason !== 'destroyed') {
      // Could attempt re-init here
    }
  })

  const context = canvas.getContext('webgpu')
  if (!context) {
    throw new Error('Failed to get WebGPU context')
  }

  const format = navigator.gpu.getPreferredCanvasFormat()

  context.configure({
    device,
    format,
    alphaMode: 'premultiplied',
  })

  const { depthTexture, depthView } = createDepthTexture(device, canvas.width, canvas.height)

  return { device, context, format, canvas, depthTexture, depthView }
}

export function createDepthTexture(
  device: GPUDevice,
  width: number,
  height: number
): { depthTexture: GPUTexture; depthView: GPUTextureView } {
  const depthTexture = device.createTexture({
    size: { width, height },
    format: 'depth24plus-stencil8',
    usage: GPUTextureUsage.RENDER_ATTACHMENT,
  })
  return { depthTexture, depthView: depthTexture.createView() }
}

export function resizeGPU(ctx: GPUContext): void {
  const { canvas, device } = ctx
  const dpr = window.devicePixelRatio || 1
  const width = Math.floor(canvas.clientWidth * dpr)
  const height = Math.floor(canvas.clientHeight * dpr)

  if (canvas.width === width && canvas.height === height) return

  canvas.width = width
  canvas.height = height

  ctx.context.configure({
    device,
    format: ctx.format,
    alphaMode: 'premultiplied',
  })

  ctx.depthTexture.destroy()
  const { depthTexture, depthView } = createDepthTexture(device, width, height)
  ctx.depthTexture = depthTexture
  ctx.depthView = depthView
}
