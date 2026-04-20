// Mechanics registry + side-effect registrations.
//
// The registry itself lives in ./_registry to keep its initialization
// order independent of the side-effect imports below — otherwise the
// circular `mechanic → index → registry` chain leaves `mechanicRegistry`
// undefined when each mechanic's bottom-of-file .register(...) runs.
//
// Each mechanic module (sibling files in this directory) exports a
// factory via `mechanicRegistry.register(...)` at module scope. Simply
// importing the mechanic file here triggers that registration as a
// side-effect.

export {
  mechanicRegistry,
  type MechanicRuntime,
  type MechanicFactory,
} from './_registry'

// Phase 1 registrations.
import './rhythm_track'
import './dialog_tree'
import './procedural_room_chain'
import './bullet_pattern'
import './puzzle_object'
// Phase 2.
import './embedded_minigame'
// world_flags is a helper module, not a mechanic — import its exports
// from mechanics/world_flags.ts directly when needed.
// Phase 3 — action-core (13 mechanics).
import './difficulty'
import './wave_spawner'
import './hud'
import './lose_on_zero'
import './win_on_count'
import './pickup_loop'
import './score_combos'
import './checkpoint_progression'
import './lock_and_key'
import './camera_follow'
import './timed_state_modifier'
import './level_sequence'
import './room_graph'
// Phase 4 — extensions (14 mechanics).
import './state_machine_mechanic'
import './combo_attacks'
import './boss_phases'
import './item_use'
import './gated_trigger'
import './attack_frames'
import './shop'
import './utility_ai'
import './hotspot_mechanic'
import './inventory_combine'
import './status_stack'
import './ending_branches'
import './vision_cone'
import './route_map'
// Phase 5 — audio v1.1 (2 mechanics).
import './chip_music'
import './sfx_library'
// Phase 6 — JRPG v1.2 cluster. Implementations land incrementally per cycle.
import './level_up_progression'
import './turn_based_combat'
