import { apiClient, isMockEnabled } from './client'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'

export interface CvNodeMediaEntry { name: string; path: string }
export interface CvNodeMediaDirectory { current_path: string; parent_path: string | null; directories: CvNodeMediaEntry[]; files: CvNodeMediaEntry[] }

const adminHeaders = () => ({
  Authorization: `Bearer ${import.meta.env.VITE_AGENT_ADMIN_TOKEN || ''}`,
})

export async function fetchCvNodes(): Promise<CvNodeResponse[]> {
  if (isMockEnabled) return []
  const res = await apiClient.get<CvNodeResponse[]>('/api/v1/cv-nodes', { headers: adminHeaders() })
  return res.data
}

export async function createCvNode(payload: { node_id: string; display_name: string; control_url: string; capacity: number }): Promise<CvNodeResponse & { control_token: string }> {
  const res = await apiClient.post<CvNodeResponse & { control_token: string }>('/api/v1/cv-nodes', payload, { headers: adminHeaders() })
  return res.data
}

export async function fetchManagedCameras(): Promise<ManagedCameraResponse[]> {
  if (isMockEnabled) return []
  const res = await apiClient.get<ManagedCameraResponse[]>('/api/v1/managed-cameras', { headers: adminHeaders() })
  return res.data
}

export async function createManagedCamera(payload: {
  camera_id: string; display_name: string; node_id: string; source_type: 'rtsp' | 'file'; source_uri: string
}): Promise<ManagedCameraResponse> {
  const res = await apiClient.post<ManagedCameraResponse>('/api/v1/managed-cameras', payload, { headers: adminHeaders() })
  return res.data
}

export async function updateManagedCamera(cameraId: string, payload: {
  display_name?: string; node_id: string; source_type: 'rtsp' | 'file'; source_uri?: string
}): Promise<ManagedCameraResponse> {
  const res = await apiClient.put<ManagedCameraResponse>(`/api/v1/managed-cameras/${encodeURIComponent(cameraId)}/source`, payload, { headers: adminHeaders() })
  return res.data
}

export async function fetchNodeMediaFiles(nodeId: string, directory?: string): Promise<CvNodeMediaDirectory> {
  const res = await apiClient.get<CvNodeMediaDirectory>(`/api/v1/cv-nodes/${encodeURIComponent(nodeId)}/media-files`, {
    headers: adminHeaders(), params: directory ? { directory } : undefined,
  })
  return res.data
}

export async function setMonitoring(cameraId: string, action: 'start' | 'stop'): Promise<void> {
  await apiClient.post(`/api/v1/cameras/${encodeURIComponent(cameraId)}/monitoring:${action}`, {}, { headers: adminHeaders() })
}

export function previewUrl(cameraId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/v1/cameras/${encodeURIComponent(cameraId)}/preview`
}

export function previewFrameUrl(cameraId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/v1/cameras/${encodeURIComponent(cameraId)}/preview.jpg`
}
