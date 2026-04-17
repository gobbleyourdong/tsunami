// Action Blocks + Mechanics — validator (step 3 of implementation plan).
//
// Port target: takes a raw DesignScript object, walks the full tree, and
// returns either {ok: true, design: ValidatedDesign} or {ok: false, errors}.
// Every error carries a structured `kind` (one of the 12 discriminants in
// ValidationError), a dotted path, a human message, and optional suggestions.
//
// Note: the implementation plan said "8 error classes" but the
// ValidationError union in schema.ts actually has 12 kinds — updating count
// inline here rather than silently dropping four of them.
//
// Cost model: O(N) in declaration count. All cross-reference lookups are
// O(1) via prebuilt sets. No network, no disk, no async.

import type {
  ActionRef,
  ComponentSpec,
  DesignScript,
  FlowNode,
  MechanicInstance,
  MechanicType,
  ValidatedDesign,
  ValidationError,
  ValidationResult,
} from './schema'
import { CATALOG } from './catalog'

// All MechanicType values accepted by the typed catalog.
const KNOWN_MECHANIC_TYPES: Set<string> = new Set(Object.keys(CATALOG))

// v2 placeholders — catalog lists them but the compiler declines to lower.
const V2_DECLINED: Set<string> = new Set([
  'RoleAssignment', 'CrowdSimulation', 'TimeReverseMechanic', 'PhysicsModifier',
])

// Component grammar: 'Name' | 'Name(arg1,arg2,...)'.
const COMPONENT_PATTERN = /^([A-Z][A-Za-z0-9_]*)(?:\(([^)]*)\))?$/

interface ConditionTracker {
  emitted: Set<string>
  consumed: Array<{ key: string; path: string }>
}

interface ItemTracker {
  declared: Set<string>
  consumed: Array<{ item: string; path: string }>
}


// ───────── helpers ─────────

function err(
  kind: ValidationError['kind'],
  path: string,
  message: string,
  extra?: { hint?: string; suggestions?: string[] },
): ValidationError {
  return { kind, path, message, ...extra }
}

function parseComponent(spec: ComponentSpec): { name: string; args: string[] } | null {
  const m = spec.trim().match(COMPONENT_PATTERN)
  if (!m) return null
  const args = m[2] ? m[2].split(',').map(s => s.trim()).filter(Boolean) : []
  return { name: m[1], args }
}

function walkActionRefs(action: ActionRef | undefined, visit: (a: ActionRef) => void): void {
  if (!action) return
  visit(action)
  if (action.kind === 'sequence') action.actions.forEach(a => walkActionRefs(a, visit))
}


// ───────── main ─────────

export function validate(raw: DesignScript): ValidationResult {
  const errors: ValidationError[] = []
  const archetypeIds = new Set<string>(Object.keys(raw.archetypes ?? {}))
  const singletonIds = new Set<string>(Object.keys(raw.singletons ?? {}))
  const mechanicIds = new Set<string>()

  const cond: ConditionTracker = { emitted: new Set(), consumed: [] }
  const items: ItemTracker = { declared: new Set(), consumed: [] }

  // --- mechanic id uniqueness + type validity ---
  for (let i = 0; i < (raw.mechanics ?? []).length; i++) {
    const m = raw.mechanics[i]
    const p = `mechanics[${i}]`
    if (!m || typeof m !== 'object') {
      errors.push(err('unknown_mechanic_type', p, 'mechanic entry is not an object'))
      continue
    }
    const mid = m.id as unknown as string
    if (mechanicIds.has(mid)) {
      errors.push(err('duplicate_id', `${p}.id`,
        `duplicate mechanic id ${JSON.stringify(mid)}`))
    }
    mechanicIds.add(mid)

    const mtype = m.type as unknown as string
    if (!KNOWN_MECHANIC_TYPES.has(mtype)) {
      errors.push(err('unknown_mechanic_type', `${p}.type`,
        `unknown mechanic type ${JSON.stringify(mtype)}`,
        { suggestions: [...KNOWN_MECHANIC_TYPES].slice(0, 8) }))
      continue
    }
    if (V2_DECLINED.has(mtype)) {
      errors.push(err('out_of_scope', `${p}.type`,
        `${mtype} is a v2 placeholder — compiler declines to lower it`,
        { hint: 'v2 extensions are named but not implemented; remove or move to a v2 scaffold' }))
    }

    const entry = CATALOG[mtype as MechanicType]
    if (entry?.requires_mode && entry.requires_mode !== raw.config?.mode) {
      errors.push(err('playfield_mismatch', `${p}.type`,
        `${mtype} requires mode ${entry.requires_mode}, got ${raw.config?.mode ?? 'unset'}`))
    }
    if (entry?.requires_playfield && entry.requires_playfield !== 'any') {
      const pfKind = raw.config?.playfield?.kind
      if (pfKind !== entry.requires_playfield) {
        errors.push(err('playfield_mismatch', `${p}.type`,
          `${mtype} requires playfield ${entry.requires_playfield}, got ${pfKind ?? 'unset'}`))
      }
    }
    if (entry?.requires_config?.sandbox_compat === false && raw.config?.sandbox) {
      errors.push(err('incompatible_combo', `${p}.type`,
        `${mtype} is not sandbox-compatible but config.sandbox is true`))
    }
  }

  // --- archetype components + tag collection ---
  const tagUnion = new Set<string>()
  for (const [aid, arch] of Object.entries(raw.archetypes ?? {})) {
    const p = `archetypes[${JSON.stringify(aid)}]`
    ;(arch.tags ?? []).forEach(t => tagUnion.add(t))
    for (let ci = 0; ci < (arch.components ?? []).length; ci++) {
      const c = arch.components[ci]
      if (parseComponent(c) === null) {
        errors.push(err('component_parse', `${p}.components[${ci}]`,
          `component ${JSON.stringify(c)} does not match Name or Name(args) grammar`,
          { hint: "e.g. 'Health(100)' or 'Score' — identifier + optional comma-args" }))
      }
    }
  }

  // --- mechanic.requires cross-refs + param sweeps ---
  for (let i = 0; i < (raw.mechanics ?? []).length; i++) {
    const m = raw.mechanics[i]
    const p = `mechanics[${i}]`
    for (let ri = 0; ri < (m.requires ?? []).length; ri++) {
      const ref = m.requires![ri] as unknown as string
      if (!mechanicIds.has(ref)) {
        errors.push(err('unknown_mechanic_ref', `${p}.requires[${ri}]`,
          `mechanic ${JSON.stringify(m.id)} requires ${JSON.stringify(ref)} which is not defined`))
      }
    }
    checkMechanicParamRefs(m, p, {
      archetypes: archetypeIds, mechanics: mechanicIds,
      singletons: singletonIds, cond, items, errors,
    })
    const entry = CATALOG[m.type as MechanicType]
    if (entry?.requires_tags) {
      const missing = entry.requires_tags.filter(t => !tagUnion.has(t))
      if (missing.length > 0) {
        errors.push(err('tag_requirement', `${p}.type`,
          `${m.type} requires tags ${missing.join(', ')} on some archetype, none found`,
          { hint: 'add these tags to an archetype in design.archetypes' }))
      }
    }
  }

  // --- HUD singleton refs ---
  for (let i = 0; i < (raw.mechanics ?? []).length; i++) {
    const m = raw.mechanics[i]
    if (m.type !== 'HUD') continue
    const fields = ((m.params as Record<string, unknown>)?.fields ?? []) as Array<Record<string, unknown>>
    fields.forEach((f, fi) => {
      const s = f.singleton
      if (typeof s === 'string' && !singletonIds.has(s)) {
        errors.push(err('unknown_singleton_ref', `mechanics[${i}].params.fields[${fi}].singleton`,
          `HUD field references singleton ${JSON.stringify(s)} which is not declared`))
      }
    })
  }

  // --- flow tree walk ---
  walkFlow(raw.flow, 'flow', {
    archetypes: archetypeIds, mechanics: mechanicIds,
    singletons: singletonIds, cond, items, errors,
  })

  // --- dangling conditions ---
  for (const { key, path } of cond.consumed) {
    if (!cond.emitted.has(key)) {
      errors.push(err('dangling_condition', path,
        `condition ${JSON.stringify(key)} is consumed but never emitted`,
        { hint: 'use an action {kind: "emit", condition: key} or a LoseOnZero/WinOnCount that emits it' }))
    }
  }

  // --- unknown_item_ref ---
  for (const { item, path } of items.consumed) {
    if (!items.declared.has(item)) {
      errors.push(err('unknown_item_ref', path,
        `item ${JSON.stringify(item)} is referenced but never declared`,
        { hint: 'declare it via ItemUseParams.items[], HotspotMechanic on_pickup, or Shop stock[]' }))
    }
  }

  if (errors.length > 0) return { ok: false, errors }
  return { ok: true, design: raw as ValidatedDesign }
}


// ───────── cross-ref walkers ─────────

interface RefContext {
  archetypes: Set<string>
  mechanics: Set<string>
  singletons: Set<string>
  cond: ConditionTracker
  items: ItemTracker
  errors: ValidationError[]
}

const ARCH_FIELDS = new Set([
  'archetype', 'target_archetype', 'vendor_archetype', 'emitter_archetype',
  'bullet_archetype', 'trigger_archetype', 'beat_spawn_archetype', 'gate_archetype',
])

function checkArchetypeRef(aid: unknown, path: string, ctx: RefContext): void {
  if (typeof aid !== 'string') return
  if (!ctx.archetypes.has(aid)) {
    ctx.errors.push(err('unknown_archetype_ref', path,
      `archetype ${JSON.stringify(aid)} not declared in design.archetypes`))
  }
}

function checkMechanicParamRefs(
  m: MechanicInstance, path: string, ctx: RefContext,
): void {
  const params = m.params as unknown as Record<string, unknown>
  if (!params || typeof params !== 'object') return

  function walk(o: unknown, p: string): void {
    if (o === null || o === undefined) return
    if (Array.isArray(o)) {
      o.forEach((v, i) => walk(v, `${p}[${i}]`))
      return
    }
    if (typeof o !== 'object') return
    for (const [k, v] of Object.entries(o as Record<string, unknown>)) {
      const childPath = `${p}.${k}`
      if (ARCH_FIELDS.has(k)) {
        if (typeof v === 'string') checkArchetypeRef(v, childPath, ctx)
        else if (v && typeof v === 'object'
                 && Array.isArray((v as Record<string, unknown>).any_of)) {
          ((v as Record<string, unknown>).any_of as unknown[]).forEach((aid, i) =>
            checkArchetypeRef(aid, `${childPath}.any_of[${i}]`, ctx))
        }
      }
      if (k === 'emit_condition' && typeof v === 'string') ctx.cond.emitted.add(v)
      if (k === 'win_condition' || k === 'fail_condition'
          || k === 'exit_condition' || k === 'trigger'
          || k === 'requires_condition' || k === 'unlock_condition') {
        if (typeof v === 'string') ctx.cond.consumed.push({ key: v, path: childPath })
        else if (v && typeof v === 'object') {
          const cv = (v as Record<string, unknown>).condition
          if (typeof cv === 'string') ctx.cond.consumed.push({ key: cv, path: childPath })
        }
      }
      if (k === 'items' && Array.isArray(v)) {
        ;(v as Array<Record<string, unknown>>).forEach(item => {
          if (item && typeof item.name === 'string') ctx.items.declared.add(item.name)
        })
      }
      if (k === 'stock' && Array.isArray(v)) {
        ;(v as Array<Record<string, unknown>>).forEach(s => {
          if (s && typeof s.item === 'string') ctx.items.declared.add(s.item)
        })
      }
      if (k === 'recipes' && Array.isArray(v)) {
        ;(v as Array<Record<string, unknown>>).forEach(r => {
          if (r && typeof r.result === 'string') ctx.items.declared.add(r.result)
          if (r && Array.isArray(r.ingredients)) {
            ;(r.ingredients as unknown[]).forEach(ing => {
              if (typeof ing === 'string') ctx.items.consumed.push(
                { item: ing, path: `${childPath}.ingredients` })
            })
          }
        })
      }
      if (k === 'requires_item' && typeof v === 'string') {
        ctx.items.consumed.push({ item: v, path: childPath })
      }
      if (v && typeof v === 'object'
          && typeof (v as Record<string, unknown>).kind === 'string'
          && ACTION_KINDS.has((v as Record<string, unknown>).kind as string)) {
        walkAction(v as ActionRef, childPath, ctx)
      }
      walk(v, childPath)
    }
  }
  walk(params, `${path}.params`)
}

const ACTION_KINDS = new Set<string>([
  'award_score', 'damage', 'heal', 'spawn', 'destroy', 'emit',
  'set_flag', 'play_sound', 'apply_status', 'give_item', 'dialog',
  'scene_goto', 'sequence',
])

function walkAction(a: ActionRef, path: string, ctx: RefContext): void {
  walkActionRefs(a, action => {
    if (action.kind === 'emit') ctx.cond.emitted.add(action.condition as unknown as string)
    if (action.kind === 'give_item') {
      if (typeof action.item === 'string') ctx.items.consumed.push({ item: action.item, path })
    }
    if (action.kind === 'damage' || action.kind === 'heal'
        || action.kind === 'spawn' || action.kind === 'apply_status') {
      checkArchetypeRef((action as Record<string, unknown>).archetype, path, ctx)
    }
    if (action.kind === 'destroy'
        && (action as Record<string, unknown>).archetype !== 'caller') {
      checkArchetypeRef((action as Record<string, unknown>).archetype, path, ctx)
    }
    if (action.kind === 'dialog') {
      const ref = (action as Record<string, unknown>).tree_ref
      if (typeof ref === 'string' && !ctx.mechanics.has(ref)) {
        ctx.errors.push(err('unknown_mechanic_ref', path,
          `dialog tree_ref ${JSON.stringify(ref)} not defined`))
      }
    }
  })
}

function walkFlow(node: FlowNode | undefined, path: string, ctx: RefContext): void {
  if (!node) return
  const p = `${path}.${node.kind}`
  if ('on_enter' in node) walkAction((node as Record<string, unknown>).on_enter as ActionRef, `${p}.on_enter`, ctx)
  if ('on_complete' in node) walkAction((node as Record<string, unknown>).on_complete as ActionRef, `${p}.on_complete`, ctx)
  if (node.kind === 'level_sequence' || node.kind === 'room_graph') {
    const rec = node as Record<string, unknown>
    const ref = (rec.sequence_ref ?? rec.graph_ref) as unknown
    if (typeof ref === 'string' && !ctx.mechanics.has(ref)) {
      ctx.errors.push(err('unknown_mechanic_ref', `${p}.ref`,
        `flow ${node.kind} references mechanic ${JSON.stringify(ref)} which is not defined`))
    }
  }
  if (node.kind === 'round_match') {
    const vc = (node as Record<string, unknown>).victor_condition
    if (typeof vc === 'string') ctx.cond.consumed.push({ key: vc, path: `${p}.victor_condition` })
  }
  if (node.kind === 'scene' && Array.isArray(node.children)) {
    node.children.forEach((c, i) => walkFlow(c, `${p}.children[${i}]`, ctx))
  }
  if (node.kind === 'linear' && Array.isArray(node.steps)) {
    node.steps.forEach((s, i) => {
      if (typeof s.condition === 'string') ctx.cond.consumed.push({
        key: s.condition, path: `${p}.steps[${i}].condition`,
      })
    })
  }
}
