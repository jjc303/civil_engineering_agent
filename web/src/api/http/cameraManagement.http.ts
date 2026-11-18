import { apiClient } from '../client'
import type { CameraManagementPort, CvNodeMediaDirectory } from '../ports'
import type { CvNodeResponse, ManagedCameraResponse } from '@/types/contract'

export const httpCameraManagementAdapter: CameraManagementPort = {
  async fetchCvNodes(): Promise<CvNodeResponse[]> {
    const res = await apiClient.get<CvNodeResponse[]>('/api/v1/cv-nodes')
    return res.data
  },

  async createCvNode(payload: {
    node_id: string
    display_name: string
    control_url: string
    capacity: number
  }): Promise<CvNodeResponse & { control_token: string }> {
    const res = await apiClient.post<CvNodeResponse & { control_token: string }>('/api/v1/cv-nodes', payload)
    return res.data
  },

  async fetchManagedCameras(): Promise<ManagedCameraResponse[]> {
    const res = await apiClient.get<ManagedCameraResponse[]>('/api/v1/managed-cameras')
    return res.data
  },

  async createManagedCamera(payload: {
    camera_id: string
    display_name: string
    node_id: string
    source_type: 'rtsp' | 'file'
    source_uri: string
  }): Promise<ManagedCameraResponse> {
    const res = await apiClient.post<ManagedCameraResponse>('/api/v1/managed-cameras', payload)
    return res.data
  },

  async updateManagedCamera(
    cameraId: string,
    payload: {
      display_name?: string
      node_id: string
      source_type: 'rtsp' | 'file'
      source_uri?: string
    },
  ): Promise<ManagedCameraResponse> {
    const res = await apiClient.put<ManagedCameraResponse>(
      `/api/v1/managed-cameras/${encodeURIComponent(cameraId)}/source`,
      payload,
    )
    return res.data
  },

  async fetchNodeMediaFiles(nodeId: string, directory?: string): Promise<CvNodeMediaDirectory> {
    const res = await apiClient.get<CvNodeMediaDirectory>(
      `/api/v1/cv-nodes/${encodeURIComponent(nodeId)}/media-files`,
      { params: directory ? { directory } : undefined },
    )
    return res.data
  },

  async setMonitoring(cameraId: string, action: 'start' | 'stop'): Promise<void> {
    await apiClient.post(`/api/v1/cameras/${encodeURIComponent(cameraId)}/monitoring:${action}`, {})
  },
}
