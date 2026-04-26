import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  snapshotStyles,
  saveToStorage,
  tryLoadFromStorage,
  STORAGE_KEY,
} from '../src/character3d/face_pixel_editor'
import { EYE_STYLES, MOUTH_STYLES } from '../src/character3d/face_pixels'

interface MockStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function installMockLocalStorage(): MockStorage {
  const store = new Map<string, string>()
  const mock: MockStorage = {
    getItem(k) { return store.get(k) ?? null },
    setItem(k, v) { store.set(k, v) },
    removeItem(k) { store.delete(k) },
  }
  ;(globalThis as { localStorage?: MockStorage }).localStorage = mock
  return mock
}

function clearMockLocalStorage() {
  delete (globalThis as { localStorage?: MockStorage }).localStorage
}

describe('face pixel editor — localStorage persistence', () => {
  let originalEye: ReturnType<typeof snapshotStyles>['eye']
  let originalMouth: ReturnType<typeof snapshotStyles>['mouth']

  beforeEach(() => {
    installMockLocalStorage()
    // Snapshot current state so each test can restore it without
    // contaminating other suites that read EYE_STYLES / MOUTH_STYLES.
    const snap = snapshotStyles()
    originalEye = snap.eye
    originalMouth = snap.mouth
  })

  afterEach(() => {
    // Restore the live registries to their pre-test state.
    for (let i = 0; i < EYE_STYLES.length; i++)   EYE_STYLES[i]   = originalEye[i]
    for (let i = 0; i < MOUTH_STYLES.length; i++) MOUTH_STYLES[i] = originalMouth[i]
    clearMockLocalStorage()
  })

  it('snapshot deep-clones — mutating the snapshot does not change registries', () => {
    const snap = snapshotStyles()
    snap.eye[0].pixels.push({ dx: 99, dy: 99, slot: 'pupil' })
    // Live registry stays unchanged.
    expect(EYE_STYLES[0].pixels.find((p) => p.dx === 99)).toBeUndefined()
  })

  it('saveToStorage + tryLoadFromStorage round-trip', () => {
    // Mutate live state slightly.
    EYE_STYLES[0].pixels.push({ dx: 0, dy: 0, slot: 'tear' })
    saveToStorage()
    // Reset live state then reload.
    EYE_STYLES[0].pixels = EYE_STYLES[0].pixels.slice(0, -1)
    expect(EYE_STYLES[0].pixels.find((p) => p.slot === 'tear' && p.dx === 0 && p.dy === 0)).toBeUndefined()
    const loaded = tryLoadFromStorage()
    expect(loaded).toBe(true)
    expect(EYE_STYLES[0].pixels.find((p) => p.slot === 'tear' && p.dx === 0 && p.dy === 0)).toBeDefined()
  })

  it('tryLoadFromStorage returns false when nothing is saved', () => {
    expect(tryLoadFromStorage()).toBe(false)
  })

  it('tryLoadFromStorage rejects mismatched eye-style count', () => {
    const ls = (globalThis as { localStorage: MockStorage }).localStorage
    ls.setItem(STORAGE_KEY, JSON.stringify({
      eye: [{ name: 'lone', pixels: [] }],   // wrong length (canonical = 7)
      mouth: MOUTH_STYLES.map((m) => ({ name: m.name, pixels: m.pixels })),
    }))
    expect(tryLoadFromStorage()).toBe(false)
  })

  it('tryLoadFromStorage rejects malformed JSON', () => {
    const ls = (globalThis as { localStorage: MockStorage }).localStorage
    ls.setItem(STORAGE_KEY, '{ not valid json')
    expect(tryLoadFromStorage()).toBe(false)
  })

  it('tryLoadFromStorage rejects missing eye/mouth arrays', () => {
    const ls = (globalThis as { localStorage: MockStorage }).localStorage
    ls.setItem(STORAGE_KEY, JSON.stringify({ eye: [], mouth: 'not an array' }))
    expect(tryLoadFromStorage()).toBe(false)
  })

  it('tryLoadFromStorage rejects entries missing pixels arrays', () => {
    const ls = (globalThis as { localStorage: MockStorage }).localStorage
    const eye = EYE_STYLES.map((e, i) =>
      i === 0 ? { name: e.name }    // missing pixels[]
              : { name: e.name, pixels: e.pixels },
    )
    const mouth = MOUTH_STYLES.map((m) => ({ name: m.name, pixels: m.pixels }))
    ls.setItem(STORAGE_KEY, JSON.stringify({ eye, mouth }))
    expect(tryLoadFromStorage()).toBe(false)
  })

  it('saveToStorage no-ops gracefully when localStorage is unavailable', () => {
    clearMockLocalStorage()
    expect(() => saveToStorage()).not.toThrow()
    expect(() => tryLoadFromStorage()).not.toThrow()
  })
})
