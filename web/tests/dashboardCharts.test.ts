import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DASHBOARD_CHART_THEME,
  buildDailyBarOption,
  buildHeatmapChartOption,
  buildSeverityBarOption,
  buildTypePieOption,
  resolveRiskBarColor,
} from '@/composables/useDashboardCharts'

describe('useDashboardCharts pure option builders', () => {
  const labels = {
    chartTodayEvents: '今日事件',
    chartUnitSuffix: (value: number) => `${value} 起`,
    riskSafe: '安全',
    riskExtreme: '極高',
    riskHigh: '高',
    riskNormal: '一般',
    tooltipFreq: '違規頻次：',
    tooltipRisk: '風險等級：',
    unitCount: '起',
    legendHighRisk: '高風險',
    legendNoViolation: '無違規',
  }

  it('maps risk bar colors against configured thresholds', () => {
    assert.equal(resolveRiskBarColor(0.8), DASHBOARD_CHART_THEME.riskBarColors.high)
    assert.equal(resolveRiskBarColor(0.45), DASHBOARD_CHART_THEME.riskBarColors.medium)
    assert.equal(resolveRiskBarColor(0.1), DASHBOARD_CHART_THEME.riskBarColors.low)
  })

  it('builds pie and severity bar options cleanly for empty and populated stats', () => {
    const emptyPie = buildTypePieOption({
      stats: { total_violations: 0, average_duration_seconds: 0, by_type: { NO_HELMET: 0, DANGER_ZONE_INTRUSION: 0, DWELL_TIMEOUT: 0 }, by_severity: { CRITICAL: 0, WARNING: 0, INFO: 0 } },
      violationLabels: { NO_HELMET: '未戴安全帽', DANGER_ZONE_INTRUSION: '闖入危險區域', DWELL_TIMEOUT: '滯留超時' },
      labels,
      animation: false,
    })
    assert.equal(emptyPie.title.text, '0')
    assert.equal(emptyPie.series[0]!.data.length, 0)

    const populatedSeverity = buildSeverityBarOption({
      stats: { total_violations: 5, average_duration_seconds: 12, by_type: { NO_HELMET: 3, DANGER_ZONE_INTRUSION: 2, DWELL_TIMEOUT: 0 }, by_severity: { INFO: 1, WARNING: 2, CRITICAL: 2 } },
      severityKeys: ['INFO', 'WARNING', 'CRITICAL'],
      severityLabel: (s) => s,
      chartUnitSuffix: labels.chartUnitSuffix,
      animation: false,
    })
    assert.deepEqual(
      populatedSeverity.series[0]!.data.map((d) => d.value),
      [1, 2, 2],
    )
  })

  it('builds 24-hour heatmap and lookback-day daily bar options', () => {
    const heatmapOption = buildHeatmapChartOption({
      heatmap: {
        lookback_days: 7,
        total_violations: 4,
        daily_counts: [0, 1, 0, 2, 0, 1, 0],
        hourly_risk: [{ hour: 10, count: 4, risk_level: 'HIGH', risk_pct: 100 }],
        zone_risks: [],
        summary: 'test',
      },
      labels,
      animation: false,
    })
    assert.equal(heatmapOption.xAxis.data.length, 24)
    assert.equal(heatmapOption.visualMap.max, 4)

    const dailyOption = buildDailyBarOption({
      heatmap: {
        lookback_days: 7,
        total_violations: 4,
        daily_counts: [0, 1, 0, 2, 0, 1, 0],
        hourly_risk: [],
        zone_risks: [],
        summary: 'test',
      },
      labels,
      animation: false,
      referenceDate: new Date('2026-11-18T00:00:00Z'),
    })
    assert.equal(dailyOption.xAxis.data.length, 7)
    assert.deepEqual(dailyOption.series[0]!.data, [0, 1, 0, 2, 0, 1, 0])
  })
})
