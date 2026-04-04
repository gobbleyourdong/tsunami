/**
 * Input module — public API barrel export.
 */

export { KeyboardInput } from './keyboard'
export { GamepadInput, GAMEPAD_BUTTONS } from './gamepad'
export type { GamepadState } from './gamepad'
export { TouchInput } from './touch'
export type { VirtualJoystick, TouchButton } from './touch'
export { PointerLockInput } from './pointer_lock'
export { ActionMap, createFPSActionMap, createPlatformerActionMap } from './action_map'
export type { InputSource, ActionBinding } from './action_map'
export { ComboSystem } from './combo'
export type { ComboInput, ComboPattern } from './combo'
