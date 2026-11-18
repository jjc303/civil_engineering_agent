import { httpCameraManagementAdapter } from './http/cameraManagement.http'
import { httpCamerasAdapter } from './http/cameras.http'
import { httpChatAdapter } from './http/chat.http'
import { httpRealtimeAdapter, resolveSafetyEventsStreamUrl } from './http/realtime.http'
import { httpRectificationTasksAdapter } from './http/rectificationTasks.http'
import { httpUiConfigAdapter } from './http/uiConfig.http'
import { httpViolationsAdapter } from './http/violations.http'
import { httpZonesAdapter } from './http/zones.http'
import type {
  CameraManagementPort,
  CamerasPort,
  ChatPort,
  RealtimePort,
  RectificationTasksPort,
  SafetyEventStreamCallbacks,
  SafetyEventStreamHandle,
  UiConfigPort,
  ViolationsPort,
  ZonesPort,
} from './ports'

export interface ApiBundle {
  cameras: CamerasPort
  violations: ViolationsPort
  zones: ZonesPort
  chat: ChatPort
  cameraManagement: CameraManagementPort
  rectificationTasks: RectificationTasksPort
  uiConfig: UiConfigPort
  realtime: RealtimePort
}

const httpBundle: ApiBundle = {
  cameras: httpCamerasAdapter,
  violations: httpViolationsAdapter,
  zones: httpZonesAdapter,
  chat: httpChatAdapter,
  cameraManagement: httpCameraManagementAdapter,
  rectificationTasks: httpRectificationTasksAdapter,
  uiConfig: httpUiConfigAdapter,
  realtime: httpRealtimeAdapter,
}

let cachedBundle: Promise<ApiBundle> | null = null

export function getApiBundle(): Promise<ApiBundle> {
  if (import.meta.env?.VITE_USE_MOCK === 'true') {
    if (!cachedBundle) {
      cachedBundle = import('./mock').then((mod) => mod.createMockApiBundle())
    }
    return cachedBundle
  }
  return Promise.resolve(httpBundle)
}

export function createStreamFromBundle(callbacks: SafetyEventStreamCallbacks): SafetyEventStreamHandle {
  if (import.meta.env?.VITE_USE_MOCK === 'true') {
    callbacks.onStateChange?.('disabled')
    return {
      close() {
        callbacks.onStateChange?.('closed')
      },
    }
  }
  return httpBundle.realtime.createSafetyEventStream(callbacks)
}

export { resolveSafetyEventsStreamUrl }
export * from './ports'
export * from './client'
