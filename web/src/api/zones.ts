import { getApiBundle } from './index'
import type { CameraConfigUpdateRequest, CameraRunConfig } from '@/types/contract'

export async function fetchCameraZones(cameraId: string): Promise<CameraRunConfig | null> {
  return (await getApiBundle()).zones.fetchCameraZones(cameraId)
}

export async function updateCameraZones(
  cameraId: string,
  request: CameraConfigUpdateRequest,
): Promise<CameraRunConfig> {
  return (await getApiBundle()).zones.updateCameraZones(cameraId, request)
}
