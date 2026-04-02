import { Application, Sprite, Texture, Rectangle, BaseTexture } from "pixi.js"

interface SpriteFrame {
  x: number
  y: number
  width: number
  height: number
}

/** Create an animated sprite from a sprite sheet.
 *  Returns a Sprite and a function to advance frames. */
export function createAnimatedSprite(
  app: Application,
  sheetUrl: string,
  frameWidth: number,
  frameHeight: number,
  columns: number,
  totalFrames: number,
  fps: number = 12,
): { sprite: Sprite; update: (dt: number) => void } {
  const baseTexture = BaseTexture.from(sheetUrl)
  const frames: Texture[] = []

  for (let i = 0; i < totalFrames; i++) {
    const col = i % columns
    const row = Math.floor(i / columns)
    const rect = new Rectangle(col * frameWidth, row * frameHeight, frameWidth, frameHeight)
    frames.push(new Texture({ source: baseTexture, frame: rect }))
  }

  const sprite = new Sprite(frames[0])
  let currentFrame = 0
  let elapsed = 0

  const update = (dt: number) => {
    elapsed += dt
    if (elapsed > 1 / fps) {
      elapsed = 0
      currentFrame = (currentFrame + 1) % totalFrames
      sprite.texture = frames[currentFrame]
    }
  }

  return { sprite, update }
}

/** Simple 2D puppet rig — connect body parts with offsets.
 *  Each part is a sprite positioned relative to its parent. */
export interface PuppetPart {
  sprite: Sprite
  offsetX: number
  offsetY: number
  children: PuppetPart[]
}

export function createPuppet(parts: PuppetPart, rootX: number, rootY: number) {
  function updatePart(part: PuppetPart, parentX: number, parentY: number) {
    part.sprite.position.set(parentX + part.offsetX, parentY + part.offsetY)
    for (const child of part.children) {
      updatePart(child, part.sprite.x, part.sprite.y)
    }
  }

  return {
    update() {
      updatePart(parts, rootX, rootY)
    },
    setPosition(x: number, y: number) {
      rootX = x
      rootY = y
    },
    root: parts,
  }
}
