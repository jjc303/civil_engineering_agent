import { apiClient, isMockEnabled } from './client'
import type {
  ViolationPageResponse,
  ViolationRecord,
  ViolationSeverity,
  ViolationStatistics,
  ViolationType,
  EventStatus,
} from '@/types/contract'
import { mockPageResponse, mockStatistics } from '@/mock/fixtures'

export interface ViolationQueryParams {
  camera_id?: string
  violation_type?: ViolationType
  severity?: ViolationSeverity
  status?: EventStatus
  start_time_utc?: string
  end_time_utc?: string
  limit?: number
  offset?: number
}

export async function fetchViolations(params: ViolationQueryParams = {}): Promise<ViolationPageResponse> {
  if (isMockEnabled) {
    return Promise.resolve(mockPageResponse)
  }
  const res = await apiClient.get<ViolationPageResponse | ViolationRecord[]>('/api/v1/violations', {
    params,
  })
  // 兼容可能返回的裸数组形式
  if (Array.isArray(res.data)) {
    return {
      items: res.data,
      total: res.data.length,
      limit: params.limit || 100,
      offset: params.offset || 0,
    }
  }
  return res.data
}

export async function fetchViolationStatistics(params: {
  camera_id?: string
  start_time_utc?: string
  end_time_utc?: string
} = {}): Promise<ViolationStatistics> {
  if (isMockEnabled) {
    return Promise.resolve(mockStatistics)
  }
  const res = await apiClient.get<ViolationStatistics>('/api/v1/violations/statistics', {
    params,
  })
  return res.data
}
