/**
 * Game systems module — public API barrel export.
 */

export { HealthSystem } from './health'
export type { DamageType, DamageEvent } from './health'
export { Inventory } from './inventory'
export type { ItemDef, InventorySlot } from './inventory'
export { CheckpointSystem, MemorySaveBackend, localStorageBackend } from './checkpoint'
export type { SaveData, SaveBackend } from './checkpoint'
export { ScoreSystem } from './score'
