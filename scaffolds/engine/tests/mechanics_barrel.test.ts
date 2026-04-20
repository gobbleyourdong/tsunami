/**
 * Phase 1 — mechanics barrel smoke test.
 *
 * Verifies @engine/mechanics resolves cleanly and the registry contains
 * the expected runtime implementations from design/mechanics/*.
 */

import { describe, it, expect } from 'vitest'
import { mechanicRegistry } from '../src/mechanics'
import type { MechanicType } from '../src/design/schema'

// 35 MechanicTypes that have runtime implementations per FRAMEWORK_MANIFEST.md.
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

  it('does NOT have the 13 missing mechanics registered (per manifest)', () => {
    const MISSING: MechanicType[] = [
      'HUD', 'UtilityAI', 'RoleAssignment', 'CrowdSimulation',
      'TimeReverseMechanic', 'PhysicsModifier', 'MinigamePool',
      'ATBCombat', 'TurnBasedCombat', 'PartyComposition',
      'LevelUpProgression', 'WorldMapTravel', 'EquipmentLoadout',
    ]
    // This test documents the current gap — it should FAIL once Phase 3
    // lands implementations for these. Flip the assertion then.
    const present: MechanicType[] = []
    for (const type of MISSING) {
      if (mechanicRegistry.has(type)) present.push(type)
    }
    // Currently we expect all 13 to be unregistered.
    expect(present).toEqual([])
  })
})
