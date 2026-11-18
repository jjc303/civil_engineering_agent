import { apiClient } from '../client'
import type { RiskHeatmapData, ViolationQueryParams, ViolationsPort } from '../ports'
import type { ViolationPageResponse, ViolationRecord, ViolationStatistics } from '@/types/contract'

export const httpViolationsAdapter: ViolationsPort = {
  async fetchViolations(params: ViolationQueryParams = {}): Promise<ViolationPageResponse> {
    const res = await apiClient.get<ViolationPageResponse | ViolationRecord[]>('/api/v1/violations', { params })
    if (Array.isArray(res.data)) {
      return {
        items: res.data,
        total: res.data.length,
        limit: params.limit || 100,
        offset: params.offset || 0,
      }
    }
    return res.data
  },

  async fetchViolationStatistics(
    params: {
      camera_id?: string
      start_time_utc?: string
      end_time_utc?: string
    } = {},
  ): Promise<ViolationStatistics> {
    const res = await apiClient.get<ViolationStatistics>('/api/v1/violations/statistics', { params })
    return res.data
  },

  async fetchRiskHeatmap(lookbackDays = 7): Promise<RiskHeatmapData> {
    const tzOffset = -new Date().getTimezoneOffset() / 60
    const res = await apiClient.get<RiskHeatmapData>('/api/v1/safety/risk-heatmap', {
      params: { lookback_days: lookbackDays, timezone_offset_hours: tzOffset },
    })
    return res.data
  },
}
