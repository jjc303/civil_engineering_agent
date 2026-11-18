<template>
  <el-dialog v-model="open" :title="t('learning.trainingBuilderTitle')" width="740px">
    <p class="hint">{{ t('learning.trainingBuilderHint') }}</p>
    <p v-if="!confirmedReports.length" class="inline-error">{{ t('learning.needConfirmedReport') }}</p>

    <el-form label-position="top">
      <el-form-item :label="t('learning.taskName')">
        <el-input v-model="form.title" :placeholder="t('learning.taskNamePlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('learning.currentReport')">
        <el-select v-model="form.report_id" :placeholder="t('learning.selectConfirmedReport')" style="width: 100%">
          <el-option
            v-for="report in confirmedReports"
            :key="report.report_id"
            :label="`${reportDay(report.period_start_utc)} — ${reportDay(report.period_end_utc, true)}`"
            :value="report.report_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('learning.casesAndStandards')">
        <el-select
          v-model="form.document_ids"
          multiple
          filterable
          remote
          :remote-method="(q: string) => $emit('searchDocs', q)"
          :placeholder="t('learning.selectDocsPlaceholder')"
          style="width: 100%"
        >
          <el-option
            v-for="doc in allDocuments"
            :key="doc.document_id"
            :label="`${doc.document_type === 'STANDARD' ? t('enums.documentType.STANDARD_SHORT') : t('enums.documentType.ACCIDENT_CASE_SHORT')} · ${doc.title}`"
            :value="doc.document_id"
          />
        </el-select>
      </el-form-item>
      <div class="form-row">
        <el-form-item :label="t('copilot.targetCount')"><el-input-number v-model="form.target_count" :min="1" /></el-form-item>
        <el-form-item :label="t('copilot.questionCount')"><el-input-number v-model="form.question_count" :min="1" :max="20" /></el-form-item>
        <el-form-item :label="t('copilot.passScore')"><el-input-number v-model="form.pass_score" :min="0" :max="100" /></el-form-item>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="open = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="busy" @click="submit">{{ t('learning.generateTrainingDraft') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { KnowledgeDocument, Report } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

export interface TrainingBuilderFormState {
  report_id: string
  title: string
  document_ids: string[]
  target_count: number
  question_count: number
  pass_score: number
}

const props = defineProps<{
  modelValue: boolean
  form: TrainingBuilderFormState
  confirmedReports: Report[]
  allDocuments: KnowledgeDocument[]
  busy: boolean
  reportDay: (value: string, exclusiveEnd?: boolean) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  searchDocs: [query: string]
  submit: []
}>()

const { t } = useAppI18n()

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

function submit() {
  if (!props.form.report_id || !props.form.title) {
    ElMessage.warning(t('learning.makeTrainingValidation'))
    return
  }
  emit('submit')
}
</script>

<style scoped>
.hint { color: #919aab; font-size: 12px; }
.inline-error { font-size: 12px; color: #c16b5c; margin: 16px 0 0; }
.form-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
</style>
