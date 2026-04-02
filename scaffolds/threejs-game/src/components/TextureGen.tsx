import { useMemo } from "react"
import * as THREE from "three"

/** Generate a procedural texture from a canvas drawing function.
 *  Returns a THREE.CanvasTexture. */
export function useProceduralTexture(
  width: number,
  height: number,
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void,
  deps: any[] = [],
): THREE.CanvasTexture {
  return useMemo(() => {
    const canvas = document.createElement("canvas")
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext("2d")!
    draw(ctx, width, height)
    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    return tex
  }, [width, height, ...deps])
}

// ── Built-in texture generators ──

/** Checkerboard pattern */
export function drawCheckerboard(ctx: CanvasRenderingContext2D, w: number, h: number, size = 32, color1 = "#333", color2 = "#666") {
  for (let y = 0; y < h; y += size) {
    for (let x = 0; x < w; x += size) {
      ctx.fillStyle = ((x + y) / size) % 2 === 0 ? color1 : color2
      ctx.fillRect(x, y, size, size)
    }
  }
}

/** Noise/grain pattern */
export function drawNoise(ctx: CanvasRenderingContext2D, w: number, h: number, intensity = 0.3) {
  const img = ctx.createImageData(w, h)
  for (let i = 0; i < img.data.length; i += 4) {
    const v = Math.random() * 255 * intensity
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v
    img.data[i + 3] = 255
  }
  ctx.putImageData(img, 0, 0)
}

/** Gradient */
export function drawGradient(ctx: CanvasRenderingContext2D, w: number, h: number, colors = ["#004444", "#000044"]) {
  const grad = ctx.createLinearGradient(0, 0, 0, h)
  colors.forEach((c, i) => grad.addColorStop(i / (colors.length - 1), c))
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, w, h)
}

/** Brick/tile pattern */
export function drawBricks(ctx: CanvasRenderingContext2D, w: number, h: number, bw = 40, bh = 20, mortar = "#222", brick = "#884422") {
  ctx.fillStyle = mortar
  ctx.fillRect(0, 0, w, h)
  ctx.fillStyle = brick
  for (let y = 0; y < h; y += bh + 2) {
    const offset = (Math.floor(y / (bh + 2)) % 2) * (bw / 2)
    for (let x = -bw; x < w + bw; x += bw + 2) {
      ctx.fillRect(x + offset, y, bw, bh)
    }
  }
}
