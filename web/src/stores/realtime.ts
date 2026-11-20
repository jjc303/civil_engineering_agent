import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createSafetyEventStream,
  type RealtimeConnectionState,
  type RealtimeViolationEventPayload,
  type SafetyEventStreamCallbacks,
  type SafetyEventStreamHandle,
} from '@/api/realtime'
import { subscribeLocaleChange } from '@/i18n/localeDetect'
import type { CameraStatusResponse } from '@/types/contract'

export interface RealtimeSubscriber {
  onStateChange?: (state: RealtimeConnectionState) => void
  onViolationEvent?: (payload: RealtimeViolationEventPayload) => void
  onCameraStatus?: (status: CameraStatusResponse) => void
}

export const useRealtimeStore = defineStore('realtime', () => {
  const streamState = ref<RealtimeConnectionState>('closed')
  const subscribers = new Set<RealtimeSubscriber>()
  let handle: SafetyEventStreamHandle | undefined
  let retainCount = 0

  subscribeLocaleChange(() => {
    restart()
  })

  function ensureStarted(): void {
    if (handle) return
    handle = createSafetyEventStream({
      onStateChange(next) {
        streamState.value = next
        for (const sub of subscribers) {
          sub.onStateChange?.(next)
        }
      },
      onViolationEvent(payload) {
        for (const sub of subscribers) {
          sub.onViolationEvent?.(payload)
        }
      },
      onCameraStatus(status) {
        for (const sub of subscribers) {
          sub.onCameraStatus?.(status)
        }
      },
    })
  }

  function stopStream(): void {
    if (handle) {
      handle.close()
      handle = undefined
    }
    streamState.value = 'closed'
  }

  function retain(): void {
    retainCount += 1
    ensureStarted()
  }

  function release(): void {
    retainCount = Math.max(0, retainCount - 1)
    if (retainCount === 0 && subscribers.size === 0) {
      stopStream()
    }
  }

  function restart(): void {
    if (!handle && retainCount === 0 && subscribers.size === 0) return
    stopStream()
    ensureStarted()
  }

  function subscribe(callbacks: SafetyEventStreamCallbacks): () => void {
    subscribers.add(callbacks)
    retain()
    if (streamState.value !== 'closed') {
      callbacks.onStateChange?.(streamState.value)
    }
    return () => {
      subscribers.delete(callbacks)
      release()
    }
  }

  return {
    streamState,
    retain,
    release,
    restart,
    subscribe,
  }
})
