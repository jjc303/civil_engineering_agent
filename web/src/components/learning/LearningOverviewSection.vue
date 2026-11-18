<template>
  <section class="overview-panel" :aria-label="t('learning.overviewAria')">
    <div class="overview-heading">
      <div>
        <span class="section-kicker">{{ t('learning.overviewKicker') }}</span>
        <h2>{{ weekLabel }}</h2>
      </div>
      <span class="overview-source">{{ t('learning.overviewSource') }}</span>
    </div>

    <div class="metric-grid">
      <div class="metric">
        <span>{{ t('learning.metricViolations') }}</span>
        <strong>{{ overview?.total_events ?? '—' }}</strong>
        <small>{{ t('learning.metricViolationsHint') }}</small>
      </div>
      <div class="metric critical">
        <span>{{ t('learning.metricHighRisk') }}</span>
        <strong>{{ overview?.high_risk_events ?? '—' }}</strong>
        <small>{{ t('learning.metricHighRiskHint') }}</small>
      </div>
      <div class="metric">
        <span>{{ t('learning.metricTrainings') }}</span>
        <strong>{{ overview?.training_count ?? '—' }}</strong>
        <small>{{ t('learning.metricTrainingsHint') }}</small>
      </div>
      <div class="metric progress">
        <span>{{ t('learning.metricCompletion') }}</span>
        <strong>{{ overview ? `${Math.min(100, overview.completion_rate)}%` : '—' }}</strong>
        <small>
          {{
            overview
              ? t('learning.metricCompletionHint', { completed: overview.completed_count, target: overview.target_count })
              : t('learning.metricCompletionFallback')
          }}
        </small>
        <small v-if="overview?.excess_completed_count">
          {{ t('learning.excessCompleted', { count: overview.excess_completed_count }) }}
        </small>
      </div>
    </div>

    <div class="overview-footer">
      <div class="risk-line">
        <span>{{ t('learning.mainRisks') }}</span>
        <template v-if="overview?.main_risks.length">
          <span v-for="risk in overview.main_risks" :key="risk.code" class="risk-chip">
            {{ risk.label }} <b>{{ risk.count }}</b>
          </span>
        </template>
        <span v-else class="muted">{{ t('learning.noWeeklyEvents') }}</span>
      </div>
      <div class="hero-actions">
        <el-button plain @click="$emit('openCustomReport')">{{ t('learning.customReportPeriod') }}</el-button>
        <el-button type="primary" :loading="busy" @click="$emit('createWeeklyReport')">{{ t('learning.generateWeeklyReport') }}</el-button>
        <el-button color="#6959d5" plain @click="$emit('openTrainingComposer')">{{ t('learning.generateTrainingPlan') }}</el-button>
      </div>
    </div>

    <p v-if="error" class="inline-error">
      {{ t('learning.overviewError') }}
      <button @click="$emit('retry')">{{ t('learning.retry') }}</button>
    </p>
  </section>
</template>

<script setup lang="ts">
import type { WeeklyOverview } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

defineProps<{
  overview: WeeklyOverview | null
  weekLabel: string
  busy: boolean
  error: boolean
}>()

defineEmits<{
  openCustomReport: []
  createWeeklyReport: []
  openTrainingComposer: []
  retry: []
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.section-kicker { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.overview-panel { background: linear-gradient(115deg, #fff 15%, #f6f4ff 100%); border: 1px solid #e6e4f7; border-radius: 22px; padding: 26px 30px; box-shadow: 0 10px 35px #4b3b9b0b; }
.overview-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.overview-heading h2 { margin: 5px 0 0; font-size: 21px; letter-spacing: -.02em; }
.overview-source, .muted { color: #919aab; font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 26px; border: 1px solid #eceaf7; background: #fff; border-radius: 16px; overflow: hidden; }
.metric { display: flex; flex-direction: column; gap: 5px; padding: 19px 22px; border-right: 1px solid #f0eef8; }
.metric:last-child { border-right: 0; }
.metric span { color: #8791a1; font-size: 12px; }
.metric strong { font-size: 31px; line-height: 1.25; color: #3d425d; font-weight: 700; }
.metric.critical strong { color: #d16968; }
.metric.progress strong { color: #6657c9; }
.metric small { color: #a1a8b4; font-size: 11px; }
.overview-footer { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-top: 23px; flex-wrap: wrap; }
.risk-line, .hero-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.risk-line > span:first-child { font-size: 12px; font-weight: 700; margin-right: 4px; color: #5a6478; }
.risk-chip { background: #eceafb; color: #6555ba; border-radius: 16px; padding: 7px 10px; font-size: 11px; }
.risk-chip b { margin-left: 4px; }
.inline-error { font-size: 12px; color: #c16b5c; margin: 16px 0 0; }
.inline-error button { border: 0; background: none; color: inherit; text-decoration: underline; cursor: pointer; }

@media (max-width: 1080px) { .overview-footer { align-items: flex-start; } }
@media (max-width: 760px) {
  .overview-panel { padding: 18px; border-radius: 16px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric:nth-child(2) { border-right: 0; }
  .metric:nth-child(-n + 2) { border-bottom: 1px solid #f0eef8; }
  .metric { padding: 15px; }
  .metric strong { font-size: 25px; }
  .hero-actions { width: 100%; }
  .hero-actions .el-button { margin: 0; }
  .overview-source { display: none; }
}
</style>
