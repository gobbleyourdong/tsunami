/**
 * RPG Renderer — top-down tile map with sprite characters.
 * Renders terrain tiles, props, NPCs, player, and UI overlays.
 */

import type { WorldMap, TileType } from './world'
import type { RPGPlayer } from './rpg_player'
import type { NPCDef } from './world'
import type { CombatSystem } from './combat'
import type { QuestSystem } from './quests'

const TILE_SPRITES: Record<TileType, string> = {
  grass: '/sprites/texture/tile_grass/tile_grass_best.png',
  darkgrass: '/sprites/texture/tile_darkgrass/tile_darkgrass_best.png',
  flowers: '/sprites/texture/tile_flowers/tile_flowers_best.png',
  path: '/sprites/texture/tile_path/tile_path_best.png',
  stone: '/sprites/texture/tile_stone/tile_stone_best.png',
  water: '/sprites/texture/tile_water/tile_water_best.png',
  sand: '/sprites/texture/tile_sand/tile_sand_best.png',
  lava: '/sprites/texture/tile_lava/tile_lava_best.png',
  wood: '/sprites/texture/tile_wood/tile_wood_best.png',
}

const TILE_COLORS: Record<TileType, string> = {
  grass: '#2d5a1e', darkgrass: '#1a3a10', flowers: '#3d7a2e',
  path: '#8a7a5a', stone: '#6a6a6a', water: '#2a4a8a',
  sand: '#c4a84a', lava: '#aa3300', wood: '#6a4a2a',
}

export class RPGRenderer {
  private ctx: CanvasRenderingContext2D
  private canvas: HTMLCanvasElement
  private sprites = new Map<string, HTMLImageElement>()
  private tileSize = 32
  private time = 0

  // Camera follows player with smoothing
  cameraX = 0
  cameraY = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D not supported')
    this.ctx = ctx
    this.resize()
    window.addEventListener('resize', () => this.resize())
  }

  private resize(): void {
    const dpr = window.devicePixelRatio || 1
    this.canvas.width = window.innerWidth * dpr
    this.canvas.height = window.innerHeight * dpr
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    // Pixel-perfect rendering
    this.ctx.imageSmoothingEnabled = false
  }

  /** Load a sprite image, returns immediately (renders fallback until loaded). */
  private getSprite(path: string): HTMLImageElement | null {
    if (this.sprites.has(path)) return this.sprites.get(path)!
    // Start loading
    const img = new Image()
    img.src = path
    img.onload = () => this.sprites.set(path, img)
    this.sprites.set(path, null as any) // mark as loading
    return null
  }

  /** Get character sprite by name. */
  private getCharSprite(name: string): HTMLImageElement | null {
    const path = `/sprites/character/${name}/${name}_best.png`
    return this.getSprite(path)
  }

  /** Get prop sprite by type. */
  private getPropSprite(type: string): HTMLImageElement | null {
    const path = `/sprites/object/${type}/${type}_best.png`
    return this.getSprite(path)
  }

  render(dt: number, map: WorldMap, player: RPGPlayer, activeDialog: string[] | null, dialogIndex: number, combat?: CombatSystem, quests?: QuestSystem): void {
    this.time += dt
    const ctx = this.ctx
    const ts = map.tileSize
    this.tileSize = ts

    // Camera: smooth follow player
    const targetCamX = player.x * ts - window.innerWidth / 2
    const targetCamY = player.y * ts - window.innerHeight / 2
    this.cameraX += (targetCamX - this.cameraX) * Math.min(dt * 5, 1)
    this.cameraY += (targetCamY - this.cameraY) * Math.min(dt * 5, 1)

    // Clear
    ctx.fillStyle = '#0a0a12'
    ctx.fillRect(0, 0, window.innerWidth, window.innerHeight)

    ctx.save()
    ctx.translate(-this.cameraX, -this.cameraY)

    // Determine visible tile range
    const startX = Math.max(0, Math.floor(this.cameraX / ts) - 1)
    const startY = Math.max(0, Math.floor(this.cameraY / ts) - 1)
    const endX = Math.min(map.width, Math.ceil((this.cameraX + window.innerWidth) / ts) + 1)
    const endY = Math.min(map.height, Math.ceil((this.cameraY + window.innerHeight) / ts) + 1)

    // Draw ground tiles
    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        const tile = map.layers.ground[y]?.[x]
        if (!tile) continue
        const sx = x * ts, sy = y * ts

        const spritePath = TILE_SPRITES[tile]
        const img = spritePath ? this.getSprite(spritePath) : null
        if (img) {
          ctx.drawImage(img, sx, sy, ts, ts)
        } else {
          ctx.fillStyle = TILE_COLORS[tile] ?? '#333'
          ctx.fillRect(sx, sy, ts, ts)
        }
      }
    }

    // Collect all renderables and sort by Y (painter's algorithm)
    const renderables: { y: number; draw: () => void }[] = []

    // Props
    for (const prop of map.props) {
      const px = prop.x * ts, py = prop.y * ts
      if (px < this.cameraX - ts * 2 || px > this.cameraX + window.innerWidth + ts) continue
      if (py < this.cameraY - ts * 2 || py > this.cameraY + window.innerHeight + ts) continue

      renderables.push({
        y: prop.y,
        draw: () => {
          const img = this.getPropSprite(prop.type)
          const size = prop.type === 'prop_house' ? ts * 2 : prop.type === 'prop_tree' ? ts * 1.5 : ts
          if (img) {
            ctx.drawImage(img, px - (size - ts) / 2, py - (size - ts), size, size)
          } else {
            // Fallback shapes
            ctx.fillStyle = prop.type.includes('tree') ? '#1a5a1a' : prop.type.includes('house') ? '#8a6a3a' : '#666'
            ctx.fillRect(px + 4, py + 4, ts - 8, ts - 8)
          }
        },
      })
    }

    // NPCs
    for (const npc of map.npcs) {
      renderables.push({
        y: npc.y,
        draw: () => {
          const nx = npc.x * ts, ny = npc.y * ts
          const img = this.getCharSprite(npc.sprite)
          const size = ts * 1.4

          // Hit flash effect (white overlay)
          const enemyState = combat?.getEnemyState(npc.id)
          if (enemyState?.hitFlash && enemyState.hitFlash > 0) {
            ctx.globalAlpha = 0.5 + enemyState.hitFlash * 3
            ctx.fillStyle = '#ffffff'
            ctx.beginPath()
            ctx.arc(nx + ts / 2, ny + ts / 2, ts * 0.5, 0, Math.PI * 2)
            ctx.fill()
            ctx.globalAlpha = 1
          }

          if (img) {
            ctx.drawImage(img, nx - (size - ts) / 2, ny - (size - ts), size, size)
          } else {
            ctx.fillStyle = npc.hostile ? '#cc3333' : '#3399cc'
            ctx.beginPath()
            ctx.arc(nx + ts / 2, ny + ts / 2, ts * 0.35, 0, Math.PI * 2)
            ctx.fill()
          }

          // Enemy HP bar
          if (npc.hostile && enemyState && !enemyState.dead) {
            const hpPct = enemyState.health.healthPercent
            if (hpPct < 1) {
              const barW = ts * 1.2
              const barH = 3
              const barX = nx + ts / 2 - barW / 2
              const barY = ny - 6
              ctx.fillStyle = '#333'
              ctx.fillRect(barX, barY, barW, barH)
              ctx.fillStyle = hpPct > 0.5 ? '#44cc44' : hpPct > 0.25 ? '#cccc44' : '#cc4444'
              ctx.fillRect(barX, barY, barW * hpPct, barH)
            }
          }

          // Name label (non-hostile only)
          if (!npc.hostile) {
            ctx.fillStyle = '#ffffff'
            ctx.font = '10px monospace'
            ctx.textAlign = 'center'
            ctx.fillText(npc.name, nx + ts / 2, ny - 4)
          }
        },
      })
    }

    // Loot drops (bobbing items on ground)
    if (combat) {
      for (const drop of combat.worldDrops) {
        renderables.push({
          y: drop.y,
          draw: () => {
            const dx = drop.x * ts, dy = drop.y * ts
            const bob = Math.sin(this.time * 4 + drop.x * 3) * 2
            ctx.fillStyle = '#ffcc00'
            ctx.globalAlpha = 0.6 + 0.3 * Math.sin(this.time * 3)
            ctx.shadowColor = '#ffcc00'
            ctx.shadowBlur = 6
            ctx.beginPath()
            ctx.arc(dx + ts / 2, dy + ts / 2 + bob, 4, 0, Math.PI * 2)
            ctx.fill()
            ctx.shadowBlur = 0
            ctx.globalAlpha = 1
            // Label
            ctx.fillStyle = '#ffcc00'
            ctx.font = '8px monospace'
            ctx.textAlign = 'center'
            ctx.fillText(drop.name, dx + ts / 2, dy - 2 + bob)
            ctx.textAlign = 'left'
          },
        })
      }
    }

    // Player
    renderables.push({
      y: player.y,
      draw: () => {
        const px = player.x * ts, py = player.y * ts
        const img = this.getCharSprite(player.sprite)
        const size = ts * 1.4
        if (img) {
          ctx.drawImage(img, px - (size - ts) / 2, py - (size - ts), size, size)
        } else {
          ctx.fillStyle = '#00ff88'
          ctx.beginPath()
          ctx.arc(px + ts / 2, py + ts / 2, ts * 0.35, 0, Math.PI * 2)
          ctx.fill()
        }

        // Facing indicator
        const [fx, fy] = player.getFacingTile()
        ctx.strokeStyle = '#00ff8844'
        ctx.lineWidth = 1
        ctx.strokeRect(fx * ts + 2, fy * ts + 2, ts - 4, ts - 4)
      },
    })

    // Sort by Y and draw
    renderables.sort((a, b) => a.y - b.y)
    for (const r of renderables) r.draw()

    ctx.restore()

    // --- UI Overlays (screen space) ---

    // Health bar
    const hpPct = player.health.healthPercent
    ctx.fillStyle = '#333'
    ctx.fillRect(12, 12, 104, 12)
    ctx.fillStyle = hpPct > 0.5 ? '#ff4444' : hpPct > 0.25 ? '#ff8800' : '#ff0000'
    ctx.fillRect(14, 14, 100 * hpPct, 8)
    ctx.fillStyle = '#fff'
    ctx.font = '10px monospace'
    ctx.fillText(`HP ${Math.ceil(player.health.health)}`, 120, 22)

    // Map name
    ctx.fillStyle = '#8888aa'
    ctx.font = '12px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(map.name, window.innerWidth / 2, 22)
    ctx.textAlign = 'left'

    // Quest tracker (top-right)
    if (quests) {
      const active = quests.getActive()
      let qy = 16
      for (const q of active) {
        ctx.fillStyle = '#ffcc00'
        ctx.font = '11px monospace'
        ctx.textAlign = 'right'
        ctx.fillText(q.name, window.innerWidth - 16, qy)
        qy += 14
        for (const obj of q.objectives) {
          const done = obj.current >= obj.required
          ctx.fillStyle = done ? '#44cc44' : '#aaaaaa'
          ctx.font = '10px monospace'
          ctx.fillText(
            `${done ? '✓' : '○'} ${obj.description.replace(/\(\d+\/\d+\)/, `(${obj.current}/${obj.required})`)}`,
            window.innerWidth - 16, qy
          )
          qy += 12
        }
        qy += 4
      }
      ctx.textAlign = 'left'
    }

    // Inventory count
    const itemCount = player.inventory.usedSlots
    if (itemCount > 0) {
      ctx.fillStyle = '#888'
      ctx.font = '10px monospace'
      ctx.fillText(`Items: ${itemCount}/${player.inventory.maxSlots}`, 12, 38)
    }

    // Interaction prompt
    const npc = player.findNearbyNPC(map)
    if (npc && !npc.hostile && !activeDialog) {
      ctx.fillStyle = '#ffcc00'
      ctx.font = '14px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`[E] Talk to ${npc.name}`, window.innerWidth / 2, window.innerHeight - 40)
      ctx.textAlign = 'left'
    }

    // Dialog box
    if (activeDialog && dialogIndex < activeDialog.length) {
      const boxH = 80
      const boxY = window.innerHeight - boxH - 20
      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'
      ctx.fillRect(40, boxY, window.innerWidth - 80, boxH)
      ctx.strokeStyle = '#4a9eff'
      ctx.lineWidth = 2
      ctx.strokeRect(40, boxY, window.innerWidth - 80, boxH)

      ctx.fillStyle = '#e2e8f0'
      ctx.font = '14px monospace'
      ctx.fillText(activeDialog[dialogIndex], 60, boxY + 35)

      ctx.fillStyle = '#666'
      ctx.font = '11px monospace'
      ctx.fillText(dialogIndex < activeDialog.length - 1 ? '[E] Continue' : '[E] Close', 60, boxY + 60)
    }
  }
}
