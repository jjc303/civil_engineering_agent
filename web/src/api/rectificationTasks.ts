import {
  getApiBundle,
  type CreateRectificationTaskPayload,
  type RectificationTaskFilters,
  type UpdateRectificationTaskPayload,
} from './index'
import type {
  PendingAction,
  RectificationTaskDetail,
  RectificationTaskPageResponse,
  RectificationTaskRecord,
} from '@/types/contract'

export type {
  CreateRectificationTaskPayload,
  RectificationTaskFilters,
  UpdateRectificationTaskPayload,
}

export async function fetchRectificationTasks(
  filters: RectificationTaskFilters = {},
): Promise<RectificationTaskPageResponse> {
  return (await getApiBundle()).rectificationTasks.fetchRectificationTasks(filters)
}

export async function fetchRectificationTask(taskId: string): Promise<RectificationTaskDetail> {
  return (await getApiBundle()).rectificationTasks.fetchRectificationTask(taskId)
}

export async function createRectificationTask(
  payload: CreateRectificationTaskPayload,
): Promise<RectificationTaskRecord> {
  return (await getApiBundle()).rectificationTasks.createRectificationTask(payload)
}

export async function updateRectificationTask(
  taskId: string,
  payload: UpdateRectificationTaskPayload,
): Promise<RectificationTaskRecord> {
  return (await getApiBundle()).rectificationTasks.updateRectificationTask(taskId, payload)
}

export async function proposeRectificationTaskCreate(
  payload: CreateRectificationTaskPayload,
): Promise<PendingAction> {
  return (await getApiBundle()).rectificationTasks.proposeRectificationTaskCreate(payload)
}

export async function proposeRectificationTaskUpdate(
  taskId: string,
  payload: UpdateRectificationTaskPayload,
): Promise<PendingAction> {
  return (await getApiBundle()).rectificationTasks.proposeRectificationTaskUpdate(taskId, payload)
}
