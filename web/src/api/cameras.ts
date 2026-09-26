import { apiClient, isMockEnabled } from './client'
import type { CameraStatusResponse } from '@/types/contract'
import { mockCameras } from '@/mock/fixtures'

export async function fetchCameras(): Promise<CameraStatusResponse[]> {
  if (isMockEnabled) {
    return Promise.resolve([...mockCameras])
  }
  const res = await apiClient.get<CameraStatusResponse[]>('/api/v1/cameras')
  return res.data
}

export async function fetchCameraStatus(cameraId: string): Promise<CameraStatusResponse> {
  if (isMockEnabled) {
    const found = mockCameras.find((c) => c.camera_id === cameraId)
    if (!found) {
      throw new Error(`Camera ${cameraId} not found`)
    }
    return Promise.resolve(found)
  }
  const res = await apiClient.get<CameraStatusResponse>(`/api/v1/cameras/${cameraId}/status`)
  return res.data
}
