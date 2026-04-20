/**
 * Phase 1 — mechanics barrel smoke test.
 *
 * Verifies @engine/mechanics resolves cleanly and the registry contains
 * the expected runtime implementations from design/mechanics/*.
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicType } from '../src/design/schema'

// 36 MechanicTypes that have runtime implementations per FRAMEWORK_MANIFEST.md.
// Must stay in sync with design/mechanics/index.ts side-effect imports.
const EXPECTED_REGISTERED: MechanicType[] = [
  'Difficulty', 'LoseOnZero', 'WinOnCount', 'WaveSpawner', 'PickupLoop',
  'ScoreCombos', 'CheckpointProgression', 'LockAndKey', 'StateMachineMechanic',
  'ComboAttacks', 'BossPhases', 'RhythmTrack', 'LevelSequence', 'RoomGraph',
  'ItemUse', 'GatedTrigger', 'TimedStateModifier', 'AttackFrames', 'Shop',
  'DialogTree', 'HotspotMechanic', 'InventoryCombine', 'CameraFollow',
  'StatusStack', 'EmbeddedMinigame', 'EndingBranches', 'VisionCone',
  'PuzzleObject', 'ProceduralRoomChain', 'BulletPattern', 'RouteMap',
  'ChipMusic', 'SfxLibrary',
  'HUD', 'UtilityAI',  // missed in initial scan (snake-case regex bug)
  'LevelUpProgression',  // v1.2 JRPG cluster — landed 2026-04-20
]

describe('Phase 1 — mechanics barrel', () => {
  it('registry is importable from @engine/mechanics', () => {
    expect(mechanicRegistry).toBeDefined()
    expect(typeof mechanicRegistry.has).toBe('function')
    expect(typeof mechanicRegistry.create).toBe('function')
  })

  it('has the expected core mechanics registered', () => {
    const missing: MechanicType[] = []
    for (const type of EXPECTED_REGISTERED) {
      if (!mechanicRegistry.has(type)) missing.push(type)
    }
    expect(missing).toEqual([])
  })

  it('does NOT have the 5 still-missing mechanics registered', () => {
    const MISSING: MechanicType[] = [
      'RoleAssignment', 'CrowdSimulation',
      'TimeReverseMechanic', 'PhysicsModifier', 'MinigamePool',
      // LevelUpProgression landed 2026-04-20 — removed from missing list
      // TurnBasedCombat landed 2026-04-20 (Cycle 10) — removed from missing list
      // ATBCombat landed 2026-04-20 (Cycle 11) — removed from missing list
      // PartyComposition landed 2026-04-20 (Cycle 12) — removed from missing list
      // WorldMapTravel landed 2026-04-20 (Cycle 13) — removed from missing list
      // EquipmentLoadout landed 2026-04-20 (Cycle 14) — JRPG v1.2 cluster complete
    ]
    // This list shrinks each cycle as Phase 3 catches up.
    const present: MechanicType[] = []
    for (const type of MISSING) {
      if (mechanicRegistry.has(type)) present.push(type)
    }
    expect(present).toEqual([])
  })
})
