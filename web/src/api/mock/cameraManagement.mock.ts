import { httpCameraManagementAdapter } from '../http/cameraManagement.http'
import type { CameraManagementPort } from '../ports'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'

export const mockCameraManagementAdapter: CameraManagementPort = {
  ...httpCameraManagementAdapter,
  async fetchCvNodes(): Promise<CvNodeResponse[]> {
    return []
  },
  async fetchManagedCameras(): Promise<ManagedCameraResponse[]> {
    return []
  },
}
