// WorldFlags — Phase 2 composability primitive.
//
// Not a MechanicType — there's no WorldFlags discriminant in the schema's
// MechanicType union. Instead, this is the shared flag-store helper every
// mechanic uses to read/write world_flag state on the active scene. Prior
// to this module dialog_tree and puzzle_object each had their own ad-hoc
// flag readers; centralising keeps them coherent and gives the compiler
// one place to preload flags declared in Singletons.
//
// Storage location: `sceneManager.activeScene().properties.world_flags`
// as a plain object keyed by flag name. The compiler stamps any
// SingletonSpec with kind 'world_flags' into the scene's initial
// properties so designs can declare starting state.

import type { Game } from '../../game/game'

export type WorldFlagValue = boolean | string | number

/** Read a named flag from the active scene's world-flag store. */
export function readWorldFlag(game: Game, key: string): WorldFlagValue | undefined {
  const flags = getFlagStore(game)
  return flags?.[key] as WorldFlagValue | undefined
}

/** Write a named flag to the active scene's world-flag store. Creates the
 *  store lazily if the scene doesn't have one yet. */
export function writeWorldFlag(game: Game, key: string, value: WorldFlagValue): void {
  const flags = getOrCreateFlagStore(game)
  if (!flags) return
  flags[key] = value
}

/** Truthiness probe — used by condition-gated choices / transitions.
 *  true iff the flag exists AND is not false/empty-string/zero. */
export function flagTruthy(game: Game, key: string): boolean {
  const v = readWorldFlag(game, key)
  if (v === undefined || v === null) return false
  if (v === true) return true
  if (v === false) return false
  if (typeof v === 'string') return v.length > 0
  if (typeof v === 'number') return v !== 0
  return false
}

/** Clear all flags — used by CheckpointProgression with mode='reset_scene'. */
export function clearFlags(game: Game): void {
  const flags = getFlagStore(game)
  if (!flags) return
  for (const k of Object.keys(flags)) delete flags[k]
}

/** Dump all flags as a plain object — used by HUD / expose(). */
export function snapshotFlags(game: Game): Record<string, WorldFlagValue> {
  const flags = getFlagStore(game)
  if (!flags) return {}
  return { ...flags } as Record<string, WorldFlagValue>
}

// ─────────────────────────────────────────────────────────────
//   internals
// ─────────────────────────────────────────────────────────────

function getFlagStore(game: Game): Record<string, unknown> | undefined {
  const active = game.sceneManager?.activeScene?.() as
    Record<string, unknown> | undefined
  if (!active) return undefined
  const props = active.properties as Record<string, unknown> | undefined
  if (!props) return undefined
  return props.world_flags as Record<string, unknown> | undefined
}

function getOrCreateFlagStore(game: Game): Record<string, unknown> | null {
  const active = game.sceneManager?.activeScene?.() as
    Record<string, unknown> | undefined
  if (!active) return null
  let props = active.properties as Record<string, unknown> | undefined
  if (!props) {
    props = {}
    ;(active as Record<string, unknown>).properties = props
  }
  let flags = props.world_flags as Record<string, unknown> | undefined
  if (!flags) {
    flags = {}
    props.world_flags = flags
  }
  return flags as Record<string, unknown>
}
