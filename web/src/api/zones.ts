import { apiClient, isMockEnabled } from './client'
import type { CameraConfigUpdateRequest, CameraRunConfig } from '@/types/contract'
import { mockCameraZones } from '@/mock/fixtures'

export async function fetchCameraZones(cameraId: string): Promise<CameraRunConfig | null> {
  if (isMockEnabled) {
    const config = mockCameraZones[cameraId]
    return Promise.resolve(config ? JSON.parse(JSON.stringify(config)) : null)
  }
  try {
    const res = await apiClient.get<CameraRunConfig>(`/api/v1/cameras/${cameraId}/zones`)
    return res.data
  } catch (err: any) {
    if (err.response?.status === 404) {
      // 404 说明尚未配置围栏
      return null
    }
    console.warn(`Fetch zones for ${cameraId} failed, fallback to mock:`, err)
    return mockCameraZones[cameraId] || null
  }
}

export async function updateCameraZones(
  cameraId: string,
  request: CameraConfigUpdateRequest
): Promise<CameraRunConfig> {
  if (isMockEnabled) {
    const prev = mockCameraZones[cameraId]
    if (prev && request.expected_version && prev.config_version !== request.expected_version) {
      const err: any = new Error(
        `camera ${cameraId} config version mismatch: expected ${request.expected_version}, found ${prev.config_version}`
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
  }
  const res = await apiClient.put<CameraRunConfig>(`/api/v1/cameras/${cameraId}/zones`, request)
  return res.data
}
