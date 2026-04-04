/**
 * Animation module — public API barrel export.
 */

export { Skeleton } from './skeleton'
export type { BonePose } from './skeleton'
export { AnimationClip } from './clip'
export type { AnimationChannel } from './clip'
export { AnimationStateMachine } from './state_machine'
export type { AnimState, AnimTransition, AnimationEvent } from './state_machine'
export { solveTwoBoneIK, solveFABRIK } from './ik'
export { RootMotionExtractor } from './root_motion'
export {
  getSkinningPipeline,
  createSkinningBuffers,
  dispatchSkinning,
} from './skinning'
export type { SkinningPipeline, SkinningBuffers } from './skinning'
