// Action Blocks + Mechanics — v1.0 catalog metadata
//
// One entry per MechanicType. Powers:
//   (a) LLM prompt — `description` + `example_params` feed the model
//   (b) validator  — `requires_*`, `emits_*`, compatibility rules
//   (c) topo sort  — `needs_mechanic_types`
//   (d) QA mutation — `common_patches` are cheap-high-impact edits
//
// 29 mechanics + 3 supporting concepts (Resource component, WorldFlags
// singleton kind, PointerController controller name).

import type { MechanicType, MechanicParams } from './schema'

export interface CatalogEntry {
  type: MechanicType
  description: string
  example_params: MechanicParams | Record<string, unknown>

  // Validation constraints
  requires_mode?: '2d' | '3d'
  requires_playfield?: 'continuous' | 'grid' | 'any'
  requires_tags?: string[]
  requires_components?: string[]
  requires_controller?: string[]
  requires_config?: { sandbox_compat?: boolean }

  // Dependencies
  needs_mechanic_types?: MechanicType[]

  // What it publishes
  emits_fields?: string[]
  emits_conditions?: boolean

  // Domain-map tier
  tier?: 'v1_core' | 'v1_ext' | 'v2'

  // Lowering order — see attempt_008 mechanic arbitration
  priority_class?: 'pre_update' | 'sensors' | 'state_modifiers'
                 | 'default' | 'effects' | 'hud'

  // Composability — how much this multiplies with others (attempt_009, note_007).
  // High-composability mechanics render first in the LLM-facing catalog.
  composability_score?: 'high' | 'medium' | 'low'

  // Mutation hints for QA
  common_patches?: string[]
}

export const CATALOG: Record<MechanicType, CatalogEntry> = {

  Difficulty: {
    type: 'Difficulty',
    description: 'S-curve ramp over a drive signal (time/score/wave/level). Publishes named multipliers consumed by other mechanics.',
    example_params: {
      drive: 'wave_index',
      easy: { spawnRateMul: 0.6, enemyHealthMul: 0.8 },
      hard: { spawnRateMul: 2.0, enemyHealthMul: 1.5 },
      max_level: 10,
    },
    emits_fields: ['level', 'spawnRateMul', 'enemyHealthMul'],
    tier: 'v1_core',
    common_patches: ['tune max_level', 'soften easy', 'cap hard'],
  },

  HUD: {
    type: 'HUD',
    description: 'Renders named archetype components, mechanic fields, or singleton fields to screen overlay.',
    example_params: {
      fields: [
        { archetype: 'player', component: 'Health' },
        { archetype: 'player', component: 'Score' },
      ],
      layout: 'corners',
    },
    tier: 'v1_core',
    common_patches: ['add field', 'remove clutter', 'change layout'],
  },

  LoseOnZero: {
    type: 'LoseOnZero',
    description: 'Emits a flow condition when an archetype field reaches zero. Party-wipe via any_of.',
    example_params: { archetype: 'player', field: 'Health', emit_condition: 'player_dead' },
    emits_conditions: true,
    tier: 'v1_core',
  },

  WinOnCount: {
    type: 'WinOnCount',
    description: 'Emits flow condition when archetype instance count hits comparator.',
    example_params: { archetype: 'goal', count: 1, comparison: 'gte', emit_condition: 'goal_reached' },
    emits_conditions: true,
    tier: 'v1_core',
  },

  WaveSpawner: {
    type: 'WaveSpawner',
    description: 'Spawns enemy archetype waves on a rest timer. Scales by Difficulty reference.',
    example_params: {
      archetype: 'grunt', difficulty_ref: 'diff', base_count: 4,
      rest_sec: 6, arena_radius: 20, intro_delay_sec: 2,
    },
    requires_tags: ['enemy'],
    emits_fields: ['wave_index', 'alive_count'],
    tier: 'v1_core',
    common_patches: ['lower base_count', 'raise rest_sec', 'add intro_delay_sec'],
  },

  PickupLoop: {
    type: 'PickupLoop',
    description: 'Trigger-driven reward on pickup archetype; respawn after sec or never (survival scarcity).',
    example_params: {
      archetype: 'coin', reward_field: 'Score', reward_amount: 10,
      respawn: { sec: 4 },
    },
    requires_tags: ['pickup'],
    tier: 'v1_core',
    common_patches: ['adjust reward_amount', 'shorten respawn', 'set respawn:never'],
  },

  ScoreCombos: {
    type: 'ScoreCombos',
    description: 'Multiplier on Score increments. Window-based or event-banked (THPS).',
    example_params: {
      archetype: 'player', window_sec: 2.5, curve: 'quadratic', max_multiplier: 8,
    },
    requires_components: ['Score'],
    tier: 'v1_core',
  },

  CheckpointProgression: {
    type: 'CheckpointProgression',
    description: 'Checkpoint archetype saves named fields on contact; death restores from latest.',
    example_params: {
      archetype: 'checkpoint', mode: 'respawn_in_place',
      restore_fields: ['Health', 'position'],
    },
    requires_tags: ['checkpoint'],
    tier: 'v1_core',
  },

  LockAndKey: {
    type: 'LockAndKey',
    description: 'Key-tagged archetype opens lock-tagged archetype on contact. Consumable or persistent.',
    example_params: { key_tag: 'key_red', lock_tag: 'lock_red', consume_key: true },
    tier: 'v1_core',
  },

  StateMachineMechanic: {
    type: 'StateMachineMechanic',
    description: 'Declarative FSM on an archetype. States run enter/exit actions; transitions fire on condition DSL.',
    example_params: {
      archetype: 'enemy',
      states: [{ name: 'patrol' }, { name: 'chase' }, { name: 'attack' }],
      transitions: [
        { from: 'patrol', to: 'chase',  when: 'player_in_radius(8)' },
        { from: 'chase',  to: 'attack', when: 'player_in_radius(2)' },
      ],
      initial: 'patrol',
    },
    tier: 'v1_core',
  },

  ComboAttacks: {
    type: 'ComboAttacks',
    description: 'Input-sequence recognizer. Named patterns fire ActionRefs within window_ms. Gatable by state.',
    example_params: {
      archetype: 'player',
      patterns: [
        {
          name: 'fireball',
          sequence: ['down', 'down_forward', 'forward', 'punch'],
          window_ms: 500,
          action: { kind: 'spawn', archetype: 'fireball_projectile' },
        },
      ],
    },
    tier: 'v1_core',
  },

  BossPhases: {
    type: 'BossPhases',
    description: 'Health-threshold FSM with on_phase_enter ActionRefs. AI and tint swap per phase.',
    example_params: {
      archetype: 'boss',
      phases: [
        { health_pct: 1.0, ai: 'patrol',    tint: [1, 1, 1] },
        { health_pct: 0.5, ai: 'chase',     tint: [1, 0.5, 0.5] },
        { health_pct: 0.2, ai: 'bt:enrage', tint: [1, 0, 0],
          on_phase_enter: [{ kind: 'spawn', archetype: 'minion' }] },
      ],
    },
    requires_tags: ['boss'],
    requires_components: ['Health'],
    tier: 'v1_core',
  },

  // TileRewriteMechanic moved to future grid-puzzle scaffold (v1.0.4 rescope).
  // Rule-DSL spec (PuzzleScript-style with our extensions) preserved in
  // attempts/attempt_012.md for the grid-puzzle scaffold's use.

  RhythmTrack: {
    type: 'RhythmTrack',
    description: 'Beat timeline synced to audio. Spawns beat-archetype per beat with hit window.',
    example_params: {
      bpm: 128, audio_ref: 'track_01',
      beat_spawn_archetype: 'beat_marker',
      measure: { beats: 4, note_value: 4 },
      hit_window_ms: 120,
    },
    tier: 'v1_ext',
  },

  // GridPlayfield + GridController moved to future grid-puzzle scaffold (v1.0.4).

  LevelSequence: {
    type: 'LevelSequence',
    description: 'Ordered progression through authored levels. Handles win/fail transitions per level.',
    example_params: {
      levels: [
        { id: '1-1', layout_source: 'world1/1-1.tmx', on_win: 'next' },
        { id: '1-2', layout_source: 'world1/1-2.tmx', on_win: 'next' },
        { id: '1-3', layout_source: 'world1/1-3.tmx', on_win: 'next',
          fail_condition: 'time_up', on_fail: 'retry' },
      ],
      start_at: '1-1',
    },
    emits_fields: ['current_level', 'levels_completed'],
    tier: 'v1_core',
  },

  RoomGraph: {
    type: 'RoomGraph',
    description: 'Directed graph of rooms with gated edges. Zelda/Metroid-shape. Doors can require items or conditions.',
    example_params: {
      rooms: [
        { id: 'overworld' },
        { id: 'dungeon_1' },
      ],
      edges: [
        { from: 'overworld', to: 'dungeon_1',
          requires_item: 'red_key', transition: 'fade' },
      ],
      start_room: 'overworld',
    },
    tier: 'v1_core',
  },

  // FallingPieceMechanic + LineClearMechanic moved to future grid-puzzle scaffold (v1.0.4).

  ItemUse: {
    type: 'ItemUse',
    description: 'Inventory → ActionRef mapping with active slot + target requirements.',
    example_params: {
      archetype: 'player',
      items: [
        { name: 'hookshot', action: { kind: 'spawn', archetype: 'hook_projectile' },
          requires_target_tag: 'hookable', consume_on_use: false },
        { name: 'bomb', action: { kind: 'spawn', archetype: 'bomb' },
          consume_on_use: true },
      ],
      active_slot: 'a_button',
    },
    requires_components: ['Inventory'],
    tier: 'v1_core',
  },

  GatedTrigger: {
    type: 'GatedTrigger',
    description: 'Gate archetype (door, path) opens on a named condition. Pairs with ItemUse for item-gated progression.',
    example_params: {
      gate_archetype: 'locked_door',
      opens_when: { has_item: 'boss_key' },
      open_effect: { kind: 'play_sound', asset: 'door_unlock' },
    },
    tier: 'v1_core',
  },

  TimedStateModifier: {
    type: 'TimedStateModifier',
    description: 'Archetype gains a named state for a duration. Power-up, invuln, stun.',
    example_params: {
      archetype: 'player', state: 'powered_up', duration_sec: 10,
      on_apply:  { kind: 'play_sound', asset: 'power_up' },
      on_expire: { kind: 'play_sound', asset: 'power_down' },
    },
    tier: 'v1_core',
  },

  AttackFrames: {
    type: 'AttackFrames',
    description: 'Per-state hitbox/hurtbox window with startup/active/recovery frames. Fighter core.',
    example_params: {
      archetype: 'fighter',
      states: [
        { name: 'jab',   startup_ms: 60,  active_ms: 80,  recovery_ms: 200,
          hitbox: { offset: [1, 0], size: [1, 1] } },
        { name: 'heavy', startup_ms: 240, active_ms: 120, recovery_ms: 500,
          hitbox: { offset: [1.5, 0], size: [1.2, 1] } },
      ],
    },
    tier: 'v1_core',
  },

  // TurnManager moved to future turn-based scaffold (v1.0.4 rescope).

  Shop: {
    type: 'Shop',
    description: 'Vendor archetype with currency-gated purchases. Lowers to a DialogTree subtree.',
    example_params: {
      vendor_archetype: 'shopkeeper',
      currency_field: 'Resource(money)',
      stock: [
        { item: 'potion', price: 50, stock_count: 10 },
        { item: 'key',    price: 200, unlock_condition: 'after_dungeon_1' },
      ],
      ui_layout: 'dialog_embedded',
    },
    needs_mechanic_types: ['DialogTree'],
    tier: 'v1_core',
  },

  UtilityAI: {
    type: 'UtilityAI',
    description: 'Action selection by utility score over named needs. Sims autonomy; animal AI; RPG companion idle.',
    example_params: {
      archetype: 'sim',
      needs: [
        { name: 'hunger',  decay_per_sec: 0.01, max: 100, initial: 50 },
        { name: 'comfort', decay_per_sec: 0.005, max: 100, initial: 80 },
      ],
      actions: [
        { name: 'eat',  need_deltas: { hunger: -60 },
          effect: { kind: 'play_sound', asset: 'eat' } },
        { name: 'sit',  need_deltas: { comfort: 30, hunger: -2 },
          effect: { kind: 'play_sound', asset: 'sit' } },
      ],
      selection: 'highest_need',
    },
    tier: 'v1_core',
  },

  DialogTree: {
    type: 'DialogTree',
    description: 'Branching conversation. Choices gated by conditions or world_flags. Triggers on contact or hotspot.',
    example_params: {
      trigger_archetype: 'npc_sage',
      tree: {
        id: 'root',
        line: 'What brings you here?',
        speaker: 'Sage',
        choices: [
          { text: 'The prophecy.',     goto: 'prophecy' },
          { text: 'Training, please.', goto: 'training',
            requires: { world_flag: 'has_met_sage' } },
        ],
      },
    },
    tier: 'v1_core',
  },

  HotspotMechanic: {
    type: 'HotspotMechanic',
    description: 'Named clickable regions in a scene with examine/use/pickup actions. Monkey Island-shape.',
    example_params: {
      scene: 'tavern',
      hotspots: [
        { name: 'mug',  region: { x: 120, y: 200, w: 40, h: 40 },
          on_examine: { kind: 'dialog', tree_ref: 'mug_desc' } },
        { name: 'door', region: { x: 400, y: 100, w: 80, h: 200 },
          on_use: { kind: 'scene_goto', scene: 'street' } },
      ],
    },
    requires_controller: ['pointer'],
    tier: 'v1_core',
  },

  InventoryCombine: {
    type: 'InventoryCombine',
    description: 'Recipe table combining inventory items. Two or more ingredients → new item.',
    example_params: {
      archetype: 'player',
      recipes: [
        { ingredients: ['rope', 'hook'], result: 'grappling_hook', consumes: 'all' },
        { ingredients: ['bread', 'cheese'], result: 'sandwich', consumes: 'all' },
      ],
    },
    requires_components: ['Inventory'],
    tier: 'v1_core',
  },

  CameraFollow: {
    type: 'CameraFollow',
    description: 'Camera tracks an archetype with deadzone + easing + optional scene bounds. Ubiquitous.',
    example_params: {
      target_archetype: 'player',
      mode: 'sidescroll',
      offset: [0, 2, 0],
      deadzone: { width: 3, height: 2 },
      ease: 0.2,
    },
    tier: 'v1_core',
  },

  StatusStack: {
    type: 'StatusStack',
    description: 'Multi-slot status container: poison/sleep/burn/haste with duration, tags, conflict rules.',
    example_params: {
      archetype: 'unit',
      statuses: [
        { name: 'poison', tags: ['damage_over_time'], duration_sec: 15,
          tick_effect: { kind: 'damage', archetype: 'unit', amount: 2 } },
        { name: 'sleep',  tags: ['mental', 'movement_block'], duration_sec: 5,
          on_apply: { kind: 'play_sound', asset: 'zzz' } },
      ],
      conflict_rules: [
        { if_present: 'sleep', and_applying: 'haste', resolve: 'remove_present' },
      ],
    },
    tier: 'v1_ext',
    priority_class: 'state_modifiers',
  },

  EmbeddedMinigame: {
    type: 'EmbeddedMinigame',
    description: 'Horizontal-composition wrapper. Outer mechanics suspend, inner mechanic-set runs, control returns. FF6 Opera House, Zelda fishing, Phoenix Wright cross-examination.',
    example_params: {
      trigger: 'opera_started',
      mechanics: [
        { id: 'rhythm_sub', type: 'RhythmTrack',
          params: { bpm: 80, audio_ref: 'opera_aria',
                    beat_spawn_archetype: 'beat', measure: { beats: 4, note_value: 4 },
                    hit_window_ms: 200 } },
      ],
      suspend_mechanics: ['overworld_ai', 'overworld_spawner'],
      exit_condition: 'opera_finished',
      on_exit: { kind: 'give_item', archetype: 'player', item: 'opera_ticket' },
    },
    tier: 'v1_core',
    priority_class: 'pre_update',
    common_patches: ['extend duration', 'soften exit_condition', 'change on_exit reward'],
  },

  EndingBranches: {
    type: 'EndingBranches',
    description: 'Narrative flow with multiple terminal states. Chrono-like multi-ending selection based on world flags / flags / completion timing.',
    example_params: {
      endings: [
        { id: 'true', scene: 'ending_true',   priority: 100,
          requires: [{ world_flag: 'all_party_recruited' },
                     { world_flag: 'boss_true_defeated' }] },
        { id: 'good', scene: 'ending_good',   priority: 50,
          requires: [{ world_flag: 'boss_defeated' }] },
        { id: 'bad',  scene: 'ending_bad',    priority: 10,
          requires: [{ elapsed_sec: { max: 3600 } }] },   // speedrun
      ],
      default_ending: 'bad',
    },
    tier: 'v1_core',
    priority_class: 'default',
  },

  VisionCone: {
    type: 'VisionCone',
    description: 'Stealth primitive. Cone-of-vision sensor on archetype; target in cone + LoS triggers alert-state FSM (calm/suspicious/alert).',
    example_params: {
      archetype: 'guard',
      target_tags: ['player'],
      cone_angle_deg: 60,
      cone_range: 12,
      line_of_sight: true,
      alert_states: [
        { name: 'calm',       ai_override: 'patrol' },
        { name: 'suspicious', ai_override: 'chase', decay_to: 'calm', decay_sec: 3,
          on_enter: { kind: 'spawn', archetype: 'question_mark', at: 'caller' } },
        { name: 'alert',      ai_override: 'chase',
          on_enter: { kind: 'spawn', archetype: 'exclamation_mark', at: 'caller' } },
      ],
      initial_state: 'calm',
    },
    tier: 'v1_core',
    priority_class: 'sensors',
    composability_score: 'medium',
  },

  PuzzleObject: {
    type: 'PuzzleObject',
    description: 'Mutable world object with state transitions. Myst rotating wheel, Monkey Island jury-rigged items, RE lock-combos. Cycles through named states on interaction / item-use / adjacent-state / world-flag.',
    example_params: {
      archetype: 'wheel',
      states: [
        { name: '0',   tint: [1, 1, 1] },
        { name: '90',  tint: [1, 0.9, 0.9] },
        { name: '180', tint: [0.9, 1, 0.9] },
        { name: '270', tint: [0.9, 0.9, 1] },
      ],
      transitions: [
        { from: '0',   to: '90',  triggered_by: { interaction: 'use' } },
        { from: '90',  to: '180', triggered_by: { interaction: 'use' } },
        { from: '180', to: '270', triggered_by: { interaction: 'use' } },
        { from: '270', to: '0',   triggered_by: { interaction: 'use' },
          effect: { kind: 'set_flag', world_flag: 'wheel_cycled', value: true } },
      ],
      initial_state: '0',
    },
    tier: 'v1_core',
    priority_class: 'default',
    composability_score: 'high',
    common_patches: ['add state', 'change trigger kind', 'chain effect'],
  },

  ProceduralRoomChain: {
    type: 'ProceduralRoomChain',
    description: 'Run-based room sequencing for roguelites. Sample rooms from a weighted pool, apply connection rules, handle run lifecycle. Content-multiplier: 1 mechanic × N room pools = N distinct roguelites.',
    example_params: {
      room_pool: [
        { id: 'combat_small', weight: 4 },
        { id: 'combat_large', weight: 2, min_depth: 3 },
        { id: 'treasure',     weight: 1 },
        { id: 'elite',        weight: 1, min_depth: 4 },
      ],
      connection_rules: {
        min_rooms_per_run: 8, max_rooms_per_run: 12,
        branch_factor: 2, elite_room_after: 4,
      },
      run_lifecycle: {
        on_run_start:    { kind: 'play_sound', asset: 'run_start' },
        on_run_complete: { kind: 'award_score', amount: 1000 },
      },
    },
    tier: 'v1_core',
    priority_class: 'pre_update',
    composability_score: 'high',
    common_patches: ['tune weights', 'adjust min/max rooms', 'add room to pool'],
  },

  BulletPattern: {
    type: 'BulletPattern',
    description: 'Parametric bullet emission. Named patterns (line/ring/spiral/spread/aimed) with params. Touhou-class shmup core. Content-multiplier: 1 mechanic × hundreds of patterns per boss.',
    example_params: {
      emitter_archetype: 'boss',
      patterns: [
        { name: 'basic_spread', bullet_archetype: 'bullet_blue',
          layout: 'spread',
          layout_params: { count: 8, spread_deg: 60, speed: 4 },
          duration_ms: 1500 },
        { name: 'ring_burst', bullet_archetype: 'bullet_red',
          layout: 'ring',
          layout_params: { count: 24, speed: 6 },
          trigger_condition: 'boss.health_pct < 0.5' },
      ],
      sequence: 'scripted',
      scripted_order: ['basic_spread', 'basic_spread', 'ring_burst'],
    },
    tier: 'v1_core',
    priority_class: 'effects',
    composability_score: 'high',
    common_patches: ['add pattern', 'tune layout_params', 'reorder sequence'],
  },

  RouteMap: {
    type: 'RouteMap',
    description: 'Meta-progression map. Node graph with encounter types (battle/elite/shop/rest/boss). StS-shape. Content-multiplier: 1 mechanic × N map topologies = N distinct run structures.',
    example_params: {
      nodes: [
        { id: 's0', kind: 'battle', depth: 0, scene: 'battle_basic' },
        { id: 'e1', kind: 'elite',  depth: 2, scene: 'battle_elite',
          reward: { kind: 'give_item', archetype: 'player', item: 'relic' } },
        { id: 'sh', kind: 'shop',   depth: 4, scene: 'shop_scene' },
        { id: 'b',  kind: 'boss',   depth: 6, scene: 'battle_boss' },
      ],
      edges: [{ from: 's0', to: 'e1' }, { from: 'e1', to: 'sh' },
              { from: 'sh', to: 'b' }],
      start_nodes: ['s0'],
      boss_node: 'b',
      layout: 'layered_dag',
    },
    tier: 'v1_core',
    priority_class: 'pre_update',
    composability_score: 'high',
    common_patches: ['add node', 'rewire edges', 'swap scene_ref'],
  },

  // v1.1 audio extension
  ChipMusic: {
    type: 'ChipMusic',
    description:
      '4+1 channel chiptune (pulse1/pulse2/triangle/noise/wave). Optional ' +
      'N-layer overlay tracks with crossfade on condition. BPM and mixer ' +
      'can be numbers OR {mechanic_ref, field} to drive tempo/volume from ' +
      'Difficulty or any other mechanic. Publishes beat events for ' +
      'rhythm-gated triggers.',
    example_params: {
      base_track: {
        bpm: 128,
        bars: 4,
        loop: true,
        channels: {
          pulse1: [{ time: 0, note: 'C5', duration: 0.5 },
                   { time: 0.5, note: 'E5', duration: 0.5 },
                   { time: 1, note: 'G5', duration: 0.5 }],
          noise:  [{ time: 0, note: 'kick',  duration: 0.25 },
                   { time: 1, note: 'snare', duration: 0.25 }],
        },
        mixer: { pulse1: 1, noise: 0.8 },
      },
      channel: 'music',
      autoplay_on: 'stage_loaded',
    },
    emits_fields: [
      'is_playing', 'current_beat', 'active_layer',
      'on_beat', 'off_beat',
      'channel_gain.pulse1', 'channel_gain.pulse2',
      'channel_gain.triangle', 'channel_gain.noise', 'channel_gain.wave',
    ],
    tier: 'v1_core',
    priority_class: 'effects',
    composability_score: 'high',
    common_patches: ['swap base_track', 'toggle overlay',
                     'adjust crossfade_ms', 'reference difficulty for BPM'],
  },

  SfxLibrary: {
    type: 'SfxLibrary',
    description:
      'Named catalog of sfxr parameter sets referenced by ActionRef ' +
      'play_sfx_ref / play_sfx_loop_ref. Presets are pre-rendered to ' +
      'AudioBuffers at load time; trigger cost is a single AudioBuffer ' +
      'start call.',
    example_params: {
      sfx: {
        pickup: {
          waveType: 'square',
          envelopeAttack: 0, envelopeSustain: 0.05, envelopePunch: 0.4,
          envelopeDecay: 0.2,
          baseFreq: 0.7, freqLimit: 0, freqRamp: 0, freqDeltaRamp: 0,
          vibratoStrength: 0, vibratoSpeed: 0,
          arpMod: 0.3, arpSpeed: 0.6,
          duty: 0.5, dutyRamp: 0, repeatSpeed: 0,
          flangerOffset: 0, flangerRamp: 0,
          lpFilterCutoff: 1, lpFilterCutoffRamp: 0, lpFilterResonance: 0,
          hpFilterCutoff: 0, hpFilterCutoffRamp: 0,
          masterVolume: 0.25, sampleRate: 44100, sampleSize: 16,
        },
      },
    },
    tier: 'v1_core',
    priority_class: 'effects',
    composability_score: 'high',
    common_patches: ['add preset', 'tune punch', 'shift base_freq'],
  },

  // v2 placeholders — shape not specified; compiler emits out_of_scope error.
  RoleAssignment: {
    type: 'RoleAssignment',
    description: 'v2 placeholder — runtime BT swap on archetype instance (Lemmings). Not implemented.',
    example_params: {},
    tier: 'v2',
  },
  CrowdSimulation: {
    type: 'CrowdSimulation',
    description: 'v2 placeholder — many-allied-archetype ambient behavior (Pikmin, Overlord). Not implemented.',
    example_params: {},
    tier: 'v2',
  },
  TimeReverseMechanic: {
    type: 'TimeReverseMechanic',
    description: 'v2 placeholder — record/playback of entity state (Braid, Prince of Persia Sands). Not implemented.',
    example_params: {},
    tier: 'v2',
  },
  PhysicsModifier: {
    type: 'PhysicsModifier',
    description: 'v2 placeholder — toggle gravity/time/friction globally (VVVVVV, Superhot). Not implemented.',
    example_params: {},
    tier: 'v2',
  },

  // v2 anthology pattern — per numerics note_011
  MinigamePool: {
    type: 'MinigamePool',
    description: 'v2 placeholder — anthology pattern: collection of disjoint mini-games IS the game (WarioWare, Mario Party minigames, Rhythm Tengoku, Mario 64 DS). Each pool entry is a full nested design subtree. Distinct from EmbeddedMinigame (outer loop exists).',
    example_params: {},
    tier: 'v2',
  },
}

// ───────── domain-map / out-of-scope ─────────
//
// Prompts matching these patterns should be declined by the scaffold.

export const OUT_OF_SCOPE_V1: Array<{ pattern: string; redirect: string }> = [
  { pattern: 'text adventure, interactive fiction, Zork-like, parser-driven',
    redirect: 'Inform 7 or Twine — this method targets real-time spatial games.' },
  { pattern: 'real-time strategy, RTS, multi-unit command, StarCraft-like',
    redirect: 'a dedicated RTS engine — v1 is single-protagonist.' },
  { pattern: 'turn-based strategy, Fire Emblem, Advance Wars, Civ-like',
    redirect: 'Belongs in a dedicated turn-based-tactics scaffold (not yet built). Action-blocks targets real-time spatial games.' },
  { pattern: 'grid puzzle, Sokoban, Tetris, block falling, tile rewrite, PuzzleScript',
    redirect: 'Belongs in a dedicated grid-puzzle scaffold (not yet built). Action-blocks is continuous-physics real-time.' },
  { pattern: 'card game, deckbuilder, TCG, Magic-like, Slay the Spire combat',
    redirect: 'Belongs in a dedicated card-game scaffold (not yet built). RouteMap for the map layer IS in action-blocks.' },
  { pattern: 'JRPG battle system, Chrono Trigger-like, ATB combat',
    redirect: 'v2 — requires BattleSystem sub-schema.' },
  { pattern: 'racing simulator, lap-based, track geometry',
    redirect: 'v2 — requires VehicleController + TrackSpline.' },
  { pattern: 'persistent simulation, SimCity, Civ, multi-day sim',
    redirect: 'v2 — requires persistent timeline + save system.' },
  { pattern: 'MMO, online multiplayer, networked, server-authoritative, matchmaking',
    redirect: 'Networked multiplayer requires server infrastructure beyond the WebGPU client. ' +
              'Local multiplayer (split-screen, couch co-op, party games) IS supported — the ' +
              'engine handles input routing. Try "local multiplayer <genre>" instead.' },
  { pattern: 'team sports sim, Madden, FIFA, NBA sim',
    redirect: 'v2+ — requires team-AI, play-call system, physics sim beyond single-protagonist.' },
]

// ───────── lookup helpers ─────────

export function describeCatalog(): string {
  // LLM-facing single-line descriptions; stable order.
  return Object.values(CATALOG)
    .map(e => `- **${e.type}** — ${e.description}`)
    .join('\n')
}

export function exampleParams(type: MechanicType): Record<string, unknown> {
  return CATALOG[type].example_params as Record<string, unknown>
}

export function isOutOfScopeV1(prompt: string): { out: boolean; redirect?: string } {
  const p = prompt.toLowerCase()
  for (const entry of OUT_OF_SCOPE_V1) {
    const any_match = entry.pattern.split(',').map(s => s.trim().toLowerCase())
      .some(kw => p.includes(kw))
    if (any_match) return { out: true, redirect: entry.redirect }
  }
  return { out: false }
}
