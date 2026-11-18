import { onUnmounted, ref } from 'vue'
import {
  createSafetyEventStream,
  type RealtimeConnectionState,
  type SafetyEventStreamCallbacks,
  type SafetyEventStreamHandle,
} from '@/api/realtime'

export function useSafetyStream() {
  const streamState = ref<RealtimeConnectionState>('closed')
  let handle: SafetyEventStreamHandle | undefined

  function stop(): void {
    if (handle) {
      handle.close()
      handle = undefined
    }
  }

  function start(callbacks: SafetyEventStreamCallbacks): void {
    stop()
    handle = createSafetyEventStream({
      onStateChange(state) {
        streamState.value = state
        callbacks.onStateChange?.(state)
      },
      onViolationEvent: callbacks.onViolationEvent,
      onCameraStatus: callbacks.onCameraStatus,
    })
  }

  onUnmounted(stop)

  return {
    streamState,
    start,
    stop,
  }
}
