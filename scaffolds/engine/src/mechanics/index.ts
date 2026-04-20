/**
 * Mechanics barrel — Layer 2 of the gamedev framework.
 *
 * Re-exports the runtime mechanic classes from design/mechanics/*
 * so callers can import from @engine/mechanics without caring about
 * the underlying file layout.
 *
 * Rationale for keeping the implementations under design/mechanics/:
 * they were originally co-located with design-time types for import
 * locality, and renaming 38 files + fixing internal imports is high
 * churn for low payoff. The barrel below is the public API.
 *
 * Every registered MechanicType from schema.ts self-registers in the
 * mechanicRegistry via side-effect imports in design/mechanics/index.ts.
 * Importing @engine/mechanics also re-exports the registry + types.
 */

// Registry + types
export {
  mechanicRegistry,
  type MechanicRuntime,
  type MechanicFactory,
} from '../design/mechanics/_registry'

// Side-effect import triggers all mechanic registrations.
// Without this line, calling mechanicRegistry.create(...) returns null
// because the factories were never attached.
import '../design/mechanics/index'
