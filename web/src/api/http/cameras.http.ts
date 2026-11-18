import { apiClient } from '../client'
import type { CamerasPort } from '../ports'
import type { CameraStatusResponse } from '@/types/contract'

export const httpCamerasAdapter: CamerasPort = {
  async fetchCameras(): Promise<CameraStatusResponse[]> {
    const res = await apiClient.get<CameraStatusResponse[]>('/api/v1/cameras')
    return res.data
  },

  async fetchCameraStatus(cameraId: string): Promise<CameraStatusResponse> {
    const res = await apiClient.get<CameraStatusResponse>(`/api/v1/cameras/${cameraId}/status`)
    return res.data
  },
}
