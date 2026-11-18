<template>
  <section class="history-section">
    <div class="section-head">
      <div>
        <span class="section-kicker">{{ t('learning.historyKicker') }}</span>
        <h2>{{ t('learning.historyTitle') }}</h2>
      </div>
    </div>

    <div class="history-grid">
      <div class="surface history-list">
        <h3>{{ t('learning.safetyReports') }} <small>{{ reports.length }}</small></h3>
        <div v-if="reports.length">
          <div v-for="report in reports.slice(0, showAllReports ? undefined : 8)" :key="report.report_id" class="history-row">
            <div>
              <strong>{{ reportDay(report.period_start_utc) }} — {{ reportDay(report.period_end_utc, true) }}</strong>
              <small>
                {{
                  t('learning.reportStatsLine', {
                    status: report.status === 'CONFIRMED' ? t('enums.reportStatus.CONFIRMED') : t('enums.reportStatus.DRAFT'),
                    total: report.statistics.total,
                  })
                }}
              </small>
            </div>
            <div>
              <el-button link @click="$emit('showReport', report)">{{ t('learning.view') }}</el-button>
              <el-button v-if="report.pdf_url" link type="primary" @click="$emit('downloadPdf', report.report_id)">
                {{ t('copilot.downloadPdf') }}
              </el-button>
            </div>
          </div>
          <el-button v-if="reports.length > 8" link @click="showAllReports = !showAllReports">
            {{ showAllReports ? t('learning.collapse') : t('learning.viewAllReports', { count: reports.length }) }}
          </el-button>
        </div>
        <p v-else class="muted">{{ t('learning.noHistoryReports') }}</p>
      </div>

      <div class="surface history-list">
        <h3>{{ t('learning.trainingRecords') }} <small>{{ trainings.length }}</small></h3>
        <div v-if="trainings.length">
          <div v-for="task in trainings.slice(0, showAllTraining ? undefined : 8)" :key="task.task_id" class="history-row">
            <div>
              <strong>{{ task.title }}</strong>
              <small>
                {{
                  t('learning.trainingRecordLine', {
                    status: task.status === 'PUBLISHED' ? t('enums.trainingStatus.PUBLISHED') : t('enums.trainingStatus.DRAFT'),
                    target: task.target_count,
                  })
                }}
              </small>
            </div>
            <el-button link @click="$emit('showTraining', task)">{{ t('learning.view') }}</el-button>
          </div>
          <el-button v-if="trainings.length > 8" link @click="showAllTraining = !showAllTraining">
            {{ showAllTraining ? t('learning.collapse') : t('learning.viewAllTrainings', { count: trainings.length }) }}
          </el-button>
        </div>
        <p v-else class="muted">{{ t('learning.noHistoryTrainings') }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Report, Training } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

defineProps<{
  reports: Report[]
  trainings: Training[]
  reportDay: (value: string, exclusiveEnd?: boolean) => string
}>()

defineEmits<{
  showReport: [report: Report]
  downloadPdf: [reportId: string]
  showTraining: [task: Training]
}>()

const { t } = useAppI18n()
const showAllReports = ref(false)
const showAllTraining = ref(false)
</script>

<style scoped>
.history-section { margin-top: 28px; }
.section-kicker { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 15px; }
.section-head h2 { margin: 5px 0 0; font-size: 21px; letter-spacing: -.02em; }
.history-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.surface { border: 1px solid #eceef5; border-radius: 20px; background: #fff; box-shadow: 0 5px 20px #37406607; padding: 24px; }
.history-list h3 { font-size: 15px; margin: 0 0 12px; }
.history-list h3 small { color: #a0a8b6; font-weight: 400; }
.history-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 0; border-top: 1px solid #f0f1f6; }
.history-row > div:first-child { display: grid; gap: 4px; min-width: 0; }
.history-row strong { font-size: 12px; line-height: 1.5; }
.history-row small { font-size: 11px; color: #99a2ae; }
.history-row > div:last-child { display: flex; white-space: nowrap; }
.muted { color: #919aab; font-size: 12px; }

@media (max-width: 760px) {
  .history-grid { grid-template-columns: 1fr; }
  .surface { padding: 18px; border-radius: 16px; }
}
</style>
