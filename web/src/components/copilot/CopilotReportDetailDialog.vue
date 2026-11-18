<template>
  <el-dialog v-model="open" :title="t('copilot.reportDetailTitle')" width="800px" destroy-on-close>
    <div v-loading="loading">
      <template v-if="report">
        <div class="report-detail-head">
          <strong>{{ reportDate(report.period_start_utc) }} — {{ reportDate(report.period_end_utc, true) }}</strong>
          <el-tag :type="report.status === 'CONFIRMED' ? 'success' : 'warning'">
            {{ report.status === 'CONFIRMED' ? t('enums.reportStatus.CONFIRMED') : t('enums.reportStatus.DRAFT') }}
          </el-tag>
        </div>
        <p>{{ t('copilot.validViolationsMeta', { total: report.statistics.total, repeat: report.statistics.repeat_occurrences }) }}</p>
        <h4>{{ t('copilot.reportSummary') }}</h4>
        <p class="report-detail-text">{{ report.content.summary }}</p>
        <h4>{{ t('copilot.reportRiskAnalysis') }}</h4>
        <p class="report-detail-text">{{ report.content.risk_analysis }}</p>
        <h4>{{ t('copilot.reportRemediation') }}</h4>
        <p class="report-detail-text">{{ report.content.remediation }}</p>
        <template v-if="report.citations.length">
          <h4>{{ t('copilot.citationsTitle') }}</h4>
          <p v-for="citation in report.citations" :key="citation.chunk_id" class="report-citation">
            {{ citation.title }} · {{ citation.page_or_section }}
          </p>
        </template>
      </template>
    </div>
    <template #footer>
      <el-button @click="open = false">{{ t('common.close') }}</el-button>
      <el-button v-if="report?.pdf_url" type="primary" @click="$emit('previewPdf', report.report_id)">
        {{ t('copilot.previewPdf') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getReport, type Report } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'
import { getLearningTimezone, utcDate } from '@/utils/datetime'

const props = defineProps<{
  modelValue: boolean
  reportId: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  previewPdf: [reportId: string]
}>()

const { t, formatDate } = useAppI18n()
const loading = ref(false)
const report = ref<Report | null>(null)

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

function reportDate(value: string, exclusiveEnd = false): string {
  const date = new Date(utcDate(value).getTime() - (exclusiveEnd ? 1 : 0))
  return formatDate(date, { timeZone: getLearningTimezone(), year: 'numeric', month: '2-digit', day: '2-digit' })
}

watch(
  () => [props.modelValue, props.reportId] as const,
  async ([visible, reportId]) => {
    if (!visible || !reportId) return
    loading.value = true
    report.value = null
    try {
      const loaded = await getReport(reportId)
      if (props.modelValue && props.reportId === reportId) {
        report.value = loaded
      }
    } catch {
      ElMessage.error(t('copilot.reportDetailLoadFailed'))
    } finally {
      loading.value = false
    }
  },
)
</script>

<style scoped>
.report-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-detail-head strong { font-size: 14px; color: #303b51; }
.report-detail-text { line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.report-citation { font-size: 12px; color: #718096; border-left: 2px solid #aea6df; padding-left: 9px; }
</style>
