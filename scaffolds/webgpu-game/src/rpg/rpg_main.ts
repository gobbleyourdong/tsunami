/**
 * RPG Main — 2.5D top-down RPG with tile maps, NPC dialog, and combat.
 * Entry point: import and call rpgBoot(canvas, hud)
 */

import { KeyboardInput } from '@engine/input/keyboard'
import { createVillageMap, createForestMap, WorldMap } from './world'
import { RPGPlayer } from './rpg_player'
import { RPGRenderer } from './rpg_renderer'
import { CombatSystem } from './combat'
import { QuestSystem } from './quests'
import { GameSynth } from '../game/synth'

export interface RPGState {
  currentMap: WorldMap
  maps: Map<string, WorldMap>
  player: RPGPlayer
  combat: CombatSystem
  quests: QuestSystem
  activeDialog: string[] | null
  dialogIndex: number
  dialogSpeaker: string
  gamePhase: 'explore' | 'dialog' | 'combat' | 'paused'
}

export async function rpgBoot(canvas: HTMLCanvasElement, hud: HTMLElement): Promise<void> {
  const keyboard = new KeyboardInput()
  keyboard.bind()

  // Load maps — check URL for custom map: rpg.html?map=/maps/custom.json
  const maps = new Map<string, WorldMap>()
  maps.set('village', createVillageMap())
  maps.set('forest', createForestMap())

  // Load custom map: ?map=editor (sessionStorage) or ?map=/path/to/map.json (fetch)
  const urlParams = new URLSearchParams(window.location.search)
  const customMapParam = urlParams.get('map')
  if (customMapParam === 'editor') {
    // Load from editor via sessionStorage
    const editorData = sessionStorage.getItem('editorMap')
    if (editorData) {
      try {
        maps.set('custom', JSON.parse(editorData) as WorldMap)
      } catch (e) {
        console.warn('[rpg] Failed to parse editor map:', e)
      }
    }
  } else if (customMapParam) {
    // Load from URL
    try {
      const resp = await fetch(customMapParam)
      maps.set('custom', await resp.json() as WorldMap)
    } catch (e) {
      console.warn('[rpg] Failed to load custom map:', customMapParam, e)
    }
  }

  const startMapName = customMapParam ? 'custom' : 'village'
  const startMap = maps.get(startMapName)!
  const player = new RPGPlayer(keyboard, startMap.playerStart[0], startMap.playerStart[1])

  const combat = new CombatSystem()
  const quests = new QuestSystem()
  const synth = new GameSynth()

  combat.initFromMap(startMap)

  // Wire combat events to quest + audio
  combat.onHit = (id, dmg) => {
    synth.play('swordHit', { intensity: Math.min(dmg / 20, 1) })
  }
  combat.onKill = (id, x, y) => {
    synth.play('explosion', { intensity: 0.6 })
    const npc = startMap.npcs.find(n => n.id === id) ?? maps.get('forest')?.npcs.find(n => n.id === id)
    if (npc) quests.notifyKill(npc.sprite)
  }
  combat.onPlayerHit = (dmg) => {
    synth.play('playerHurt')
  }

  const state: RPGState = {
    currentMap: startMap,
    maps,
    player,
    combat,
    quests,
    activeDialog: null,
    dialogIndex: 0,
    dialogSpeaker: '',
    gamePhase: 'explore',
  }

  const renderer = new RPGRenderer(canvas)

  // Show RPG title
  showRPGTitle(hud)

  let started = false
  let lastTime = performance.now()

  function tick(now: number) {
    const dt = Math.min((now - lastTime) / 1000, 0.1)
    lastTime = now

    if (!started) {
      if (keyboard.justPressed('Enter') || keyboard.justPressed('Space')) {
        started = true
        clearHUD(hud)
      }
      keyboard.update()
      renderer.render(dt, state.currentMap, state.player, null, 0, combat, quests)
      requestAnimationFrame(tick)
      return
    }

    // --- Update ---
    if (state.gamePhase === 'explore') {
      player.update(dt, state.currentMap)

      // Check for map exit
      if (player.interactTarget?.id === '__exit__') {
        const targetName = player.interactTarget.name
        const spawnX = player.interactTarget.x
        const spawnY = player.interactTarget.y
        player.interactTarget = null

        const newMap = state.maps.get(targetName)
        if (newMap) {
          state.currentMap = newMap
          player.x = spawnX
          player.y = spawnY
          player.targetX = spawnX
          player.targetY = spawnY
          player.moving = false
          combat.initFromMap(newMap)
          quests.notifyReach(targetName)
        }
      }

      // Combat update
      combat.update(dt, state.currentMap, player)

      // Loot pickup → quest notify
      for (const drop of combat.worldDrops) {
        // Check if player just picked it up (distance check happens in combat.update)
      }

      // Interact (E key)
      if (keyboard.justPressed('KeyE')) {
        const npc = player.findNearbyNPC(state.currentMap)
        if (npc && !npc.hostile) {
          // Quest dialog takes priority over default NPC dialog
          const questDialog = quests.getQuestDialog(npc.id)
          const dialog = questDialog ?? (npc.dialog && npc.dialog.length > 0 ? npc.dialog : null)
          if (dialog) {
            // Accept quest if inactive
            quests.acceptQuest(npc.id)
            // Try turn-in if complete
            quests.turnInQuest(npc.id, player)

            state.activeDialog = dialog
            state.dialogIndex = 0
            state.dialogSpeaker = npc.name
            state.gamePhase = 'dialog'
          }
        }
      }

      // Attack (Space) — uses combat system with HP, knockback, loot
      if (keyboard.justPressed('Space')) {
        synth.play('swordSlash')
        combat.playerAttack(player, state.currentMap)
      }

      // NPC patrol movement
      for (const npc of state.currentMap.npcs) {
        if (npc.patrol && npc.patrol.length > 0) {
          // Simple patrol: move toward next waypoint
          const wp = npc.patrol[0]
          const dx = wp[0] - npc.x
          const dy = wp[1] - npc.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 0.1) {
            npc.patrol.push(npc.patrol.shift()!) // cycle waypoints
          } else {
            const speed = 1.5 * dt
            npc.x += (dx / dist) * speed
            npc.y += (dy / dist) * speed
          }
        }
      }

    } else if (state.gamePhase === 'dialog') {
      if (keyboard.justPressed('KeyE') || keyboard.justPressed('Space') || keyboard.justPressed('Enter')) {
        state.dialogIndex++
        if (state.dialogIndex >= (state.activeDialog?.length ?? 0)) {
          state.activeDialog = null
          state.dialogIndex = 0
          state.gamePhase = 'explore'
        }
      }
    }

    // Pause
    if (keyboard.justPressed('Escape')) {
      if (state.gamePhase === 'paused') state.gamePhase = 'explore'
      else if (state.gamePhase === 'explore') state.gamePhase = 'paused'
    }

    // --- Render ---
    renderer.render(dt, state.currentMap, state.player, state.activeDialog, state.dialogIndex, combat, quests)

    // Pause overlay
    if (state.gamePhase === 'paused') {
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = 'rgba(0,0,0,0.6)'
      ctx.fillRect(0, 0, window.innerWidth, window.innerHeight)
      ctx.fillStyle = '#fff'
      ctx.font = '24px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('PAUSED', window.innerWidth / 2, window.innerHeight / 2)
      ctx.font = '14px monospace'
      ctx.fillText('Press ESC to resume', window.innerWidth / 2, window.innerHeight / 2 + 30)
      ctx.textAlign = 'left'
    }

    keyboard.update()
    requestAnimationFrame(tick)
  }

  requestAnimationFrame(tick)
}

function showRPGTitle(hud: HTMLElement): void {
  while (hud.firstChild) hud.removeChild(hud.firstChild)
  Object.assign(hud.style, { textAlign: 'center', paddingTop: '25vh' })

  const title = document.createElement('div')
  title.style.cssText = 'font-size:42px;font-weight:bold;color:#ffcc00;text-shadow:0 0 20px #ffcc0044'
  title.textContent = 'OAKVALE'
  hud.appendChild(title)

  const sub = document.createElement('div')
  sub.style.cssText = 'margin-top:10px;color:#aaa;font-size:16px'
  sub.textContent = 'A 2.5D Sprite RPG'
  hud.appendChild(sub)

  const prompt = document.createElement('div')
  prompt.style.cssText = 'margin-top:40px;color:#4a9eff;font-size:16px'
  prompt.textContent = 'Press ENTER to Begin'
  hud.appendChild(prompt)

  const controls = document.createElement('div')
  controls.style.cssText = 'margin-top:30px;color:#666;font-size:12px;line-height:1.8'
  controls.textContent = 'WASD: Move | E: Interact | Space: Attack | ESC: Pause'
  hud.appendChild(controls)
}

function clearHUD(hud: HTMLElement): void {
  while (hud.firstChild) hud.removeChild(hud.firstChild)
  Object.assign(hud.style, { textAlign: '', paddingTop: '' })
}
