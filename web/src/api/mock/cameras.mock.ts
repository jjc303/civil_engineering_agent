import { mockCameras } from '@/mock/fixtures'
import type { CamerasPort } from '../ports'
import type { CameraStatusResponse } from '@/types/contract'

export const mockCamerasAdapter: CamerasPort = {
  async fetchCameras(): Promise<CameraStatusResponse[]> {
    return Promise.resolve([...mockCameras])
  },

  async fetchCameraStatus(cameraId: string): Promise<CameraStatusResponse> {
    const found = mockCameras.find((c) => c.camera_id === cameraId)
    if (!found) {
      throw new Error(`Camera ${cameraId} not found`)
    }
    return Promise.resolve(found)
  },
}
