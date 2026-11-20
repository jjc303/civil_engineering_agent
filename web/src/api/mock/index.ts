import { mockCameraManagementAdapter } from './cameraManagement.mock'
import { mockCamerasAdapter } from './cameras.mock'
import { mockChatAdapter } from './chat.mock'
import { mockRealtimeAdapter } from './realtime.mock'
import { mockRectificationTasksAdapter } from './rectificationTasks.mock'
import { mockUiConfigAdapter } from './uiConfig.mock'
import { mockViolationsAdapter } from './violations.mock'
import { mockZonesAdapter } from './zones.mock'

export function createMockApiBundle() {
  return {
    cameras: mockCamerasAdapter,
    violations: mockViolationsAdapter,
    zones: mockZonesAdapter,
    chat: mockChatAdapter,
    cameraManagement: mockCameraManagementAdapter,
    rectificationTasks: mockRectificationTasksAdapter,
    uiConfig: mockUiConfigAdapter,
    realtime: mockRealtimeAdapter,
  }
}
