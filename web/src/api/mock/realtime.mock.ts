import type {
  RealtimePort,
  RealtimeViolationEventPayload,
  SafetyEventStreamCallbacks,
  SafetyEventStreamHandle,
} from '../ports'

const mockListeners = new Set<SafetyEventStreamCallbacks>()

export function emitMockViolationEvent(payload: RealtimeViolationEventPayload): void {
  for (const listener of mockListeners) {
    listener.onViolationEvent?.(payload)
  }
}

export const mockRealtimeAdapter: RealtimePort = {
  createSafetyEventStream(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle {
    mockListeners.add(callbacks)
    callbacks.onStateChange?.('disabled')
    return {
      close() {
        mockListeners.delete(callbacks)
        callbacks.onStateChange?.('closed')
      },
    }
  },
}
