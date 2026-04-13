/**
 * Checkpoint/save system.
 * Serializes game state to JSON, stores in localStorage or custom backend.
 */

export interface SaveData {
  version: number
  timestamp: number
  checkpoint: string
  state: Record<string, unknown>
}

export type SaveBackend = {
  save(key: string, data: string): void
  load(key: string): string | null
  delete(key: string): void
  list(): string[]
}

/** localStorage backend (browser). */
export const localStorageBackend: SaveBackend = {
  save(key, data) { localStorage.setItem(key, data) },
  load(key) { return localStorage.getItem(key) },
  delete(key) { localStorage.removeItem(key) },
  list() {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith('save_')) keys.push(key)
    }
    return keys
  },
}

/** In-memory backend (testing / SSR). */
export class MemorySaveBackend implements SaveBackend {
  private store = new Map<string, string>()
  save(key: string, data: string) { this.store.set(key, data) }
  load(key: string) { return this.store.get(key) ?? null }
  delete(key: string) { this.store.delete(key) }
  list() { return Array.from(this.store.keys()) }
}

export class CheckpointSystem {
  private backend: SaveBackend
  private version: number
  private providers = new Map<string, {
    serialize: () => unknown
    deserialize: (data: unknown) => void
  }>()

  currentCheckpoint = ''

  constructor(backend?: SaveBackend, version = 1) {
    this.backend = backend ?? new MemorySaveBackend()
    this.version = version
  }

  /** Register a serializable system (health, inventory, player position, etc). */
  register(key: string, provider: {
    serialize: () => unknown
    deserialize: (data: unknown) => void
  }): void {
    this.providers.set(key, provider)
  }

  /** Set current checkpoint name (for respawn). */
  setCheckpoint(name: string): void {
    this.currentCheckpoint = name
  }

  /** Save game state to a named slot. */
  save(slotName = 'auto'): void {
    const state: Record<string, unknown> = {}
    for (const [key, provider] of this.providers) {
      state[key] = provider.serialize()
    }
    const saveData: SaveData = {
      version: this.version,
      timestamp: Date.now(),
      checkpoint: this.currentCheckpoint,
      state,
    }
    this.backend.save(`save_${slotName}`, JSON.stringify(saveData))
  }

  /** Load game state from a named slot. Returns false if slot doesn't exist. */
  load(slotName = 'auto'): boolean {
    const raw = this.backend.load(`save_${slotName}`)
    if (!raw) return false

    const saveData: SaveData = JSON.parse(raw)
    if (saveData.version !== this.version) return false

    this.currentCheckpoint = saveData.checkpoint
    for (const [key, provider] of this.providers) {
      if (key in saveData.state) {
        provider.deserialize(saveData.state[key])
      }
    }
    return true
  }

  /** Delete a save slot. */
  deleteSave(slotName: string): void {
    this.backend.delete(`save_${slotName}`)
  }

  /** List available save slots. */
  listSaves(): string[] {
    return this.backend.list().map(k => k.replace('save_', ''))
  }

  /** Check if a save slot exists. */
  hasSave(slotName = 'auto'): boolean {
    return this.backend.load(`save_${slotName}`) !== null
  }
}
