/**
 * End-to-end integration: blockout_loader + Canvas2D sprite blit.
 *
 * Demonstrates the scaffold-author flow for painting a blockout character
 * on-screen. Uses a mocked fetch + Canvas2D to verify the combination of
 *   loadBlockout (blockout_loader.ts)
 *   getCellForDirection (blockout_loader.ts)
 * produces the right drawImage call signature for a sprite renderer.
 *
 * Complements `parallax_e2e.test.ts` which covers the background layers;
 * this one covers the character layer.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  loadBlockout, resetBlockoutCache,
  getCellForDirection, getAnimFrameCount,
  isTopDownComplete,
} from '../src/sprites/blockout_loader'

const FIXTURES: Record<string, any> = {
  '/blockouts/1986_dragon_quest/hero_plainclothes_walk/1986_dragon_quest_hero_plainclothes_walk_movement_blockout.manifest.json': {
    cols: 4, rows: 1, cell_w: 256, cell_h: 256, gutter_px: 0,
    sheet_w: 1024, sheet_h: 256, frame_count: 4,
    cells: [
      { index: 0, label: 'N', cell_x: 0, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_N.png' },
      { index: 1, label: 'E', cell_x: 256, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_E.png' },
      { index: 2, label: 'S', cell_x: 512, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_S.png' },
      { index: 3, label: 'W', cell_x: 768, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_W.png' },
    ],
  },
  '/blockouts/1986_dragon_quest/hero_plainclothes_walk/1986_dragon_quest_hero_plainclothes_walk_movement_blockout.spec.json': {
    directions: ['N', 'E', 'S', 'W'],
    projection: 'orthographic_top_down',
    anim_frame_targets: { walk: 2 },
    rotation_angles: 4,
    per_frame_ms_default: 90,
    source_essence: '1986_dragon_quest',
    source_animation: 'hero_plainclothes_walk',
  },
}

function makeMockCtx(width = 800, height = 600) {
  const drawCalls: Array<{
    sourceX: number; sourceY: number; sourceW: number; sourceH: number
    destX: number; destY: number; destW: number; destH: number
  }> = []
  const ctx = {
    canvas: { width, height },
    // 9-arg drawImage(image, sx, sy, sw, sh, dx, dy, dw, dh)
    drawImage: vi.fn((_img: any, sx: number, sy: number, sw: number, sh: number,
                      dx: number, dy: number, dw: number, dh: number) => {
      drawCalls.push({
        sourceX: sx, sourceY: sy, sourceW: sw, sourceH: sh,
        destX: dx, destY: dy, destW: dw, destH: dh,
      })
    }),
  } as any
  return { ctx, drawCalls }
}

/** Scaffold-author-style character renderer. Given a loaded blockout +
 *  player position + facing direction, blits the correct cell from the
 *  sheet onto the canvas at the player's screen position. */
function paintCharacter(
  ctx: any, sheet: any, blockout: any,
  direction: string, screenX: number, screenY: number, drawSize = 64,
): boolean {
  const cell = getCellForDirection(blockout, direction)
  if (!cell) return false
  // drawImage(image, sx, sy, sw, sh, dx, dy, dw, dh) — crop from sheet,
  // draw at screen pos scaled to drawSize.
  ctx.drawImage(
    sheet,
    cell.cell_x, cell.cell_y, cell.cell_w, cell.cell_h,
    screenX, screenY, drawSize, drawSize,
  )
  return true
}

beforeEach(() => {
  resetBlockoutCache()
  ;(globalThis as any).fetch = vi.fn(async (url: string) => {
    const data = FIXTURES[url]
    if (!data) return { ok: false, status: 404, statusText: 'nf', json: async () => ({}) }
    return { ok: true, status: 200, statusText: 'ok', json: async () => data }
  })
})

describe('character_render_e2e — full scaffold flow', () => {
  it('renders the east-facing cell of the Dragon Quest hero', async () => {
    const blockout = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(blockout).not.toBeNull()
    expect(isTopDownComplete(blockout!)).toBe(true)

    const sheet = { __id: 'dq_hero_sheet' } as any
    const { ctx, drawCalls } = makeMockCtx()
    const drew = paintCharacter(ctx, sheet, blockout!, 'E', 100, 200, 64)

    expect(drew).toBe(true)
    expect(drawCalls).toHaveLength(1)
    const call = drawCalls[0]
    // Source rect matches the E cell (x=256, y=0, 256×256)
    expect(call.sourceX).toBe(256)
    expect(call.sourceY).toBe(0)
    expect(call.sourceW).toBe(256)
    expect(call.sourceH).toBe(256)
    // Dest rect matches the requested screen position + size
    expect(call.destX).toBe(100)
    expect(call.destY).toBe(200)
    expect(call.destW).toBe(64)
    expect(call.destH).toBe(64)
  })

  it('renders all 4 cardinal directions', async () => {
    const blockout = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    const sheet = { __id: 'dq_hero_sheet' } as any
    const { ctx, drawCalls } = makeMockCtx()

    for (const d of ['N', 'E', 'S', 'W']) {
      paintCharacter(ctx, sheet, blockout!, d, 0, 0, 64)
    }
    expect(drawCalls).toHaveLength(4)
    // Each direction sources a different cell_x
    const xs = drawCalls.map(c => c.sourceX)
    expect(xs).toEqual([0, 256, 512, 768])
  })

  it('returns false silently for unknown direction', async () => {
    const blockout = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    const sheet = {} as any
    const { ctx, drawCalls } = makeMockCtx()
    const drew = paintCharacter(ctx, sheet, blockout!, 'NE', 0, 0, 64)
    expect(drew).toBe(false)
    expect(drawCalls).toHaveLength(0)  // no-op on missing direction
  })

  it('spec carries anim frame counts for scaffold anim-state', async () => {
    const blockout = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    const walk = getAnimFrameCount(blockout!, 'walk')
    const idle = getAnimFrameCount(blockout!, 'idle')
    // walk explicitly in anim_frame_targets, idle not present
    expect(walk).toBe(2)
    expect(idle).toBe(0)
  })

  it('spec provenance links back to source essence + animation', async () => {
    const blockout = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(blockout!.spec.source_essence).toBe('1986_dragon_quest')
    expect(blockout!.spec.source_animation).toBe('hero_plainclothes_walk')
    expect(blockout!.spec.projection).toBe('orthographic_top_down')
    expect(blockout!.spec.rotation_angles).toBe(4)
  })
})
