import { apiClient, isMockEnabled } from './client'
import type { PendingAction, RectificationTaskDetail, RectificationTaskPageResponse, RectificationTaskStatus } from '@/types/contract'

export interface RectificationTaskFilters {
  status?: RectificationTaskStatus
  owner?: string
  overdue?: boolean
  limit?: number
  offset?: number
}

export interface CreateRectificationTaskPayload {
  conversation_id: string
  event_uuid: string
  title: string
  description?: string
  owner: string
  due_at_utc: string
}

export interface UpdateRectificationTaskPayload {
  conversation_id: string
  owner?: string
  due_at_utc?: string
  status?: RectificationTaskStatus
  note?: string
}

export async function fetchRectificationTasks(filters: RectificationTaskFilters = {}): Promise<RectificationTaskPageResponse> {
  if (isMockEnabled) return { items: [], total: 0, limit: filters.limit || 20, offset: filters.offset || 0 }
  const res = await apiClient.get<RectificationTaskPageResponse>('/api/v1/rectification-tasks', { params: filters })
  return res.data
}

export async function fetchRectificationTask(taskId: string): Promise<RectificationTaskDetail> {
  const res = await apiClient.get<RectificationTaskDetail>(`/api/v1/rectification-tasks/${taskId}`)
  return res.data
}

export async function proposeRectificationTaskCreate(payload: CreateRectificationTaskPayload): Promise<PendingAction> {
  const res = await apiClient.post<{ pending_action: PendingAction }>('/api/v1/rectification-tasks/pending-create', payload)
  return res.data.pending_action
}

export async function proposeRectificationTaskUpdate(taskId: string, payload: UpdateRectificationTaskPayload): Promise<PendingAction> {
  const res = await apiClient.post<{ pending_action: PendingAction }>(`/api/v1/rectification-tasks/${taskId}/pending-update`, payload)
  return res.data.pending_action
}
