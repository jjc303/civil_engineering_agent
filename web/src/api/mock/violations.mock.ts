import { mockPageResponse, mockStatistics } from '@/mock/fixtures'
import { translateApiMessage, type RiskHeatmapData, type ViolationQueryParams, type ViolationsPort } from '../ports'
import type { ViolationPageResponse, ViolationStatistics } from '@/types/contract'

export const mockViolationsAdapter: ViolationsPort = {
  async fetchViolations(_params: ViolationQueryParams = {}): Promise<ViolationPageResponse> {
    return Promise.resolve(mockPageResponse)
  },

  async fetchViolationStatistics(_params = {}): Promise<ViolationStatistics> {
    return Promise.resolve(mockStatistics)
  },

  async fetchRiskHeatmap(lookbackDays = 7): Promise<RiskHeatmapData> {
    return Promise.resolve({
      lookback_days: lookbackDays,
      total_violations: 0,
      daily_counts: new Array(lookbackDays).fill(0),
      hourly_risk: Array.from({ length: 24 }, (_, i) => ({
        hour: i,
        count: 0,
        risk_level: 'LOW' as const,
        risk_pct: 0,
      })),
      zone_risks: [],
      summary: translateApiMessage('mock.heatmapEmptySummary'),
    })
  },
}
