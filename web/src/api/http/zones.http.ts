import { apiClient } from '../client'
import type { ZonesPort } from '../ports'
import type { CameraConfigUpdateRequest, CameraRunConfig } from '@/types/contract'

export const httpZonesAdapter: ZonesPort = {
  async fetchCameraZones(cameraId: string): Promise<CameraRunConfig | null> {
    const res = await apiClient.get<CameraRunConfig>(`/api/v1/cameras/${cameraId}/zones`)
    return res.data
  },

  async updateCameraZones(cameraId: string, request: CameraConfigUpdateRequest): Promise<CameraRunConfig> {
    const res = await apiClient.put<CameraRunConfig>(`/api/v1/cameras/${cameraId}/zones`, request)
    return res.data
  },
}
