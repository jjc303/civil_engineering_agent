import { apiBaseUrl } from '@/utils/deployment'
import { getApiBundle, type CvNodeMediaDirectory, type CvNodeMediaEntry } from './index'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'

export type { CvNodeMediaDirectory, CvNodeMediaEntry }

export async function fetchCvNodes(): Promise<CvNodeResponse[]> {
  return (await getApiBundle()).cameraManagement.fetchCvNodes()
}

export async function createCvNode(payload: {
  node_id: string
  display_name: string
  control_url: string
  capacity: number
}): Promise<CvNodeResponse & { control_token: string }> {
  return (await getApiBundle()).cameraManagement.createCvNode(payload)
}

export async function fetchManagedCameras(): Promise<ManagedCameraResponse[]> {
  return (await getApiBundle()).cameraManagement.fetchManagedCameras()
}

export async function createManagedCamera(payload: {
  camera_id: string
  display_name: string
  node_id: string
  source_type: 'rtsp' | 'file'
  source_uri: string
}): Promise<ManagedCameraResponse> {
  return (await getApiBundle()).cameraManagement.createManagedCamera(payload)
}

export async function updateManagedCamera(
  cameraId: string,
  payload: {
    display_name?: string
    node_id: string
    source_type: 'rtsp' | 'file'
    source_uri?: string
  },
): Promise<ManagedCameraResponse> {
  return (await getApiBundle()).cameraManagement.updateManagedCamera(cameraId, payload)
}

export async function fetchNodeMediaFiles(nodeId: string, directory?: string): Promise<CvNodeMediaDirectory> {
  return (await getApiBundle()).cameraManagement.fetchNodeMediaFiles(nodeId, directory)
}

export async function setMonitoring(cameraId: string, action: 'start' | 'stop'): Promise<void> {
  return (await getApiBundle()).cameraManagement.setMonitoring(cameraId, action)
}

export function previewUrl(cameraId: string): string {
  return `${apiBaseUrl}/api/v1/cameras/${encodeURIComponent(cameraId)}/preview`
}

export function previewFrameUrl(cameraId: string): string {
  return `${apiBaseUrl}/api/v1/cameras/${encodeURIComponent(cameraId)}/preview.jpg`
}
