/**
 * Sprite texture loader — fetches a PNG, creates a GPUTexture, returns
 * native dimensions alongside the view + sampler.
 *
 * CRITICAL: sprites are NEVER scaled. The renderer uses `width` / `height`
 * to lock the sprite's rendered footprint to its source-pixel dimensions.
 * Nearest-neighbor sampler ensures each source pixel maps to exactly one
 * screen pixel. Combined with the pixel-snap in the vertex shader, the
 * sprite's internal layout (eyes, outline, body) is identical at every
 * position on screen.
 */

export interface SpriteTexture {
  texture: GPUTexture
  view: GPUTextureView
  sampler: GPUSampler
  width: number
  height: number
}

export async function loadSpriteTexture(
  device: GPUDevice,
  url: string
): Promise<SpriteTexture> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Failed to fetch sprite: ${url} (${resp.status})`)
  const blob = await resp.blob()
  const bitmap = await createImageBitmap(blob, { premultiplyAlpha: 'none' })

  const texture = device.createTexture({
    label: `sprite:${url}`,
    size: [bitmap.width, bitmap.height],
    format: 'rgba8unorm',
    usage:
      GPUTextureUsage.TEXTURE_BINDING |
      GPUTextureUsage.COPY_DST |
      GPUTextureUsage.RENDER_ATTACHMENT,
  })

  device.queue.copyExternalImageToTexture(
    { source: bitmap },
    { texture },
    [bitmap.width, bitmap.height]
  )

  // Nearest in both directions — never interpolate sprite pixels.
  const sampler = device.createSampler({
    label: 'sprite-nearest',
    magFilter: 'nearest',
    minFilter: 'nearest',
    addressModeU: 'clamp-to-edge',
    addressModeV: 'clamp-to-edge',
  })

  return {
    texture,
    view: texture.createView(),
    sampler,
    width: bitmap.width,
    height: bitmap.height,
  }
}
