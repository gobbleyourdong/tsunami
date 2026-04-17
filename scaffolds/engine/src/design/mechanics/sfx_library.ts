// SfxLibrary — Phase 5 audio-extension mechanic (v1.1).
//
// Pre-renders all sfxr presets into the engine's buffer map at init
// time under ids of the form `${mechanicId}.${presetName}`. Downstream
// ActionRef dispatch (kind: 'play_sfx_ref' { library_ref, preset }) maps
// to `AudioEngine.play('${library_ref}.${preset}')`.
//
// The runtime itself has no per-frame work — it exists to own the
// registration lifecycle and expose the preset list for HUD / debug.

import type { Game } from '../../game/game'
import type {
  MechanicInstance,
  SfxLibraryParams,
} from '../schema'
import { AudioEngine } from '../../audio/engine'
import { Sfxr } from '../../audio/sfxr'
import { mechanicRegistry, type MechanicRuntime } from './index'

class SfxLibraryRuntime implements MechanicRuntime {
  private params: SfxLibraryParams
  private engine: AudioEngine | null = null
  private sfxr: Sfxr | null = null
  private registeredIds: string[] = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as SfxLibraryParams
  }

  init(game: Game): void {
    try {
      this.engine = this.resolveEngine(game)
      this.engine.init()
      this.sfxr = new Sfxr(this.engine)
    } catch {
      // Headless or no-AudioContext environment: skip pre-render.
      this.engine = null
      this.sfxr = null
      return
    }
    for (const [name, params] of Object.entries(this.params.sfx ?? {})) {
      const id = `${this.instance.id}.${name}`
      try {
        this.sfxr.generateAndRegister(id, params)
        this.registeredIds.push(id)
      } catch {
        // Individual preset failure (degenerate params) shouldn't nuke
        // the rest of the library.
      }
    }
  }

  update(_dt: number): void { /* static library, no per-frame work */ }

  dispose(): void {
    this.registeredIds.length = 0
  }

  expose(): Record<string, unknown> {
    return {
      preset_count: this.registeredIds.length,
      presets: this.registeredIds.map(id => id.split('.').slice(1).join('.')),
    }
  }

  private resolveEngine(game: Game): AudioEngine {
    const existing = (game as unknown as { audio?: unknown }).audio
    if (existing instanceof AudioEngine) return existing
    return new AudioEngine()
  }
}

mechanicRegistry.register('SfxLibrary', (instance, game) => {
  const rt = new SfxLibraryRuntime(instance)
  rt.init(game)
  return rt
})
