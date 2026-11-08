import { apiBaseUrl } from '@/utils/deployment'
import { isMockEnabled } from './client'
import type { CameraStatusResponse, ViolationRecord } from '@/types/contract'

export type RealtimeConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'disabled'

export interface RealtimeViolationEventPayload {
  operation: 'CREATED' | 'UPDATED' | string
  record: ViolationRecord
}

export interface SafetyEventStreamCallbacks {
  onStateChange?: (state: RealtimeConnectionState) => void
  onViolationEvent?: (payload: RealtimeViolationEventPayload) => void
  onCameraStatus?: (status: CameraStatusResponse) => void
}

export interface SafetyEventStreamHandle {
  close: () => void
}

export function resolveSafetyEventsStreamUrl(): string {
  return `${apiBaseUrl}/api/v1/safety/events/stream`
}

export function createSafetyEventStream(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle {
  if (isMockEnabled || typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
    callbacks.onStateChange?.('disabled')
    return {
      close() {
        callbacks.onStateChange?.('closed')
      },
    }
  }

  let closed = false
  callbacks.onStateChange?.('connecting')
  const source = new EventSource(resolveSafetyEventsStreamUrl())

  const markConnected = () => {
    if (!closed) {
      callbacks.onStateChange?.('connected')
    }
  }

  source.onopen = markConnected
  source.addEventListener('ping', markConnected)

  source.addEventListener('violation_event', (event: Event) => {
    if (closed) return
    markConnected()
    try {
      const msg = event as MessageEvent<string>
      const parsed = JSON.parse(msg.data) as RealtimeViolationEventPayload
      if (parsed && parsed.record) {
        callbacks.onViolationEvent?.(parsed)
      }
    } catch {
      // Ignore malformed SSE event payload
    }
  })

  source.addEventListener('camera_status', (event: Event) => {
    if (closed) return
    markConnected()
    try {
      const msg = event as MessageEvent<string>
      const parsed = JSON.parse(msg.data) as CameraStatusResponse
      if (parsed && parsed.camera_id) {
        callbacks.onCameraStatus?.(parsed)
      }
    } catch {
      // Ignore malformed SSE event payload
    }
  })

  source.onerror = () => {
    if (closed) return
    callbacks.onStateChange?.('reconnecting')
  }

  return {
    close() {
      if (closed) return
      closed = true
      source.close()
      callbacks.onStateChange?.('closed')
    },
  }
}
