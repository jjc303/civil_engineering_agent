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

export interface RiskHeatmapData {
  lookback_days: number
  total_violations: number
  daily_counts: number[]
  hourly_risk: Array<{ hour: number; count: number; risk_level: string; risk_pct: number }>
  zone_risks: Array<{ zone_name: string; camera_id: string; total: number; by_type: Record<string, number>; risk_score: number }>
  summary: string
}

export async function fetchRiskHeatmap(lookbackDays = 7): Promise<RiskHeatmapData> {
  const tzOffset = -new Date().getTimezoneOffset() / 60
  if (isMockEnabled) {
    return Promise.resolve({
      lookback_days: lookbackDays,
      total_violations: 0,
      daily_counts: new Array(lookbackDays).fill(0),
      hourly_risk: Array.from({ length: 24 }, (_, i) => ({ hour: i, count: 0, risk_level: 'LOW' as const, risk_pct: 0 })),
      zone_risks: [],
      summary: '模拟数据：暂无风险数据。',
    })
  }
  const res = await apiClient.get<RiskHeatmapData>('/api/v1/safety/risk-heatmap', {
    params: { lookback_days: lookbackDays, timezone_offset_hours: tzOffset },
  })
  return res.data
}
