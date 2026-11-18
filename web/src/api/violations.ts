import { getApiBundle, type RiskHeatmapData, type ViolationQueryParams } from './index'
import type { ViolationPageResponse, ViolationStatistics } from '@/types/contract'

export type { RiskHeatmapData, ViolationQueryParams }

export async function fetchViolations(params: ViolationQueryParams = {}): Promise<ViolationPageResponse> {
  return (await getApiBundle()).violations.fetchViolations(params)
}

export async function fetchViolationStatistics(
  params: {
    camera_id?: string
    start_time_utc?: string
    end_time_utc?: string
  } = {},
): Promise<ViolationStatistics> {
  return (await getApiBundle()).violations.fetchViolationStatistics(params)
}

export async function fetchRiskHeatmap(lookbackDays = 7): Promise<RiskHeatmapData> {
  return (await getApiBundle()).violations.fetchRiskHeatmap(lookbackDays)
}
