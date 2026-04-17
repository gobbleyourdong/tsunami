// Action Blocks + Mechanics — v1.0 candidate design-script schema
//
// Canonical spec as of attempt_007. The implementing instance ports this
// file to ark/scaffolds/engine/src/design/schema.ts as-is.
//
// Domain per note_005 (numerics): real-time single-protagonist spatial
// games. v1 extensions relax one assumption each:
//   grid mode     — continuous-physics sub-assumption
//   sandbox flag  — win/lose flow-completion requirement
//   narrative subset — partial spatial (cursor + hotspots + dialog)
//   turn mode     — real-time, via TurnManager
//
// Out of scope v1: JRPG battle, full IF, RTS multi-select, persistent
// simulation, racing. See reference/README.md for rationale.

// ───────── branded IDs ─────────

export type ArchetypeId  = string & { __brand: 'ArchetypeId'  }
export type MechanicId   = string & { __brand: 'MechanicId'   }
export type SingletonId  = string & { __brand: 'SingletonId'  }
export type ConditionKey = string & { __brand: 'ConditionKey' }
export type SceneName    = string & { __brand: 'SceneName'    }

// ───────── root ─────────

export interface DesignScript {
  meta:       DesignMeta
  config:     GameRuntimeConfig
  singletons: Record<string, SingletonSpec>       // NEW v1
  archetypes: Record<string, Archetype>
  mechanics:  MechanicInstance[]
  flow:       FlowNode                              // NEW v1 — tree, not list
}

export interface DesignMeta {
  title: string
  shape: 'action' | 'puzzle' | 'sandbox' | 'rhythm' | 'narrative_adjacent'
          | 'skater' | 'fighter' | 'metroidvania' | 'maze_chase'
  vibe: string[]                                    // free-form QA tags
  target_session_sec?: number
}

export interface GameRuntimeConfig {
  mode: '2d' | '3d'
  camera?: 'perspective' | 'orthographic'
  gravity?: [number, number, number]
  playfield: Playfield                              // NEW v1
  sandbox?: boolean                                 // NEW v1 — note_004
}

// v1.0.4 — continuous only. Grid mode moved to future grid-puzzle scaffold.
export type Playfield =
  | { kind: 'continuous', arena: { shape: 'rect' | 'disk', size: number } }

// ───────── singletons ─────────

// NEW v1 — game-global state (Tetris playfield, SF2 round manager, WorldFlags)
export interface SingletonSpec {
  components: ComponentSpec[]
  exposes: Record<string, 'number' | 'string' | 'boolean' | 'list'>
}

// ───────── archetypes ─────────

export type MeshName       = 'box' | 'sphere' | 'capsule' | 'plane' | string
export type ControllerName =
  | 'fps' | 'orbit' | 'topdown' | 'platformer'
  | 'pointer' | 'none'                              // v1.0.4: grid removed (separate scaffold)
  | string
export type AiName         =
  | 'chase' | 'flee' | 'patrol' | 'idle'
  | `bt:${string}` | `fsm:${string}`
  | `utility:${string}`                            // NEW v1 — UtilityAI
/**
 * Component specs parse as 'Name' or 'Name(arg1,arg2)':
 *   Health(100)            → HealthSystem
 *   Score                  → ScoreSystem
 *   Lives(3)               → counter
 *   Resource(name, max?)   → generic resource  (NEW v1)
 *   Inventory              → inventory bag
 *   Checkpoint             → checkpoint state
 *   Stamina(100)           → alias for Resource('stamina', 100)
 */
export type ComponentSpec = string

export interface Archetype {
  mesh?: MeshName
  controller?: ControllerName
  ai?: AiName
  trigger?: TriggerSpec | string                   // string = sugar for {kind: string}
  components: ComponentSpec[]
  tags: string[]
}

// NEW v1 — directional trigger (note_003, our tweak: contact_side instead of from_dir)
export interface TriggerSpec {
  kind: 'pickup' | 'damage' | 'checkpoint' | 'heal'
       | 'stomp' | 'bump' | 'block' | 'hit' | string
  contact_side?: 'top' | 'bottom' | 'side' | 'front' | 'back' | 'any'
  on_contact?: ActionRef
  on_reverse?: ActionRef
  when_state?: string
  exclusive?: boolean
}

// ───────── mechanics (29 types in v1.0) ─────────

export type MechanicType =
  // kept from v0
  | 'Difficulty' | 'HUD' | 'LoseOnZero' | 'WinOnCount'
  | 'WaveSpawner' | 'PickupLoop' | 'ScoreCombos'
  | 'CheckpointProgression' | 'LockAndKey'
  | 'StateMachineMechanic' | 'ComboAttacks' | 'BossPhases'
  | 'RhythmTrack'
  // v0.2 additions (grid-mode removed in v1.0.4 — separate scaffold)
  | 'LevelSequence' | 'RoomGraph'
  | 'ItemUse' | 'GatedTrigger'
  | 'TimedStateModifier' | 'AttackFrames'
  // v0.2.2
  | 'Shop' | 'UtilityAI' | 'DialogTree'
  | 'HotspotMechanic' | 'InventoryCombine'
  // v1.0 (missed in earlier iterations, added from n=15 gap_map)
  | 'CameraFollow' | 'StatusStack'
  // v1.0.1 (batch-4 additions — attempt_008)
  | 'EmbeddedMinigame' | 'EndingBranches' | 'VisionCone'
  // v1.0.2 (batch-5; note_008 puzzle correction)
  | 'PuzzleObject'
  // v1.0.3 (batch-6; note_009 content-multiplier additions)
  | 'ProceduralRoomChain' | 'BulletPattern' | 'RouteMap'
  // v1.1 (audio extension — attempt_004 / audio_handoff.md)
  | 'ChipMusic' | 'SfxLibrary'
  // v2 placeholders (named but not implemented; compiler declines)
  | 'RoleAssignment' | 'CrowdSimulation'
  | 'TimeReverseMechanic' | 'PhysicsModifier'

export interface MechanicInstance {
  id: MechanicId
  type: MechanicType
  params: MechanicParams
  exposes?: Record<string, 'number' | 'string' | 'boolean' | 'list'>  // NEW v1 — promoted
  requires?: MechanicId[]
}

// Per-type param shapes. Compiler validates via discriminated union.
export type MechanicParams =
  | DifficultyParams | HudParams | LoseOnZeroParams | WinOnCountParams
  | WaveSpawnerParams | PickupLoopParams | ScoreCombosParams
  | CheckpointProgressionParams | LockAndKeyParams
  | StateMachineMechanicParams | ComboAttacksParams | BossPhasesParams
  | RhythmTrackParams
  | LevelSequenceParams | RoomGraphParams
  | ItemUseParams | GatedTriggerParams
  | TimedStateModifierParams | AttackFramesParams
  | ShopParams | UtilityAIParams | DialogTreeParams
  | HotspotMechanicParams | InventoryCombineParams
  | CameraFollowParams | StatusStackParams
  | EmbeddedMinigameParams | EndingBranchesParams | VisionConeParams
  | PuzzleObjectParams
  | ProceduralRoomChainParams | BulletPatternParams | RouteMapParams
  // v1.1 audio extension (defined below, after the existing param shapes)
  | ChipMusicParams | SfxLibraryParams
  // v2 placeholders — shape not yet specified; compiler declines
  | { type: 'RoleAssignment'       | 'CrowdSimulation'
            | 'TimeReverseMechanic' | 'PhysicsModifier';
      [key: string]: unknown }

// ───────── param shapes ─────────

export interface DifficultyParams {
  drive: 'time' | 'score' | 'wave_index' | 'level' | 'custom'
  easy: Record<string, number>
  hard: Record<string, number>
  max_level: number
}

export interface HudParams {
  fields: Array<
    | { archetype: ArchetypeId; component: string; label?: string }
    | { mechanic: MechanicId;   field: string;     label?: string }
    | { singleton: SingletonId; field: string;     label?: string }
  >
  layout?: 'top' | 'bottom' | 'corners' | 'minimal'
}

export interface LoseOnZeroParams {
  archetype: ArchetypeId | { any_of: ArchetypeId[] }   // 'any_of' = party-wipe case
  field: string
  emit_condition: ConditionKey
}

export interface WinOnCountParams {
  archetype: ArchetypeId
  count: number
  comparison: 'eq' | 'gte' | 'lte'
  emit_condition: ConditionKey
}

export interface WaveSpawnerParams {
  archetype: ArchetypeId
  difficulty_ref?: MechanicId
  base_count: number
  rest_sec: number
  arena_radius: number
  intro_delay_sec?: number
}

export interface PickupLoopParams {
  archetype: ArchetypeId
  reward_field: string
  reward_amount: number
  respawn: { sec: number } | 'never'           // v0.2.2 — survival-horror scarcity
  max_simultaneous?: number
}

export interface ScoreCombosParams {
  archetype: ArchetypeId
  window_sec: number
  curve: 'linear' | 'quadratic' | 'exponential'
  max_multiplier?: number
  commit?: 'window' | 'event'                  // THPS bank-on-event
  commit_event?: string                         // required when commit='event'
}

export interface CheckpointProgressionParams {
  archetype: ArchetypeId
  mode: 'respawn_in_place' | 'reset_scene' | 'reset_level'
  restore_fields: string[]
}

export interface LockAndKeyParams {
  key_tag: string
  lock_tag: string
  consume_key?: boolean
}

export interface StateMachineMechanicParams {
  archetype: ArchetypeId
  states: Array<{ name: string; enter?: ActionRef; exit?: ActionRef }>
  transitions: Array<{ from: string; to: string; when: string }>  // condition DSL — TODO Ether pass
  initial: string
}

export interface ComboAttacksParams {
  archetype: ArchetypeId
  patterns: Array<{
    name: string
    sequence: string[]
    window_ms: number
    action: ActionRef
    gated_by?: string                           // THPS air-only
  }>
}

export interface BossPhasesParams {
  archetype: ArchetypeId
  phases: Array<{
    health_pct: number
    ai: AiName
    tint?: [number, number, number]
    on_phase_enter?: ActionRef[]                // v0.2.2 — flash/spawn/sound
  }>
}

// TileRewriteMechanic moved to future grid-puzzle scaffold (v1.0.4 rescope).
// Preserved grammar spec in attempt_012 Ether pass for that scaffold's use.

export interface RhythmTrackParams {
  bpm: number
  audio_ref: string
  beat_spawn_archetype: ArchetypeId
  measure: { beats: number; note_value: number }
  hit_window_ms: number
}

// ─── v0.2 adds ───
// GridPlayfield + GridController moved to future grid-puzzle scaffold (v1.0.4).

export interface LevelSequenceParams {
  levels: Array<{
    id: string
    layout_source?: string
    archetype_overrides?: Record<string, Partial<Archetype>>
    spawn_list?: Array<{
      archetype: ArchetypeId
      at: [number, number] | [number, number, number]
    }>
    win_condition?: ConditionKey
    fail_condition?: ConditionKey
    on_win?: 'next' | string
    on_fail?: 'retry' | 'previous' | string
  }>
  start_at: string
  cycle_on_complete?: boolean
}

export interface RoomGraphParams {
  rooms: Array<{
    id: string
    layout_source?: string
    spawn_list?: Array<{ archetype: ArchetypeId; at: [number, number, number] }>
    on_enter?: ActionRef
  }>
  edges: Array<{
    from: string
    to: string
    requires_condition?: ConditionKey             // gated doors
    requires_item?: string
    transition?: 'cut' | 'slide' | 'fade'
  }>
  start_room: string
}

// FallingPiece + LineClear moved to future grid-puzzle scaffold (v1.0.4).

export interface ItemUseParams {
  archetype: ArchetypeId                          // who can use items
  items: Array<{
    name: string
    action: ActionRef
    requires_target_tag?: string                  // hookshot needs 'hook_target' in range
    consume_on_use?: boolean
  }>
  active_slot?: 'a_button' | 'b_button' | 'select'
}

export interface GatedTriggerParams {
  gate_archetype: ArchetypeId                     // the door/path
  opens_when: ConditionKey | { has_item: string } | { tag_present: string }
  open_effect?: ActionRef
}

export interface TimedStateModifierParams {
  archetype: ArchetypeId
  state: string                                   // 'invuln', 'powered_up', 'stunned'
  duration_sec: number
  on_apply?: ActionRef
  on_expire?: ActionRef
  stackable?: boolean
}

export interface AttackFramesParams {
  archetype: ArchetypeId
  states: Array<{
    name: string                                  // 'jab', 'heavy', 'block'
    startup_ms: number
    active_ms: number
    recovery_ms: number
    hitbox?: { offset: [number, number]; size: [number, number] }
    hurtbox_override?: { offset: [number, number]; size: [number, number] }
  }>
}

// TurnManager moved to future turn-based scaffold (v1.0.4 rescope).

// ─── v0.2.2 ───

export interface ShopParams {
  vendor_archetype: ArchetypeId
  currency_field: string
  stock: Array<{
    item: string
    price: number
    unlock_condition?: ConditionKey
    stock_count?: number
  }>
  ui_layout?: 'list' | 'grid' | 'dialog_embedded'
}

export interface UtilityAIParams {
  archetype: ArchetypeId
  needs: Array<{
    name: string
    decay_per_sec: number
    max: number
    initial?: number
  }>
  actions: Array<{
    name: string
    need_deltas: Record<string, number>
    precondition?: string                         // condition DSL — TODO Ether pass
    effect: ActionRef
  }>
  selection: 'highest_need' | 'weighted_sample' | 'expected_utility'
}

export interface DialogTreeParams {
  trigger_archetype?: ArchetypeId                 // NPC that starts dialog on contact
  trigger_hotspot?: string                         // Monkey-Island-style click
  tree: DialogNode
}

export interface DialogNode {
  id: string
  line: string                                    // what gets said
  speaker?: string
  choices?: Array<{
    text: string
    requires?: ConditionKey | { world_flag: string }
    goto?: string                                 // next node id
    effect?: ActionRef
  }>
  on_enter?: ActionRef
}

export interface HotspotMechanicParams {
  scene: SceneName                                // rooms hold hotspots
  hotspots: Array<{
    name: string
    region: { x: number; y: number; w: number; h: number }   // screen-space
    on_examine?: ActionRef
    on_use?: ActionRef
    on_pickup?: ActionRef                         // becomes inventory item
    unlock_condition?: ConditionKey
  }>
}

export interface InventoryCombineParams {
  archetype: ArchetypeId                          // who carries the inventory
  recipes: Array<{
    ingredients: string[]                         // 2 or more items
    result: string
    consumes: 'all' | 'first' | string[]          // which ingredients are consumed
  }>
}

// ─── v1.0 adds ───

export interface CameraFollowParams {
  target_archetype: ArchetypeId
  mode: 'topdown' | 'sidescroll' | 'chase_3d' | 'locked_axis'
  offset?: [number, number, number]
  deadzone?: { width: number; height: number }
  ease?: number                                   // 0 = rigid, 1 = smooth
  bounds?: { min: [number, number, number]; max: [number, number, number] }
}

export interface StatusStackParams {
  archetype: ArchetypeId
  statuses: Array<{
    name: string
    tags: string[]
    duration_sec?: number
    tick_effect?: ActionRef
    on_apply?: ActionRef
    on_expire?: ActionRef
    max_stacks?: number
  }>
  conflict_rules?: Array<{
    if_present: string
    and_applying: string
    resolve: 'remove_present' | 'block_apply' | 'both_remain'
  }>
}

// ─── v1.0.1 adds ───

export interface EmbeddedMinigameParams {
  trigger: ConditionKey
  mechanics: MechanicInstance[]                   // nested design subtree
  suspend_mechanics?: MechanicId[]                // outer mechanics to pause
  exit_condition: ConditionKey
  on_exit?: ActionRef
}

export interface EndingBranchesParams {
  endings: Array<{
    id: string
    requires: Array<
      | { world_flag: string; value?: boolean | string | number }
      | { condition: ConditionKey }
      | { archetype_count: { archetype: ArchetypeId; min?: number; max?: number } }
      | { elapsed_sec: { max?: number } }
    >
    scene: SceneName
    priority?: number
  }>
  default_ending: string
}

export interface VisionConeParams {
  archetype: ArchetypeId                          // the watcher
  target_tags: string[]
  cone_angle_deg: number
  cone_range: number
  line_of_sight?: boolean
  alert_states: Array<{
    name: 'calm' | 'suspicious' | 'alert' | string
    decay_to?: string
    decay_sec?: number
    on_enter?: ActionRef
    ai_override?: AiName
  }>
  initial_state: string
}

// ─── v1.0.2 adds ───

export interface PuzzleObjectParams {
  archetype: ArchetypeId
  states: Array<{
    name: string
    mesh?: MeshName
    tint?: [number, number, number]
    on_enter?: ActionRef
  }>
  transitions: Array<{
    from: string
    to: string
    triggered_by:
      | { interaction: 'examine' | 'use' | 'touch' }
      | { item_used: string }
      | { world_flag: string; value?: unknown }
      | { adjacent_state: { archetype: ArchetypeId; state: string } }
    effect?: ActionRef
  }>
  initial_state: string
}

// ─── v1.0.3 adds — content-multiplier mechanics ───

export interface ProceduralRoomChainParams {
  room_pool: Array<{
    id: string
    layout_source?: string
    weight?: number
    min_depth?: number
    max_depth?: number
    exclusive_with?: string[]
  }>
  connection_rules: {
    min_rooms_per_run: number
    max_rooms_per_run: number
    branch_factor?: number
    reward_rooms_per_chain?: number
    elite_room_after?: number
  }
  run_lifecycle: {
    on_run_start?: ActionRef
    on_room_complete?: ActionRef
    on_run_complete?: ActionRef
    on_run_fail?: ActionRef
  }
}

export interface BulletPatternParams {
  emitter_archetype: ArchetypeId
  patterns: Array<{
    name: string
    bullet_archetype: ArchetypeId
    layout: 'line' | 'ring' | 'spiral' | 'spread' | 'aimed' | 'custom'
    layout_params: Record<string, number>
    duration_ms?: number
    trigger_condition?: string
  }>
  sequence: 'round_robin' | 'weighted' | 'scripted'
  scripted_order?: string[]
}

export interface RouteMapParams {
  nodes: Array<{
    id: string
    kind: 'battle' | 'elite' | 'event' | 'shop' | 'rest' | 'boss' | 'treasure'
    depth: number
    scene: SceneName | { ref_mechanic: MechanicId }
    reward?: ActionRef
  }>
  edges: Array<{ from: string; to: string }>
  start_nodes: string[]
  boss_node: string
  layout: 'layered_dag' | 'tree' | 'graph'
}

// ───────── flow (v1 — tree) ─────────

export type FlowNode =
  | { kind: 'scene', name: SceneName,
      on_enter?: ActionRef, transition?: TransitionSpec, children?: FlowNode[] }
  | { kind: 'level_sequence', name: SceneName, sequence_ref: MechanicId,
      on_complete?: ActionRef }
  | { kind: 'room_graph', name: SceneName, graph_ref: MechanicId,
      on_complete?: ActionRef }
  | { kind: 'round_match', name: SceneName, best_of: number,
      round_scene: SceneName, victor_condition: ConditionKey }
  | { kind: 'linear', name: SceneName, steps: Array<{ scene: SceneName;
      condition?: ConditionKey; transition?: TransitionSpec }> }

export interface TransitionSpec {
  type: 'fade' | 'cut' | 'slide'
  duration_ms?: number
}

// ───────── shared ─────────

export type ActionRef =
  | { kind: 'award_score'; amount: number }
  | { kind: 'damage';      archetype: ArchetypeId; amount: number;
      damage_type?: string }
  | { kind: 'heal';        archetype: ArchetypeId; amount: number }
  | { kind: 'spawn';       archetype: ArchetypeId;
      at?: 'caller' | 'player' | [number, number] | [number, number, number] }
  | { kind: 'destroy';     archetype: ArchetypeId | 'caller' }
  | { kind: 'emit';        condition: ConditionKey }
  | { kind: 'set_flag';    world_flag: string; value: boolean | string | number }
  | { kind: 'play_sound';  asset: string; volume?: number }
  | { kind: 'apply_status'; archetype: ArchetypeId; status: string }
  | { kind: 'give_item';   archetype: ArchetypeId; item: string }
  | { kind: 'dialog';      tree_ref: MechanicId; entry_node?: string }
  | { kind: 'scene_goto';  scene: SceneName }
  | { kind: 'sequence';    actions: ActionRef[] }
  // v1.1 audio extension — 7 new kinds (see ChipMusic / SfxLibrary below).
  // Four support optional quantize_to + quantize_source so sfx fire on
  // beat boundaries of a referenced ChipMusic mechanic.
  | { kind: 'play_sfx';        params: SfxrParams;
      quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
  | { kind: 'play_sfx_ref';    library_ref: MechanicId; preset: string;
      quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
  | { kind: 'play_sfx_loop';   id: string; params: SfxrParams;
      quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
  | { kind: 'play_sfx_loop_ref'; id: string; library_ref: MechanicId;
      preset: string;
      quantize_to?: QuantizeGrid; quantize_source?: MechanicId }
  | { kind: 'stop_sfx_loop';   id: string }
  | { kind: 'play_chiptune';   track_ref: MechanicId }
  | { kind: 'stop_chiptune';   track_ref: MechanicId; release_tail?: boolean }

// ───────── v1.1 audio extension ─────────
//
// Parallel to the game mechanics above: procedural chiptune (ChipMusic)
// + sfxr-style retro SFX library (SfxLibrary). Runtime impls live in
// scaffolds/engine/src/audio/chipsynth.ts and sfxr.ts; this section only
// declares the schema types the design/validator/compiler consume.
// Audio v1.1 handoff doc: docs/… (see commit history for spec summary).

export type QuantizeGrid = 'none' | 'beat' | 'half' | 'bar'

// ── ChipMusic ─────────────────────────────────────────────────────

export type ChipChannel =
  | 'pulse1' | 'pulse2' | 'triangle' | 'noise' | 'wave'

export interface EnvelopeADSR {
  attack: number   // sec
  decay: number    // sec
  sustain: number  // 0..1
  release: number  // sec
}

export interface NoteEvent {
  time: number        // beats from track start
  note: string        // 'C4' / 'D#5' / 'R' (rest) / drum name for noise
  duration: number    // beats
  velocity?: number   // 0..1, default 1
  envelope?: EnvelopeADSR
  dutyCycle?: 0.125 | 0.25 | 0.5 | 0.75
  vibrato?: { rate: number; depth: number }
}

export interface MechanicRef {
  mechanic_ref: MechanicId
  field: string
}

export type MixerValue = number | (MechanicRef & { ramp_ms?: number })

export interface ChipMusicTrack {
  bpm: number | MechanicRef
  bars?: number
  loop: boolean
  loopStart?: number
  channels: Partial<Record<ChipChannel, NoteEvent[]>>
  mixer?: Partial<Record<ChipChannel, MixerValue>>
  wave_table?: number[]  // 32 samples, 0..15
}

export interface ChipMusicParams {
  base_track: ChipMusicTrack
  overlay_tracks?: ChipMusicTrack[]
  overlay_conditions?: ConditionKey[]  // parallel-indexed with overlay_tracks
  crossfade_ms?: number                // default 500
  beat_tolerance_ms?: number           // default 100 (on_beat window)
  channel: 'music' | 'ambient'
  autoplay_on?: ConditionKey
  stop_on?: ConditionKey
}

// ── SfxLibrary ────────────────────────────────────────────────────

export type SfxrWaveType = 'square' | 'sawtooth' | 'sine' | 'noise'

export interface SfxrParams {
  waveType: SfxrWaveType
  envelopeAttack: number
  envelopeSustain: number
  envelopePunch: number
  envelopeDecay: number
  baseFreq: number
  freqLimit: number
  freqRamp: number
  freqDeltaRamp: number
  vibratoStrength: number
  vibratoSpeed: number
  arpMod: number
  arpSpeed: number
  duty: number
  dutyRamp: number
  repeatSpeed: number
  flangerOffset: number
  flangerRamp: number
  lpFilterCutoff: number
  lpFilterCutoffRamp: number
  lpFilterResonance: number
  hpFilterCutoff: number
  hpFilterCutoffRamp: number
  masterVolume: number
  sampleRate: 44100 | 22050 | 11025
  sampleSize: 8 | 16
}

export interface SfxLibraryParams {
  sfx: Record<string, SfxrParams>
}

// ───────── validator result ─────────

export interface ValidatedDesign extends DesignScript {
  __validated: true
}

export interface ValidationError {
  kind:
    | 'unknown_mechanic_type' | 'unknown_archetype_ref' | 'unknown_mechanic_ref'
    | 'unknown_singleton_ref' | 'unknown_item_ref'
    | 'dangling_condition' | 'tag_requirement' | 'incompatible_combo'
    | 'duplicate_id' | 'component_parse' | 'playfield_mismatch'
    | 'out_of_scope'
    // v1.1 audio extension — 6 additional error kinds wired up in
    // validate.ts (audio-specific pre-compile checks).
    | 'unknown_sfx_preset'
    | 'invalid_chiptune_track'
    | 'library_ref_not_sfx_library'
    | 'unknown_mechanic_field'
    | 'invalid_quantize_source'
    | 'overlay_condition_mismatch'
  path: string
  message: string
  hint?: string
  suggestions?: string[]
}

export type ValidationResult =
  | { ok: true;  design: ValidatedDesign }
  | { ok: false; errors: ValidationError[] }
