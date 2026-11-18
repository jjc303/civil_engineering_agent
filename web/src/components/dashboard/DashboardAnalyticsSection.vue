<template>
  <section class="statistics-panel visible-statistics" :aria-label="t('dashboard.todayStatsTitle')">
    <div class="section-heading">
      <div>
        <h2>{{ t('dashboard.todayStatsTitle') }}</h2>
        <p>{{ t('dashboard.todayStatsDesc', { day: dayLabel }) }}</p>
      </div>
      <router-link class="statistics-link" to="/violations">{{ t('dashboard.viewEventDetails') }}</router-link>
    </div>
    <p v-if="statsError" class="statistics-warning" role="status">
      {{ t('dashboard.statsWarning', { detail: stats ? t('dashboard.statsWarningKeep') : t('dashboard.statsWarningRetry') }) }}
    </p>
    <div v-if="stats" class="charts-grid">
      <div class="chart">
        <h3>{{ t('dashboard.typeDistTitle') }} <span>{{ t('dashboard.totalCountLabel', { count: stats.total_violations }) }}</span></h3>
        <v-chart :option="typePieOption" autoresize :aria-label="t('dashboard.typeDistTitle')" />
        <p v-if="stats.total_violations === 0" class="zero-chart-note">{{ t('dashboard.zeroChartNote') }}</p>
        <ul class="chart-values" :aria-label="t('dashboard.typeDistTitle')">
          <li v-for="(label, type) in violationLabels" :key="type">
            <span>{{ label }}</span>
            <b>{{ stats.by_type[type] ?? 0 }}</b>
          </li>
        </ul>
      </div>
      <div class="chart">
        <h3>{{ t('dashboard.severityDistTitle') }} <span>{{ t('dashboard.severityUnit') }}</span></h3>
        <v-chart :option="severityBarOption" autoresize :aria-label="t('dashboard.severityDistTitle')" />
        <ul class="chart-values" :aria-label="t('dashboard.severityDistTitle')">
          <li v-for="severity in severityKeys" :key="severity">
            <span>{{ severityLabel(severity) }}</span>
            <b>{{ stats.by_severity[severity] ?? 0 }}</b>
          </li>
        </ul>
      </div>
    </div>
    <div v-else class="chart-empty">
      {{ loading ? t('dashboard.loadingCharts') : t('dashboard.chartsEmpty') }}
      <button v-if="!loading" class="clear-filter" @click="$emit('refresh')">{{ t('dashboard.reloadPlain') }}</button>
    </div>
    <p class="statistics-updated">{{ t('dashboard.chartsUpdated', { source: statsSourceTime }) }}</p>
  </section>

  <section v-if="heatmap" class="risk-heatmap-section" :aria-label="t('dashboard.heatmapAria')">
    <div class="section-heading">
      <div>
        <h2>{{ t('dashboard.heatmapTitle') }}</h2>
        <p>{{ t('dashboard.heatmapDesc', { days: heatmap.lookback_days }) }}</p>
      </div>
      <span class="heatmap-summary">{{ heatmap.summary }}</span>
    </div>
    <div class="heatmap-grid">
      <div class="chart heatmap-chart">
        <h3>{{ t('dashboard.hourlyTitle') }} <span>{{ t('dashboard.hourlyDesc') }}</span></h3>
        <v-chart :option="heatmapChartOption" autoresize :aria-label="t('dashboard.hourlyTitle')" />
      </div>
      <div class="chart daily-chart">
        <h3>{{ t('dashboard.dailyTitle') }} <span>{{ t('dashboard.dailyDesc', { days: heatmap.lookback_days }) }}</span></h3>
        <v-chart :option="dailyBarOption" autoresize :aria-label="t('dashboard.dailyTitle')" />
      </div>
    </div>
    <div v-if="heatmap.zone_risks.length" class="zone-risk-list">
      <h3>{{ t('dashboard.zoneRiskRanking') }}</h3>
      <div class="zone-risk-items">
        <div v-for="(zone, i) in heatmap.zone_risks.slice(0, 5)" :key="i" class="zone-risk-item">
          <span class="zone-rank">{{ i + 1 }}</span>
          <div class="zone-info">
            <strong>{{ zone.zone_name }}</strong>
            <small>{{ zone.camera_id }}</small>
          </div>
          <div class="zone-count">
            <b>{{ zone.total }}</b>
            <span>{{ t('common.unitCount') }}</span>
          </div>
          <div class="risk-bar">
            <div
              class="risk-fill"
              :style="{ width: `${zone.risk_score * 100}%`, background: resolveRiskBarColor(zone.risk_score) }"
            />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { toRef } from 'vue'
import type { RiskHeatmapData } from '@/api/violations'
import { resolveRiskBarColor, useDashboardCharts } from '@/composables/useDashboardCharts'
import { useAppI18n } from '@/i18n/useAppI18n'
import type { ViolationSeverity, ViolationStatistics, ViolationType } from '@/types/contract'

const props = defineProps<{
  stats: ViolationStatistics | null
  heatmap: RiskHeatmapData | null
  violationLabels: Record<ViolationType, string>
  severityKeys: ReadonlyArray<ViolationSeverity>
  severityLabel: (severity: ViolationSeverity) => string
  dayLabel: string
  statsError: boolean
  loading: boolean
  statsSourceTime: string
  chartAnimation: boolean
}>()

defineEmits<{
  refresh: []
}>()

const { t } = useAppI18n()

const { typePieOption, severityBarOption, heatmapChartOption, dailyBarOption } = useDashboardCharts({
  stats: toRef(props, 'stats'),
  heatmap: toRef(props, 'heatmap'),
  violationLabels: toRef(props, 'violationLabels'),
  severityKeys: props.severityKeys,
  severityLabel: props.severityLabel,
  t,
  animation: props.chartAnimation,
})
</script>

<style scoped>
.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-heading h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #4a526b;
}

.section-heading p {
  font-size: 11px;
  line-height: 1.7;
  color: #737b8d;
  margin: 7px 0 0;
}

.statistics-panel {
  background: #fff;
  border: 1px solid #ece9f4;
  border-radius: 20px;
  padding: 24px;
  margin-top: 24px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.chart {
  border: 1px solid #efebf6;
  background: #fcfbfe;
  padding: 20px;
  border-radius: 14px;
  min-width: 0;
  position: relative;
}

.chart h3 {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
  font-weight: 500;
  color: #6e687f;
  margin: 0;
}

.chart h3 span {
  font-size: 11px;
  font-weight: 400;
  color: #8d869b;
}

.chart .echarts {
  height: 220px;
}

.chart-empty {
  padding: 25px;
  font-size: 12px;
  color: #a0a5b2;
  background: #f8f8fc;
  border-radius: 5px;
  text-align: center;
  margin-bottom: 24px;
}

.clear-filter {
  background: transparent;
  border: 0;
  border-radius: 18px;
  color: #9386ac;
  padding: 4px 9px;
  font-size: 11px;
}

.clear-filter:hover {
  background: #f5f1fa;
}

.statistics-link {
  font-size: 12px;
  color: #8978bd;
  text-decoration: none;
  border-radius: 20px;
  background: #f3effb;
  padding: 9px 14px;
}

.statistics-link:hover {
  background: #eae3f9;
}

.chart-values {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 14px 0 0;
  margin: 0;
  list-style: none;
  border-top: 1px solid #eeebf5;
}

.chart-values li {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #878093;
  font-size: 11px;
}

.chart-values b {
  font-size: 17px;
  color: #716282;
  font-weight: 500;
}

.statistics-updated {
  color: #97909f;
  font-size: 11px;
  margin: 0;
}

.zero-chart-note {
  font-size: 11px;
  color: #968b9e;
  text-align: center;
  margin: -10px 0 14px;
}

.statistics-warning {
  font-size: 12px;
  color: #b77964;
  background: #fff2ec;
  padding: 10px 14px;
  border-radius: 10px;
}

.risk-heatmap-section {
  margin-top: 24px;
  border: 1px solid #ece9f4;
  border-radius: 20px;
  padding: 24px;
  background: #fff;
}

.risk-heatmap-section > .section-heading {
  flex-wrap: wrap;
}

.heatmap-summary {
  font-size: 12px;
  color: #7e6ba8;
  background: #f5f0fc;
  border: 1px solid #e8def6;
  padding: 8px 14px;
  border-radius: 10px;
  max-width: 560px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.heatmap-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 22px;
}

.heatmap-grid .chart {
  display: flex;
  flex-direction: column;
}

.heatmap-grid .chart h3 {
  align-items: center;
  margin-bottom: 10px;
}

.heatmap-grid .chart .echarts {
  height: 180px;
  width: 100%;
}

.zone-risk-list h3 {
  font-size: 13px;
  font-weight: 500;
  color: #6e687f;
  margin: 0 0 16px;
}

.zone-risk-items {
  display: grid;
  gap: 10px;
}

.zone-risk-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #fcfbfe;
  border: 1px solid #efebf6;
}

.zone-rank {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #ede5fa;
  color: #7b63b9;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.zone-info {
  flex: 1;
  min-width: 0;
}

.zone-info strong {
  display: block;
  font-size: 13px;
  color: #504963;
}

.zone-info small {
  font-size: 10px;
  color: #9b93ab;
}

.zone-count b {
  font-size: 16px;
  color: #695bb4;
  font-weight: 600;
}

.zone-count span {
  font-size: 10px;
  color: #a29ab5;
  margin-left: 3px;
}

.risk-bar {
  width: 90px;
  height: 6px;
  background: #eae5f2;
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
}

.risk-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s;
}

@media (max-width: 760px) {
  .heatmap-grid {
    grid-template-columns: 1fr;
  }

  .risk-bar {
    width: 60px;
  }

  .heatmap-summary {
    max-width: 100%;
    white-space: normal;
  }
}

@media (max-width: 620px) {
  .statistics-panel {
    padding: 18px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }

  .chart {
    padding: 14px;
  }

  .chart .echarts {
    height: 200px;
  }

  .chart-values {
    gap: 8px;
  }

  .chart-values li {
    font-size: 10px;
  }
}
</style>
