/**
 * Adventure scene — tactics × action × adventure.
 *
 * Two modes living in the same scene:
 *   - OVERWORLD (action heritage): real-time movement via CameraFollow
 *     + CheckpointProgression, hotspot interactions (shop/dialog/gates),
 *     world-map-node travel.
 *   - COMBAT (tactics heritage): on contact with an enemy patrol,
 *     drop into ATBCombat with the current PartyComposition, enemies
 *     driven by UtilityAI. Resolves back to overworld on victory/rout.
 *
 * Adventure heritage wraps both: DialogTree drives NPC interactions,
 * HotspotMechanic gates scripted beats, WorldMapTravel drives region
 * transitions, EndingBranches reads flags at endgame.
 *
 * All mechanics from @engine/mechanics registry — zero new primitives.
 */

import { mechanicRegistry, type MechanicRuntime } from '@engine/mechanics'
import type { MechanicInstance } from '@engine/design/schema'
import partyData from '../../data/party.json'
import worldData from '../../data/world.json'
import combatData from '../../data/combat.json'
import dialogData from '../../data/dialog.json'

export class Adventure {
  readonly name = 'adventure'
  description = ''
  private mechanics: MechanicRuntime[] = []
  private flags: Set<string> = new Set()
  private current_node = (worldData as any).world_map.start

  constructor() {
    const members = (partyData as any).party.members
    const enemies = (combatData as any).combat.enemy_archetypes
    const dialogs = (dialogData as any).dialogs
    const nodes = (worldData as any).world_map.nodes
    this.description =
      `${Object.keys(members).length} party members · ${Object.keys(enemies).length} enemy types · ` +
      `${Object.keys(dialogs).length} dialog trees · ${nodes.length} world nodes`
  }

  setup(): void {
    const stubGame = this.makeStubGame()

    // === TACTICS HERITAGE ===

    // 1. PartyComposition — roster + active/reserve slots.
    this.tryMount('PartyComposition', {
      max_active: (partyData as any).party.max_active,
      members: (partyData as any).party.members,
    }, stubGame)

    // 2. RoleAssignment — tank/dps/caster/healer role tags drive ATB rate bonus.
    this.tryMount('RoleAssignment', {
      roles: ['tank', 'dps', 'caster', 'healer'],
      rate_bonus_ref: (combatData as any).combat.role_rate_bonus,
    }, stubGame)

    // 3. ATBCombat — active-time turn system for combat encounters.
    this.tryMount('ATBCombat', {
      rate_baseline: (combatData as any).combat.atb_rate_baseline,
      actors_source: 'party_composition.active',
      enemies_source: 'encounter.enemies',
    }, stubGame)

    // 4. TurnBasedCombat — mounted as an alternate combat system
    //    (proves the tactics vocabulary supports both real-time and
    //    strict turn-based without the adventure scene caring which).
    this.tryMount('TurnBasedCombat', {
      turn_order: 'speed_descending',
      enabled: false,
    }, stubGame)

    // 5. UtilityAI — enemies decide actions per turn via weighted utilities.
    this.tryMount('UtilityAI', {
      archetype_weights_ref: 'combat.enemy_archetypes',
      decision_window_ms: 400,
    }, stubGame)

    // === ACTION HERITAGE (overworld real-time) ===

    // 6. CameraFollow — tracks the party leader in overworld mode.
    this.tryMount('CameraFollow', {
      target_tag: 'party_leader',
      lerp: 0.18,
      deadzone: [1.5, 1.5],
    }, stubGame)

    // 7. AttackFrames — player's overworld swing has active frames
    //    (same fighting-heritage primitive as Fight.ts / Run.ts).
    this.tryMount('AttackFrames', {
      owner_id: 'hero',
      attack: 'slash',
      startup_frames: 3,
      active_frames: 5,
      recovery_frames: 8,
    }, stubGame)

    // 8. CheckpointProgression — respawn at last visited town.
    this.tryMount('CheckpointProgression', {
      respawn_delay_sec: 1.5,
      mode: 'respawn_at_last_town',
    }, stubGame)

    // === ADVENTURE HERITAGE ===

    // 9. DialogTree — NPC conversations with branching + flags.
    const dialogs = (dialogData as any).dialogs
    for (const [id, tree] of Object.entries<any>(dialogs)) {
      this.tryMount('DialogTree', {
        tree_id: id,
        root: tree.root,
        nodes: tree.nodes,
      }, stubGame)
    }

    // 10. HotspotMechanic — one mount per hotspot on the world map.
    const hotspots = (worldData as any).hotspots
    for (const h of hotspots) {
      this.tryMount('HotspotMechanic', {
        hotspot_id: h.id,
        at_node: h.at_node,
        kind: h.kind,
        ref: h.dialog_ref ?? h.shop_ref ?? null,
        requires_flag: h.requires_flag ?? null,
      }, stubGame)
    }

    // 11. WorldMapTravel — node→node movement with link-graph.
    this.tryMount('WorldMapTravel', {
      nodes: (worldData as any).world_map.nodes,
      start: this.current_node,
    }, stubGame)

    // 12. Shop — merchant interactions (adventure heritage).
    this.tryMount('Shop', {
      shop_id: 'smith',
      items: [
        { id: 'iron_sword', price: 120 },
        { id: 'leather_guard', price: 80 },
        { id: 'potion', price: 15 },
      ],
    }, stubGame)

    // 13. EndingBranches — reads flag set at runtime to pick epilogue.
    this.tryMount('EndingBranches', {
      endings: (dialogData as any).endings,
      default_ending: 'silence_ending',
    }, stubGame)

    // === UNIVERSAL ===

    // 14. HUD — party HP/MP + current world node.
    this.tryMount('HUD', {
      fields: [
        { archetype: 'hero',   component: 'Health', label: 'H' },
        { archetype: 'mage',   component: 'Health', label: 'M' },
        { archetype: 'rogue',  component: 'Health', label: 'R' },
        { archetype: 'cleric', component: 'Health', label: 'C' },
        { mechanic: 'world_map_travel', field: 'current_node', label: 'WHERE' },
      ],
      layout: 'top',
    }, stubGame)

    // 15. LoseOnZero — game over when the whole party is downed.
    this.tryMount('LoseOnZero', {
      component: 'Health',
      on_archetype: 'party',
      condition: 'all_members_zero',
    }, stubGame)

    // 16. ItemUse — potions / scrolls etc. dispatch.
    this.tryMount('ItemUse', {
      owner_id: 'party',
      cooldown_ms: 200,
    }, stubGame)
  }

  teardown(): void {
    for (const m of this.mechanics) {
      try { m.dispose() } catch { /* swallow */ }
    }
    this.mechanics.length = 0
  }

  private tryMount(type: string, params: Record<string, unknown>, game: any): void {
    const instance = {
      id: `${type}_${this.mechanics.length}`,
      type,
      params,
    } as unknown as MechanicInstance
    const rt = mechanicRegistry.create(instance, game)
    if (rt) this.mechanics.push(rt)
  }

  private makeStubGame(): any {
    const members = (partyData as any).party.members
    return {
      sceneManager: {
        activeScene: () => ({
          entities: Object.entries(members).map(([id, c]: [string, any]) => ({ id, ...c })),
        }),
      },
      config: { mode: '2d' },
    }
  }

  mechanicsActive(): number { return this.mechanics.length }

  /** Test: simulate flag set (dialog effect). */
  setFlag(flag: string): void { this.flags.add(flag) }

  /** Test: query which ending is active given current flags. */
  activeEnding(): string {
    const endings = (dialogData as any).endings
    for (const [id, cfg] of Object.entries<any>(endings)) {
      if ((cfg.requires_flags ?? []).every((f: string) => this.flags.has(f))) return id
    }
    return 'silence_ending'
  }
}
