import { mockCameraZones } from '@/mock/fixtures'
import type { ZonesPort } from '../ports'
import type { CameraConfigUpdateRequest, CameraRunConfig } from '@/types/contract'

export const mockZonesAdapter: ZonesPort = {
  async fetchCameraZones(cameraId: string): Promise<CameraRunConfig | null> {
    const config = mockCameraZones[cameraId]
    return Promise.resolve(config ? JSON.parse(JSON.stringify(config)) : null)
  },

  async updateCameraZones(cameraId: string, request: CameraConfigUpdateRequest): Promise<CameraRunConfig> {
    const prev = mockCameraZones[cameraId]
    if (prev && request.expected_version && prev.config_version !== request.expected_version) {
      const err: Error & { response?: { status: number; data: { detail: string } } } = new Error(
        `camera ${cameraId} config version mismatch: expected ${request.expected_version}, found ${prev.config_version}`,
      )
      err.response = { status: 409, data: { detail: err.message } }
      throw err
    }
    const newVersion = (prev ? prev.config_version : 0) + 1
    const updated: CameraRunConfig = {
      camera_id: cameraId,
      config_version: newVersion,
      source_resolution: request.source_resolution,
      enter_debounce_frames: request.enter_debounce_frames,
      exit_debounce_frames: request.exit_debounce_frames,
      helmet_debounce_frames: request.helmet_debounce_frames,
      alarm_dwell_threshold_seconds: request.alarm_dwell_threshold_seconds,
      zones: request.zones,
    }
    mockCameraZones[cameraId] = updated
    return Promise.resolve(updated)
  },
}
