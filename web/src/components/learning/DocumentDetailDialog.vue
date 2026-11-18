<template>
  <el-dialog v-model="open" :title="document?.title || t('learning.docDetailFallback')" width="880px" destroy-on-close>
    <template v-if="document">
      <div class="dialog-meta">
        <span>
          {{ document.document_type === 'STANDARD' ? t('enums.documentType.STANDARD_MATERIAL') : t('enums.documentType.ACCIDENT_CASE') }}
          · {{ document.document_date ? formatDay(document.document_date) : t('learning.undated') }}
        </span>
        <el-button type="danger" link @click="$emit('retire', document)">{{ t('learning.retireDoc') }}</el-button>
      </div>

      <el-form label-position="top">
        <el-form-item :label="t('learning.docDateLabel')">
          <el-date-picker v-model="editForm.document_date" type="date" value-format="YYYY-MM-DD" clearable />
        </el-form-item>
        <el-form-item :label="t('learning.riskTagsComma')"><el-input v-model="editForm.risk_tags" /></el-form-item>
        <el-form-item :label="t('learning.sourceField')"><el-input v-model="editForm.source_label" /></el-form-item>
        <el-form-item :label="t('learning.aiSummaryEditable')">
          <el-input v-model="editForm.summary" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item v-if="document.document_type === 'STANDARD'" :label="t('learning.standardValidity')">
          <el-select v-model="editForm.validity_status">
            <el-option :label="t('enums.validityStatus.CURRENT')" value="CURRENT" />
            <el-option :label="t('enums.validityStatus.SUPERSEDED')" value="SUPERSEDED" />
            <el-option :label="t('enums.validityStatus.UNKNOWN')" value="UNKNOWN" />
          </el-select>
        </el-form-item>
        <div class="dialog-actions">
          <el-button @click="submitSave">{{ t('learning.saveMetadata') }}</el-button>
          <el-button :loading="busy" @click="$emit('regenerateSummary', document)">{{ t('learning.aiGenerateSummary') }}</el-button>
          <el-button v-if="document.document_type === 'ACCIDENT_REPORT'" @click="$emit('addToTraining', document)">
            {{ t('learning.addToTrainingBtn') }}
          </el-button>
        </div>
      </el-form>

      <template v-if="document.document_type === 'ACCIDENT_REPORT'">
        <el-divider />
        <el-button :loading="busy" @click="$emit('generateCase', document)">{{ t('learning.generateCaseAnalysis') }}</el-button>
        <div v-if="caseDetail" class="case-detail">
          <h4>{{ t('learning.caseProcess') }}</h4><p>{{ caseDetail.process }}</p>
          <h4>{{ t('learning.caseCauses') }}</h4><p>{{ caseDetail.causes }}</p>
          <h4>{{ t('learning.caseRisks') }}</h4><p>{{ caseDetail.risks }}</p>
          <h4>{{ t('learning.casePrevention') }}</h4><p>{{ caseDetail.prevention }}</p>
          <h4>{{ t('learning.caseCitations') }}</h4>
          <p v-for="item in caseDetail.citations" :key="item.chunk_id" class="citation">
            {{ item.title }} · {{ item.page_or_section }}
          </p>
        </div>
      </template>

      <template v-else>
        <el-divider />
        <h4>{{ t('learning.standardFragments') }}</h4>
        <el-button v-if="!fragments.length" @click="$emit('loadFragments', document)">
          {{ t('learning.viewOriginalFragments') }}
        </el-button>
        <div v-for="fragment in fragments" :key="fragment.citation.chunk_id" class="fragment">
          <strong>{{ fragment.citation.page_or_section }}</strong>
          <p>{{ fragment.content }}</p>
        </div>
      </template>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { CaseDetail, Citation, KnowledgeDocument } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

export interface DocumentEditPayload {
  document_date: string
  risk_tags: string
  source_label: string
  summary: string
  validity_status: string
}

const props = defineProps<{
  modelValue: boolean
  document: KnowledgeDocument | null
  caseDetail: CaseDetail | null
  fragments: Array<{ content: string; citation: Citation }>
  busy: boolean
  formatDay: (value: string) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: [doc: KnowledgeDocument, form: DocumentEditPayload]
  regenerateSummary: [doc: KnowledgeDocument]
  addToTraining: [doc: KnowledgeDocument]
  generateCase: [doc: KnowledgeDocument]
  loadFragments: [doc: KnowledgeDocument]
  retire: [doc: KnowledgeDocument]
}>()

const { t } = useAppI18n()
const editForm = reactive<DocumentEditPayload>({
  document_date: '',
  risk_tags: '',
  source_label: '',
  summary: '',
  validity_status: 'UNKNOWN',
})

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

watch(
  () => props.document,
  (doc) => {
    if (!doc) return
    editForm.document_date = doc.document_date?.slice(0, 10) || ''
    editForm.risk_tags = doc.risk_tags.join(', ')
    editForm.source_label = doc.source_display
    editForm.summary = doc.summary || ''
    editForm.validity_status = doc.validity_status
  },
  { immediate: true },
)

function submitSave() {
  if (!props.document) return
  emit('save', props.document, { ...editForm })
}
</script>

<style scoped>
.dialog-meta, .dialog-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.dialog-meta { justify-content: space-between; margin-bottom: 16px; }
.dialog-actions { justify-content: flex-end; margin-top: 20px; }
.citation { padding-left: 10px; border-left: 2px solid #aa9fe6; color: #788398; font-size: 12px; }
.fragment { border-bottom: 1px solid #edf0f5; padding: 12px 0; }
.fragment p, .case-detail p { white-space: pre-wrap; line-height: 1.7; }
</style>
