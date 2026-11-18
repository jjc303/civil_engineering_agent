import { apiClient } from '../client'
import type {
  CreateRectificationTaskPayload,
  RectificationTaskFilters,
  RectificationTasksPort,
  UpdateRectificationTaskPayload,
} from '../ports'
import type { PendingAction, RectificationTaskDetail, RectificationTaskPageResponse, RectificationTaskRecord } from '@/types/contract'

export const httpRectificationTasksAdapter: RectificationTasksPort = {
  async fetchRectificationTasks(filters: RectificationTaskFilters = {}): Promise<RectificationTaskPageResponse> {
    const res = await apiClient.get<RectificationTaskPageResponse>('/api/v1/rectification-tasks', { params: filters })
    return res.data
  },

  async fetchRectificationTask(taskId: string): Promise<RectificationTaskDetail> {
    const res = await apiClient.get<RectificationTaskDetail>(`/api/v1/rectification-tasks/${taskId}`)
    return res.data
  },

  async createRectificationTask(payload: CreateRectificationTaskPayload): Promise<RectificationTaskRecord> {
    const res = await apiClient.post<RectificationTaskRecord>('/api/v1/rectification-tasks', payload)
    return res.data
  },

  async updateRectificationTask(
    taskId: string,
    payload: UpdateRectificationTaskPayload,
  ): Promise<RectificationTaskRecord> {
    const res = await apiClient.patch<RectificationTaskRecord>(`/api/v1/rectification-tasks/${taskId}`, payload)
    return res.data
  },

  async proposeRectificationTaskCreate(payload: CreateRectificationTaskPayload): Promise<PendingAction> {
    const res = await apiClient.post<{ pending_action: PendingAction }>(
      '/api/v1/rectification-tasks/pending-create',
      payload,
    )
    return res.data.pending_action
  },

  async proposeRectificationTaskUpdate(
    taskId: string,
    payload: UpdateRectificationTaskPayload,
  ): Promise<PendingAction> {
    const res = await apiClient.post<{ pending_action: PendingAction }>(
      `/api/v1/rectification-tasks/${taskId}/pending-update`,
      payload,
    )
    return res.data.pending_action
  },
}
