import {
  createStreamFromBundle,
  resolveSafetyEventsStreamUrl,
  type RealtimeConnectionState,
  type RealtimeViolationEventPayload,
  type SafetyEventStreamCallbacks,
  type SafetyEventStreamHandle,
} from './index'

export type {
  RealtimeConnectionState,
  RealtimeViolationEventPayload,
  SafetyEventStreamCallbacks,
  SafetyEventStreamHandle,
}

export { resolveSafetyEventsStreamUrl }

export function createSafetyEventStream(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle {
  return createStreamFromBundle(callbacks)
}
