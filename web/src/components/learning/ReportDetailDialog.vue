<template>
  <el-dialog v-model="open" :title="t('learning.safetyReportDialogTitle')" width="880px" destroy-on-close>
    <template v-if="report">
      <div class="dialog-meta">
        <strong>{{ reportDay(report.period_start_utc) }} — {{ reportDay(report.period_end_utc, true) }}</strong>
        <el-tag :type="report.status === 'CONFIRMED' ? 'success' : 'warning'">
          {{ report.status === 'CONFIRMED' ? t('enums.reportStatus.CONFIRMED') : t('enums.reportStatus.DRAFT') }}
        </el-tag>
      </div>
      <div class="dialog-metrics">
        <span>{{ t('learning.reportMetricsEvents', { count: report.statistics.total }) }}</span>
        <span>{{ t('learning.reportMetricsRepeat', { count: report.statistics.repeat_occurrences }) }}</span>
      </div>
      <p>{{ t('learning.riskTypesLine', { pairs: pairs(report.statistics.by_type) }) }}</p>
      <p>{{ t('learning.zonesLine', { pairs: pairs(report.statistics.by_zone) }) }}</p>

      <el-form label-position="top">
        <el-form-item :label="t('copilot.reportSummary')">
          <el-input v-model="report.content.summary" type="textarea" :rows="4" :disabled="report.status !== 'DRAFT'" />
        </el-form-item>
        <el-form-item :label="t('copilot.reportRiskAnalysis')">
          <el-input v-model="report.content.risk_analysis" type="textarea" :rows="4" :disabled="report.status !== 'DRAFT'" />
        </el-form-item>
        <el-form-item :label="t('copilot.reportRemediation')">
          <el-input v-model="report.content.remediation" type="textarea" :rows="4" :disabled="report.status !== 'DRAFT'" />
        </el-form-item>
      </el-form>

      <h4>{{ t('copilot.citationsTitle') }}</h4>
      <p v-if="!report.citations.length" class="hint">{{ t('learning.noCitationsHint') }}</p>
      <p v-for="citation in report.citations" :key="citation.chunk_id" class="citation">
        {{ citation.title }} · {{ citation.page_or_section }}
      </p>

      <div class="dialog-actions">
        <template v-if="report.status === 'DRAFT'">
          <el-button :loading="busy" @click="$emit('save', report)">{{ t('learning.saveDraft') }}</el-button>
          <el-button type="primary" :loading="busy" @click="$emit('confirm', report)">{{ t('learning.confirmAndPdf') }}</el-button>
        </template>
        <el-button v-if="report.pdf_url" @click="$emit('downloadPdf', report.report_id)">{{ t('copilot.downloadPdf') }}</el-button>
        <el-button type="danger" plain :disabled="busy" @click="$emit('delete', report)">
          {{ t('learning.deleteItem', { kind: report.status === 'DRAFT' ? t('learning.reportDraftKind') : t('learning.reportConfirmedKind') }) }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Report } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

const props = defineProps<{
  modelValue: boolean
  report: Report | null
  busy: boolean
  reportDay: (value: string, exclusiveEnd?: boolean) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: [report: Report]
  confirm: [report: Report]
  downloadPdf: [reportId: string]
  delete: [report: Report]
}>()

const { t } = useAppI18n()

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const pairs = (value: Record<string, number>) =>
  Object.entries(value)
    .map(([key, count]) => `${key} ${count}`)
    .join('；') || t('common.none')
</script>

<style scoped>
.hint { color: #919aab; font-size: 12px; }
.dialog-meta, .dialog-actions, .dialog-metrics { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.dialog-meta { justify-content: space-between; margin-bottom: 16px; }
.dialog-actions { justify-content: flex-end; margin-top: 20px; }
.dialog-metrics span { padding: 7px 12px; border-radius: 9px; background: #eef0ff; color: #6258ac; font-size: 12px; }
.citation { padding-left: 10px; border-left: 2px solid #aa9fe6; color: #788398; font-size: 12px; }
</style>
