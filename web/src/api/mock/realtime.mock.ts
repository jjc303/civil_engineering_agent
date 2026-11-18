import type { RealtimePort, SafetyEventStreamCallbacks, SafetyEventStreamHandle } from '../ports'

export const mockRealtimeAdapter: RealtimePort = {
  createSafetyEventStream(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle {
    callbacks.onStateChange?.('disabled')
    return {
      close() {
        callbacks.onStateChange?.('closed')
      },
    }
  },
}
