/**
 * Scaffold-author ergonomic helpers for wiring ParallaxScroll from
 * sprite_sheets extraction data.
 *
 * Without these helpers a scaffold author needs to:
 *   1. loadExtractionIndex([essence])
 *   2. getParallax3LayerForEssence(essence) or getBackgroundLayersForEssence
 *   3. build ParallaxScrollLayer[] from the returned entries
 *   4. build ParallaxScrollParams + MechanicInstance
 *   5. register via mechanicRegistry.create
 *
 * `configureParallax3LayerFromEssence(essence, ...)` collapses 2-4 into
 * one call; `configureParallaxSingleLayerFromEssence` handles the
 * parallax_single case (NES-era / Raiden-style).
 *
 * The caller still does step 1 (load) + step 5 (register via
 * mechanicRegistry). These helpers only build the instance.
 */

import type {
  ArchetypeId,
  MechanicId,
  MechanicInstance,
  ParallaxScrollLayer,
  ParallaxScrollParams,
} from '../design/schema'
import {
  getParallax3LayerForEssence,
  getBackgroundLayersForEssence,
  type TaggedAnimation,
} from './kind_index'

/** Build a ParallaxScroll MechanicInstance from a 3-layer essence.
 *  Returns null if the essence doesn't have a complete far/mid/near
 *  triple (caller can fall back to single-layer mode). */
export function configureParallax3LayerFromEssence(
  essence: string,
  followArchetype: ArchetypeId,
  opts: {
    instance_id?: MechanicId
    axes?: 'horizontal' | 'vertical' | 'both'
    bounds?: ParallaxScrollParams['bounds']
  } = {},
): MechanicInstance | null {
  const trio = getParallax3LayerForEssence(essence)
  if (!trio) return null
  const layers: ParallaxScrollLayer[] = [
    layerFromEntry(trio.far, -10),
    layerFromEntry(trio.mid, -5),
    layerFromEntry(trio.near, 0),
  ]
  return {
    id: opts.instance_id ?? (`parallax_${essence}` as MechanicId),
    type: 'ParallaxScroll',
    params: {
      follow_archetype: followArchetype,
      axes: opts.axes ?? 'horizontal',
      layers,
      bounds: opts.bounds,
    } as ParallaxScrollParams,
  }
}

/** Build a ParallaxScroll MechanicInstance from a single-layer essence.
 *  Returns null if no parallax_single entry exists for the essence. */
export function configureParallaxSingleLayerFromEssence(
  essence: string,
  followArchetype: ArchetypeId,
  opts: {
    instance_id?: MechanicId
    axes?: 'horizontal' | 'vertical' | 'both'
    bounds?: ParallaxScrollParams['bounds']
  } = {},
): MechanicInstance | null {
  const bgs = getBackgroundLayersForEssence(essence)
  const single = bgs.find((t) => t.anim.sub_kind === 'parallax_single')
  if (!single) return null
  return {
    id: opts.instance_id ?? (`parallax_${essence}` as MechanicId),
    type: 'ParallaxScroll',
    params: {
      follow_archetype: followArchetype,
      axes: opts.axes ?? 'horizontal',
      layers: [layerFromEntry(single, -5)],
      bounds: opts.bounds,
    } as ParallaxScrollParams,
  }
}

/** Generic: use all background_layer entries for an essence, regardless
 *  of sub_kind shape. Useful for essences with mode7 or mixed layer
 *  compositions. Layers are assigned z-depth based on sub_kind:
 *    parallax_far → -10, parallax_mid → -5, parallax_near → 0,
 *    parallax_single → -5, mode7_horizon → -8, mode7_floor → 0,
 *    skybox_static → -100
 *  Returns null if no background_layer entries exist for the essence. */
export function configureParallaxFromEssence(
  essence: string,
  followArchetype: ArchetypeId,
  opts: {
    instance_id?: MechanicId
    axes?: 'horizontal' | 'vertical' | 'both'
    bounds?: ParallaxScrollParams['bounds']
  } = {},
): MechanicInstance | null {
  const bgs = getBackgroundLayersForEssence(essence)
  if (bgs.length === 0) return null
  const layers: ParallaxScrollLayer[] = bgs.map((t) =>
    layerFromEntry(t, zForSubKind(t.anim.sub_kind)),
  )
  // Sort by z ascending so the layer list is draw-order correct.
  layers.sort((a, b) => (a.layer_z ?? 0) - (b.layer_z ?? 0))
  return {
    id: opts.instance_id ?? (`parallax_${essence}` as MechanicId),
    type: 'ParallaxScroll',
    params: {
      follow_archetype: followArchetype,
      axes: opts.axes ?? 'horizontal',
      layers,
      bounds: opts.bounds,
    } as ParallaxScrollParams,
  }
}

/** Extract a ParallaxScrollLayer from a tagged animation. Uses the
 *  entry's `background_params` for scroll_speed_ratio + loop flag;
 *  falls back to sub_kind-derived defaults if those fields aren't set
 *  (e.g., migrated entries from the tile→background_layer promotion
 *  don't have background_params). */
function layerFromEntry(t: TaggedAnimation, defaultZ: number): ParallaxScrollLayer {
  const bp = t.anim.background_params
  const subKind = t.anim.sub_kind
  return {
    sprite_id: t.anim.name,  // extraction `name` becomes loader sprite_id
    scroll_speed_ratio: bp?.scroll_speed_ratio ?? defaultRatioForSubKind(subKind),
    layer_z: defaultZ,
    loops_horizontally: bp?.loops_horizontally ?? true,
    lock_y: subKind === 'mode7_horizon' || subKind === 'skybox_static',
  }
}

/** Default scroll_speed_ratio when background_params isn't populated
 *  (e.g., on entries migrated from tile::background). */
function defaultRatioForSubKind(sk?: string): number {
  switch (sk) {
    case 'parallax_far':      return 0.25
    case 'parallax_mid':      return 0.50
    case 'parallax_near':     return 0.75
    case 'parallax_single':   return 1.0
    case 'mode7_horizon':     return 0.0
    case 'mode7_floor':       return 1.0
    case 'skybox_static':     return 0.0
    default:                  return 0.5  // sensible default for untagged
  }
}

/** z-depth from sub_kind. Used by the generic `configureParallaxFromEssence`. */
function zForSubKind(sk?: string): number {
  switch (sk) {
    case 'parallax_far':      return -10
    case 'parallax_mid':      return -5
    case 'parallax_near':     return 0
    case 'parallax_single':   return -5
    case 'mode7_horizon':     return -8
    case 'mode7_floor':       return 0
    case 'skybox_static':     return -100
    default:                  return -5
  }
}
