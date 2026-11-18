import { getApiBundle } from './index'
import type { CameraStatusResponse } from '@/types/contract'

export async function fetchCameras(): Promise<CameraStatusResponse[]> {
  return (await getApiBundle()).cameras.fetchCameras()
}

export async function fetchCameraStatus(cameraId: string): Promise<CameraStatusResponse> {
  return (await getApiBundle()).cameras.fetchCameraStatus(cameraId)
}
