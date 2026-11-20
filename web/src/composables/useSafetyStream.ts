import { computed, onUnmounted } from 'vue'
import type { SafetyEventStreamCallbacks } from '@/api/realtime'
import { useRealtimeStore } from '@/stores/realtime'

/**
 * Composable facade over the singleton useRealtimeStore so multiple views
 * and the floating IP agent share a single SSE connection.
 */
export function useSafetyStream() {
  const realtimeStore = useRealtimeStore()
  let unsubscribe: (() => void) | undefined

  function stop(): void {
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = undefined
    }
  }

  function start(callbacks: SafetyEventStreamCallbacks): void {
    stop()
    unsubscribe = realtimeStore.subscribe(callbacks)
  }

  onUnmounted(stop)

  return {
    streamState: computed(() => realtimeStore.streamState),
    start,
    stop,
  }
}
