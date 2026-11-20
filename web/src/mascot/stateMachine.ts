import { MASCOT_DEFAULTS } from './config'

export type MascotState =
  | 'idle'
  | 'hover'
  | 'listening'
  | 'thinking'
  | 'tool_busy'
  | 'speaking'
  | 'confirm_pending'
  | 'alert'
  | 'success'
  | 'error'

export type MascotPropType =
  | 'none'
  | 'manual'
  | 'walkie_talkie'
  | 'clipboard'
  | 'warning_flag'
  | 'wrench'
  | 'check_badge'

export type MascotHelmetBeacon = 'calm' | 'pulse' | 'amber' | 'danger' | 'success'

export interface MascotStateSpec {
  state: MascotState
  priority: number
  autoRevertMs: number | null
  prop: MascotPropType
  beacon: MascotHelmetBeacon
  statusLabelKey: string
}

export const MASCOT_STATE_SPECS: Readonly<Record<MascotState, MascotStateSpec>> = {
  idle: {
    state: 'idle',
    priority: 0,
    autoRevertMs: null,
    prop: 'none',
    beacon: 'calm',
    statusLabelKey: 'mascot.states.idle',
  },
  hover: {
    state: 'hover',
    priority: 10,
    autoRevertMs: null,
    prop: 'none',
    beacon: 'calm',
    statusLabelKey: 'mascot.states.hover',
  },
  listening: {
    state: 'listening',
    priority: 20,
    autoRevertMs: null,
    prop: 'none',
    beacon: 'pulse',
    statusLabelKey: 'mascot.states.listening',
  },
  speaking: {
    state: 'speaking',
    priority: 30,
    autoRevertMs: MASCOT_DEFAULTS.autoRevertMs.speaking,
    prop: 'none',
    beacon: 'pulse',
    statusLabelKey: 'mascot.states.speaking',
  },
  success: {
    state: 'success',
    priority: 40,
    autoRevertMs: MASCOT_DEFAULTS.autoRevertMs.success,
    prop: 'check_badge',
    beacon: 'success',
    statusLabelKey: 'mascot.states.success',
  },
  error: {
    state: 'error',
    priority: 45,
    autoRevertMs: MASCOT_DEFAULTS.autoRevertMs.error,
    prop: 'wrench',
    beacon: 'amber',
    statusLabelKey: 'mascot.states.error',
  },
  thinking: {
    state: 'thinking',
    priority: 60,
    autoRevertMs: null,
    prop: 'manual',
    beacon: 'pulse',
    statusLabelKey: 'mascot.states.thinking',
  },
  tool_busy: {
    state: 'tool_busy',
    priority: 70,
    autoRevertMs: null,
    prop: 'walkie_talkie',
    beacon: 'pulse',
    statusLabelKey: 'mascot.states.toolBusy',
  },
  confirm_pending: {
    state: 'confirm_pending',
    priority: 75,
    autoRevertMs: null,
    prop: 'clipboard',
    beacon: 'amber',
    statusLabelKey: 'mascot.states.confirmPending',
  },
  alert: {
    state: 'alert',
    priority: 90,
    autoRevertMs: MASCOT_DEFAULTS.autoRevertMs.alert,
    prop: 'warning_flag',
    beacon: 'danger',
    statusLabelKey: 'mascot.states.alert',
  },
}

export function getMascotStateSpec(state: MascotState): MascotStateSpec {
  return MASCOT_STATE_SPECS[state]
}

export function isMascotBusyState(state: MascotState): boolean {
  return state === 'thinking' || state === 'tool_busy' || state === 'confirm_pending'
}

export interface TransitionDecision {
  accepted: boolean
  nextState: MascotState
  spec: MascotStateSpec
}

/**
 * Resolve FSM transition using priority arbitration unless `force` is set
 * (used when explicit async work finishes or resets to baseline).
 */
export function resolveMascotTransition(
  current: MascotState,
  target: MascotState,
  force = false,
): TransitionDecision {
  if (force || target === current) {
    return {
      accepted: true,
      nextState: target,
      spec: MASCOT_STATE_SPECS[target],
    }
  }
  const currentPriority = MASCOT_STATE_SPECS[current].priority
  const targetPriority = MASCOT_STATE_SPECS[target].priority
  if (targetPriority >= currentPriority) {
    return {
      accepted: true,
      nextState: target,
      spec: MASCOT_STATE_SPECS[target],
    }
  }
  return {
    accepted: false,
    nextState: current,
    spec: MASCOT_STATE_SPECS[current],
  }
}
