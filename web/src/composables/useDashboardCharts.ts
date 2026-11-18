import { computed, type Ref } from 'vue'
import type { RiskHeatmapData } from '@/api/violations'
import type { ViolationSeverity, ViolationStatistics, ViolationType } from '@/types/contract'

export const RISK_SCORE_THRESHOLDS = {
  high: 0.6,
  medium: 0.3,
} as const

export const HOURLY_HEATMAP_THRESHOLDS = {
  extremeRatio: 0.6,
  highRatio: 0.25,
} as const

export const DASHBOARD_CHART_THEME = {
  typeColors: ['#9181ea', '#e4a58c', '#85b5b2'],
  severityColors: {
    INFO: '#85b5b2',
    WARNING: '#b2a1e5',
    CRITICAL: '#e4a58c',
  } as Record<ViolationSeverity, string>,
  riskBarColors: {
    high: '#e4a58c',
    medium: '#e0c48c',
    low: '#85b5b2',
  },
  heatmapPalette: ['#f4f3f9', '#ded6f7', '#bcabec', '#8f70db', '#6245b7'],
  heatmapLevelColors: {
    safe: '#85b5b2',
    normal: '#7969d0',
    high: '#caa266',
    extreme: '#ce7666',
  },
  dailyBarColor: '#9b86d2',
  dailyBarHoverColor: '#7f66c4',
  titleTextColor: '#625775',
  subtextColor: '#8d869b',
  axisLabelColor: '#989daf',
  legendTextColor: '#72798b',
  splitLineColor: '#ececf4',
  emptyPieColor: '#eeebf6',
  pieBorderColor: '#f9f9fd',
  tooltipBg: 'rgba(255, 255, 255, 0.96)',
  tooltipBorder: '#ece9f4',
  tooltipText: '#433d59',
} as const

export function resolveRiskBarColor(score: number): string {
  if (score > RISK_SCORE_THRESHOLDS.high) return DASHBOARD_CHART_THEME.riskBarColors.high
  if (score > RISK_SCORE_THRESHOLDS.medium) return DASHBOARD_CHART_THEME.riskBarColors.medium
  return DASHBOARD_CHART_THEME.riskBarColors.low
}

export interface ChartI18nLabels {
  chartTodayEvents: string
  chartUnitSuffix: (value: number) => string
  riskSafe: string
  riskExtreme: string
  riskHigh: string
  riskNormal: string
  tooltipFreq: string
  tooltipRisk: string
  unitCount: string
  legendHighRisk: string
  legendNoViolation: string
}

export function buildTypePieOption(params: {
  stats: ViolationStatistics | null
  violationLabels: Record<ViolationType, string>
  labels: Pick<ChartI18nLabels, 'chartTodayEvents' | 'chartUnitSuffix'>
  animation: boolean
}) {
  const { stats, violationLabels, labels, animation } = params
  const hasViolations = Boolean(stats?.total_violations)

  return {
    animation,
    animationDuration: 400,
    color: [...DASHBOARD_CHART_THEME.typeColors],
    title: {
      text: String(stats?.total_violations ?? 0),
      subtext: labels.chartTodayEvents,
      left: '28%',
      top: '36%',
      textAlign: 'center',
      textStyle: { color: DASHBOARD_CHART_THEME.titleTextColor, fontSize: 30, fontWeight: 500 },
      subtextStyle: { color: DASHBOARD_CHART_THEME.subtextColor, fontSize: 11 },
    },
    tooltip: {
      trigger: 'item',
      valueFormatter: (value: unknown) => labels.chartUnitSuffix(Number(value ?? 0)),
    },
    legend: {
      data: Object.values(violationLabels),
      orient: 'vertical',
      right: '1%',
      top: 'middle',
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      selectedMode: false,
      textStyle: { color: DASHBOARD_CHART_THEME.legendTextColor, fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['55%', '73%'],
        center: ['28%', '50%'],
        label: { show: false },
        stillShowZeroSum: false,
        showEmptyCircle: true,
        emptyCircleStyle: { color: DASHBOARD_CHART_THEME.emptyPieColor },
        itemStyle: { borderWidth: 3, borderColor: DASHBOARD_CHART_THEME.pieBorderColor, borderRadius: 5 },
        data: hasViolations
          ? Object.entries(violationLabels).map(([key, name]) => ({
              name,
              value: stats?.by_type[key as ViolationType] ?? 0,
            }))
          : [],
      },
    ],
  }
}

export function buildSeverityBarOption(params: {
  stats: ViolationStatistics | null
  severityKeys: ReadonlyArray<ViolationSeverity>
  severityLabel: (severity: ViolationSeverity) => string
  chartUnitSuffix: (value: number) => string
  animation: boolean
}) {
  const { stats, severityKeys, severityLabel, chartUnitSuffix, animation } = params

  return {
    animation,
    animationDuration: 400,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value: unknown) => chartUnitSuffix(Number(value ?? 0)),
    },
    grid: { top: 22, bottom: 22, left: 48, right: 35 },
    xAxis: {
      type: 'value',
      minInterval: 1,
      max: stats?.total_violations === 0 ? 1 : undefined,
      splitLine: { lineStyle: { color: DASHBOARD_CHART_THEME.splitLineColor, type: 'dashed' } },
      axisLabel: { color: '#8a8fa0' },
    },
    yAxis: {
      type: 'category',
      data: severityKeys.map((code) => severityLabel(code)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: DASHBOARD_CHART_THEME.legendTextColor, fontSize: 12 },
    },
    series: [
      {
        type: 'bar',
        barWidth: 14,
        label: { show: true, position: 'right', color: '#817590' },
        itemStyle: { borderRadius: [0, 5, 5, 0] },
        data: severityKeys.map((severity) => ({
          value: stats?.by_severity[severity] ?? 0,
          itemStyle: { color: DASHBOARD_CHART_THEME.severityColors[severity] },
        })),
      },
    ],
  }
}

export function buildHeatmapChartOption(params: {
  heatmap: RiskHeatmapData | null
  labels: Pick<
    ChartI18nLabels,
    'riskSafe' | 'riskExtreme' | 'riskHigh' | 'riskNormal' | 'tooltipFreq' | 'tooltipRisk' | 'unitCount' | 'legendHighRisk' | 'legendNoViolation'
  >
  animation: boolean
}) {
  const { heatmap, labels, animation } = params
  const hourlyData = heatmap?.hourly_risk ?? []
  const maxCount = Math.max(1, ...hourlyData.map((item) => item.count))

  return {
    animation,
    tooltip: {
      position: 'top',
      backgroundColor: DASHBOARD_CHART_THEME.tooltipBg,
      borderColor: DASHBOARD_CHART_THEME.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: DASHBOARD_CHART_THEME.tooltipText, fontSize: 12 },
      formatter: (item: { value?: unknown }) => {
        const raw = Array.isArray(item.value) ? item.value : [0, 0, 0]
        const hour = Number(raw[0])
        const count = Number(raw[2])
        const nextHour = (hour + 1) % 24
        const timeRange = `${String(hour).padStart(2, '0')}:00 - ${String(nextHour).padStart(2, '0')}:00`
        const isExtreme = count >= maxCount * HOURLY_HEATMAP_THRESHOLDS.extremeRatio
        const isHigh = count >= maxCount * HOURLY_HEATMAP_THRESHOLDS.highRatio
        const riskLevel = count === 0 ? labels.riskSafe : isExtreme ? labels.riskExtreme : isHigh ? labels.riskHigh : labels.riskNormal
        const riskColor =
          count === 0
            ? DASHBOARD_CHART_THEME.heatmapLevelColors.safe
            : isExtreme
              ? DASHBOARD_CHART_THEME.heatmapLevelColors.extreme
              : isHigh
                ? DASHBOARD_CHART_THEME.heatmapLevelColors.high
                : DASHBOARD_CHART_THEME.heatmapLevelColors.normal

        return `
          <div style="font-size:12px; line-height:1.6;">
            <div style="font-weight:600; color:#343b51; margin-bottom:2px;">${timeRange}</div>
            <div>${labels.tooltipFreq}<b style="color:${count > 0 ? '#645383' : '#888'}; font-size:13px;">${count}</b> ${labels.unitCount}</div>
            <div style="font-size:11px; margin-top:2px;">${labels.tooltipRisk}<span style="color:${riskColor}; font-weight:600;">${riskLevel}</span></div>
          </div>
        `
      },
    },
    grid: { top: 12, bottom: 56, left: 14, right: 14 },
    xAxis: {
      type: 'category',
      data: Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: DASHBOARD_CHART_THEME.axisLabelColor, fontSize: 10, interval: 2 },
      splitArea: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'category',
      data: [''],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    visualMap: {
      min: 0,
      max: maxCount,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      itemWidth: 12,
      itemHeight: 140,
      inRange: {
        color: [...DASHBOARD_CHART_THEME.heatmapPalette],
      },
      text: [labels.legendHighRisk, labels.legendNoViolation],
      textGap: 8,
      textStyle: { color: '#959caa', fontSize: 10 },
    },
    series: [
      {
        type: 'heatmap',
        data: hourlyData.map((h) => [h.hour, 0, h.count]),
        label: { show: false },
        itemStyle: {
          borderColor: '#ffffff',
          borderWidth: 2,
          borderRadius: 4,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 8,
            shadowColor: 'rgba(99, 69, 183, 0.35)',
            borderColor: '#ffffff',
            borderWidth: 2,
          },
        },
      },
    ],
  }
}

export function buildDailyBarOption(params: {
  heatmap: RiskHeatmapData | null
  labels: Pick<ChartI18nLabels, 'tooltipFreq' | 'unitCount'>
  animation: boolean
  referenceDate?: Date
}) {
  const { heatmap, labels, animation, referenceDate = new Date() } = params
  const lookbackDays = heatmap?.lookback_days ?? 7

  return {
    animation,
    tooltip: {
      trigger: 'axis',
      backgroundColor: DASHBOARD_CHART_THEME.tooltipBg,
      borderColor: DASHBOARD_CHART_THEME.tooltipBorder,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: DASHBOARD_CHART_THEME.tooltipText, fontSize: 12 },
      formatter: (rawParams: unknown) => {
        const item = Array.isArray(rawParams) ? rawParams[0] : rawParams
        const typed = item as { name?: string; value?: unknown } | undefined
        const count = Number(typed?.value ?? 0)
        return `
          <div style="font-size:12px; line-height:1.6;">
            <div style="font-weight:600; color:#343b51; margin-bottom:2px;">${typed?.name ?? ''}</div>
            <div>${labels.tooltipFreq}<b style="color:${count > 0 ? '#645383' : '#888'}; font-size:13px;">${count}</b> ${labels.unitCount}</div>
          </div>
        `
      },
    },
    grid: { top: 18, bottom: 26, left: 36, right: 14 },
    xAxis: {
      type: 'category',
      data: Array.from({ length: lookbackDays }, (_, i) => {
        const d = new Date(referenceDate)
        d.setDate(d.getDate() - lookbackDays + i + 1)
        return `${d.getMonth() + 1}/${d.getDate()}`
      }),
      axisLine: { lineStyle: { color: '#eeebf5' } },
      axisTick: { show: false },
      axisLabel: { color: DASHBOARD_CHART_THEME.axisLabelColor, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#f0edf6', type: 'dashed' } },
      axisLabel: { color: DASHBOARD_CHART_THEME.axisLabelColor, fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: heatmap?.daily_counts ?? [],
        itemStyle: { color: DASHBOARD_CHART_THEME.dailyBarColor, borderRadius: [4, 4, 0, 0] },
        emphasis: { itemStyle: { color: DASHBOARD_CHART_THEME.dailyBarHoverColor } },
        barWidth: '42%',
      },
    ],
  }
}

export function useDashboardCharts(params: {
  stats: Ref<ViolationStatistics | null>
  heatmap: Ref<RiskHeatmapData | null>
  violationLabels: Ref<Record<ViolationType, string>>
  severityKeys: ReadonlyArray<ViolationSeverity>
  severityLabel: (severity: ViolationSeverity) => string
  t: (key: string, params?: Record<string, string | number>) => string
  animation: boolean
}) {
  const labels = computed<ChartI18nLabels>(() => ({
    chartTodayEvents: params.t('dashboard.chartTodayEvents'),
    chartUnitSuffix: (value: number) => params.t('dashboard.chartUnitSuffix', { value }),
    riskSafe: params.t('dashboard.riskSafe'),
    riskExtreme: params.t('dashboard.riskExtreme'),
    riskHigh: params.t('dashboard.riskHigh'),
    riskNormal: params.t('dashboard.riskNormal'),
    tooltipFreq: params.t('dashboard.tooltipFreq'),
    tooltipRisk: params.t('dashboard.tooltipRisk'),
    unitCount: params.t('common.unitCount'),
    legendHighRisk: params.t('dashboard.legendHighRisk'),
    legendNoViolation: params.t('dashboard.legendNoViolation'),
  }))

  const typePieOption = computed(() =>
    buildTypePieOption({
      stats: params.stats.value,
      violationLabels: params.violationLabels.value,
      labels: labels.value,
      animation: params.animation,
    }),
  )

  const severityBarOption = computed(() =>
    buildSeverityBarOption({
      stats: params.stats.value,
      severityKeys: params.severityKeys,
      severityLabel: params.severityLabel,
      chartUnitSuffix: labels.value.chartUnitSuffix,
      animation: params.animation,
    }),
  )

  const heatmapChartOption = computed(() =>
    buildHeatmapChartOption({
      heatmap: params.heatmap.value,
      labels: labels.value,
      animation: params.animation,
    }),
  )

  const dailyBarOption = computed(() =>
    buildDailyBarOption({
      heatmap: params.heatmap.value,
      labels: labels.value,
      animation: params.animation,
    }),
  )

  return {
    typePieOption,
    severityBarOption,
    heatmapChartOption,
    dailyBarOption,
  }
}
