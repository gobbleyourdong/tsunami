// Action Blocks + Mechanics — compiler (step 4 of implementation plan).
//
// Lowers a ValidatedDesign into a GameDefinition consumable by
// `Game.fromDefinition(def)`. Produces a minimal-but-runnable game:
//   - config.mode / camera / gravity from design.config
//   - one Scene per FlowNode in the flow tree (flattened to a linear sequence
//     of FlowSteps for GameFlow.setFlow())
//   - archetype spawn_lists from room/level specs → entities with
//     position/rotation/scale baked
//   - mechanics handed off to the runtime mechanic registry (see
//     mechanics/*.ts modules); compiler records them in scene.properties
//     so the harness can instantiate them at scene start.
//
// Mechanics that don't fit the serialized EntityDefinition shape (timers,
// spawners, HUD overlays) are lowered to a side-table on the scene. The
// harness reads `scene.properties.mechanics` at scene start and constructs
// runtime instances from the design's MechanicInstance[].

import type {
  ActionRef,
  Archetype,
  DesignScript,
  FlowNode,
  MechanicInstance,
  ValidatedDesign,
} from './schema'
import type {
  EntityDefinition,
  GameConfig,
  GameDefinition,
  SceneDefinition,
} from '../game/game'
import type { FlowStep } from '../flow/game_flow'

interface LoweringContext {
  design: ValidatedDesign
  scenes: Record<string, SceneDefinition>
  flow: FlowStep[]
  // Index mechanics by id for lookup during flow lowering.
  mechanicById: Map<string, MechanicInstance>
}

export function compile(design: ValidatedDesign): GameDefinition {
  const config = lowerConfig(design)
  const ctx: LoweringContext = {
    design,
    scenes: {},
    flow: [],
    mechanicById: new Map(
      (design.mechanics ?? []).map(m => [m.id as unknown as string, m]),
    ),
  }

  lowerFlow(design.flow, ctx, null)

  // Guarantee at least one scene exists even if the flow tree is empty.
  if (Object.keys(ctx.scenes).length === 0) {
    ctx.scenes.main = makeEmptyScene('main', design)
    ctx.flow.push({ scene: 'main' })
  }

  return {
    config,
    scenes: ctx.scenes,
    flow: ctx.flow,
  }
}


// ───────── config lowering ─────────

function lowerConfig(design: ValidatedDesign): Required<GameConfig> {
  const c = design.config ?? ({} as Record<string, unknown>)
  return {
    mode: (c.mode as '2d' | '3d') ?? '3d',
    width: (c as Record<string, number>).width ?? 1280,
    height: (c as Record<string, number>).height ?? 720,
    title: design.meta?.title ?? 'Tsunami Game',
    pixelPerfect: false,
    camera: c.camera ?? 'perspective',
    gravity: c.gravity ?? [0, -9.81, 0],
    physicsRate: 60,
    antialias: true,
  }
}


// ───────── flow lowering ─────────

function lowerFlow(
  node: FlowNode | undefined,
  ctx: LoweringContext,
  parentScene: string | null,
): void {
  if (!node) return
  const name = sceneName(node, parentScene)

  if (node.kind === 'scene') {
    ctx.scenes[name] = makeScene(name, ctx.design, {
      archetypeSpawns: [],
      onEnter: (node as Record<string, unknown>).on_enter as ActionRef | undefined,
      mechanicIds: idsForScene(name, ctx),
    })
    ctx.flow.push({
      scene: name,
      transition: lowerTransitionKind(node.transition?.type),
      duration: node.transition?.duration_ms,
    })
    if (Array.isArray(node.children)) {
      node.children.forEach(child => lowerFlow(child, ctx, name))
    }
    return
  }

  if (node.kind === 'level_sequence') {
    const mech = ctx.mechanicById.get(node.sequence_ref as unknown as string)
    const levels = (mech?.params as Record<string, unknown> | undefined)?.levels as
      Array<Record<string, unknown>> | undefined
    if (!levels) {
      ctx.scenes[name] = makeEmptyScene(name, ctx.design)
      ctx.flow.push({ scene: name })
      return
    }
    for (const level of levels) {
      const lname = `${name}.${level.id}`
      ctx.scenes[lname] = makeScene(lname, ctx.design, {
        archetypeSpawns: (level.spawn_list ?? []) as Array<{
          archetype: string
          at: [number, number] | [number, number, number]
        }>,
        mechanicIds: idsForScene(name, ctx),
      })
      ctx.flow.push({ scene: lname, condition: level.win_condition as string | undefined })
    }
    return
  }

  if (node.kind === 'room_graph') {
    const mech = ctx.mechanicById.get(node.graph_ref as unknown as string)
    const rooms = (mech?.params as Record<string, unknown> | undefined)?.rooms as
      Array<Record<string, unknown>> | undefined
    if (!rooms) {
      ctx.scenes[name] = makeEmptyScene(name, ctx.design)
      ctx.flow.push({ scene: name })
      return
    }
    for (const room of rooms) {
      const rname = `${name}.${room.id}`
      ctx.scenes[rname] = makeScene(rname, ctx.design, {
        archetypeSpawns: (room.spawn_list ?? []) as Array<{
          archetype: string
          at: [number, number] | [number, number, number]
        }>,
        mechanicIds: idsForScene(name, ctx),
      })
    }
    // Start room is the flow entry; transitions are driven at runtime by
    // the RoomGraph mechanic rather than baked into FlowStep ordering.
    const startRoom = (mech?.params as Record<string, unknown> | undefined)?.start_room as
      string | undefined
    ctx.flow.push({ scene: `${name}.${startRoom ?? rooms[0].id}` })
    return
  }

  if (node.kind === 'round_match') {
    ctx.scenes[name] = makeEmptyScene(name, ctx.design)
    ctx.flow.push({
      scene: name,
      condition: node.victor_condition as unknown as string,
    })
    return
  }

  if (node.kind === 'linear') {
    for (const step of node.steps) {
      const sname = step.scene as unknown as string
      if (!(sname in ctx.scenes)) {
        ctx.scenes[sname] = makeEmptyScene(sname, ctx.design)
      }
      ctx.flow.push({
        scene: sname,
        condition: step.condition as string | undefined,
        transition: lowerTransitionKind(step.transition?.type),
        duration: step.transition?.duration_ms,
      })
    }
    return
  }
}

function sceneName(node: FlowNode, parent: string | null): string {
  const own = node.name as unknown as string
  if (!parent) return own
  return `${parent}/${own}`
}

function lowerTransitionKind(t: 'fade' | 'cut' | 'slide' | undefined) {
  // scene_manager's TransitionType values — forward the exact string; the
  // scene manager validates it. `cut` is the default no-transition kind.
  if (!t) return undefined
  return t as 'fade' | 'cut' | 'slide'
}


// ───────── scene assembly ─────────

interface MakeSceneOpts {
  archetypeSpawns: Array<{
    archetype: string
    at: [number, number] | [number, number, number]
  }>
  onEnter?: ActionRef
  mechanicIds: string[]
}

function makeScene(name: string, design: ValidatedDesign, opts: MakeSceneOpts): SceneDefinition {
  const entities: EntityDefinition[] = opts.archetypeSpawns.map(s => {
    const arch = design.archetypes?.[s.archetype]
    return archetypeToEntity(s.archetype, arch, s.at)
  })

  const sceneProps: Record<string, unknown> = {
    mechanics: opts.mechanicIds,
  }
  if (opts.onEnter) sceneProps.on_enter = opts.onEnter

  return {
    name,
    entities,
    camera: defaultCamera(design),
    lighting: defaultLighting(),
    // Stash per-scene metadata on an auxiliary prop key. SceneDefinition
    // doesn't declare `properties`, but it's a plain object and the
    // harness reads extra fields tolerantly.
    ...(Object.keys(sceneProps).length > 0
      ? ({ properties: sceneProps } as Record<string, unknown>)
      : {}),
  } as SceneDefinition
}

function makeEmptyScene(name: string, design: ValidatedDesign): SceneDefinition {
  return makeScene(name, design, { archetypeSpawns: [], mechanicIds: [] })
}

function archetypeToEntity(
  archetypeId: string,
  arch: Archetype | undefined,
  at: [number, number] | [number, number, number],
): EntityDefinition {
  const position: [number, number, number] =
    at.length === 3 ? at : [at[0], 0, at[1]]
  return {
    name: `${archetypeId}_${cheapHash(position)}`,
    type: archetypeId,
    position,
    rotation: [0, 0, 0],
    scale: [1, 1, 1],
    properties: {
      mesh: arch?.mesh,
      controller: arch?.controller,
      ai: arch?.ai,
      trigger: arch?.trigger,
      components: arch?.components ?? [],
      tags: arch?.tags ?? [],
    },
  }
}

function cheapHash(pos: [number, number, number]): string {
  return `${pos[0]|0}_${pos[1]|0}_${pos[2]|0}`
}

function defaultCamera(design: ValidatedDesign) {
  return design.config?.mode === '2d'
    ? { position: [0, 0, 10] as [number, number, number],
        target: [0, 0, 0] as [number, number, number], fov: 50 }
    : { position: [0, 8, 14] as [number, number, number],
        target: [0, 0, 0] as [number, number, number], fov: 50 }
}

function defaultLighting() {
  return {
    ambient: [0.2, 0.22, 0.28] as [number, number, number],
    directional: {
      direction: [-0.3, -1, -0.2] as [number, number, number],
      intensity: 1.0,
      color: [1, 0.96, 0.9] as [number, number, number],
    },
  }
}


// ───────── mechanic scene-assignment ─────────

// v1 heuristic: every mechanic applies to every scene. More nuanced
// per-scene scoping (e.g., HUD only in gameplay) can come later via a
// `scenes?: SceneName[]` field on MechanicInstance.
function idsForScene(_sceneName: string, ctx: LoweringContext): string[] {
  return [...ctx.mechanicById.keys()]
}
