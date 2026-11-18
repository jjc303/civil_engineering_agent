<template>
  <el-dialog v-model="open" width="720px" class="upload-dialog" destroy-on-close>
    <template #header>
      <div class="upload-heading">
        <span class="upload-heading-icon"><el-icon><UploadFilled /></el-icon></span>
        <div>
          <h2>{{ t('learning.uploadTitle') }}</h2>
          <p>{{ t('learning.uploadSubtitle') }}</p>
        </div>
      </div>
    </template>

    <div class="upload-content">
      <label class="upload-drop-zone" :class="{ 'has-file': file }" for="learning-file-upload" @dragover.prevent @drop.prevent="dropFile">
        <input :key="fileInputKey" id="learning-file-upload" class="upload-file-input" type="file" accept=".pdf,.docx,.md,.txt" @change="pickFile" />
        <span class="upload-drop-icon"><el-icon><UploadFilled /></el-icon></span>
        <strong>{{ file ? file.name : t('learning.dropZonePrompt') }}</strong>
        <span class="upload-drop-subtitle">
          {{ file ? t('learning.dropZoneSelected', { size: formatFileSize(file.size) }) : t('learning.dropZoneTypes') }}
        </span>
        <span class="upload-select-button">{{ file ? t('learning.replaceFile') : t('learning.chooseFile') }}</span>
      </label>

      <div class="upload-divider">
        <strong>{{ t('learning.docInfoDivider') }}</strong>
        <span>{{ t('learning.docInfoHint') }}</span>
      </div>

      <el-form class="upload-form" label-position="top">
        <el-form-item :label="t('learning.docTitleLabel')" required>
          <el-input v-model="form.title" :placeholder="t('learning.docTitlePlaceholder')" clearable />
        </el-form-item>
        <div class="upload-form-grid">
          <el-form-item :label="t('learning.docTypeLabel')" required>
            <el-select v-model="form.document_type" style="width: 100%">
              <el-option :label="t('enums.documentType.ACCIDENT_REPORT')" value="ACCIDENT_REPORT" />
              <el-option :label="t('enums.documentType.STANDARD')" value="STANDARD" />
            </el-select>
          </el-form-item>
          <el-form-item :label="form.document_type === 'STANDARD' ? t('learning.standardPublishDate') : t('learning.accidentDate')">
            <el-date-picker
              v-model="form.document_date"
              type="date"
              value-format="YYYY-MM-DD"
              :placeholder="t('learning.chooseDate')"
              clearable
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="t('learning.riskTagsLabel')">
            <el-input v-model="form.risk_tags" :placeholder="t('learning.riskTagsPlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('learning.docSourceLabel')">
            <el-input v-model="form.source_label" :placeholder="t('learning.docSourcePlaceholder')" />
          </el-form-item>
        </div>
        <el-form-item :label="t('learning.summaryLabel')">
          <el-input v-model="form.summary" type="textarea" :rows="3" :placeholder="t('learning.summaryPlaceholder')" />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="upload-footer">
        <span>{{ t('learning.uploadFooterHint') }}</span>
        <div>
          <el-button @click="open = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" :loading="busy" @click="submit">{{ t('learning.uploadAndIndex') }}</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useAppI18n } from '@/i18n/useAppI18n'

export interface UploadDocumentFields {
  title: string
  source_label: string
  document_type: string
  document_date: string
  risk_tags: string
  summary: string
}

const props = defineProps<{
  modelValue: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  submit: [file: File, fields: UploadDocumentFields, done: () => void]
}>()

const { t } = useAppI18n()
const file = ref<File | null>(null)
const fileInputKey = ref(0)
const form = reactive<UploadDocumentFields>({
  title: '',
  source_label: '',
  document_type: 'ACCIDENT_REPORT',
  document_date: '',
  risk_tags: '',
  summary: '',
})

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

function formatFileSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function setSelectedFile(selected: File | null): void {
  file.value = selected
  if (selected && !form.title) {
    form.title = selected.name.replace(/\.[^.]+$/, '')
  }
}

const pickFile = (event: Event) => setSelectedFile((event.target as HTMLInputElement).files?.[0] || null)
const dropFile = (event: DragEvent) => setSelectedFile(event.dataTransfer?.files?.[0] || null)

function resetForm(): void {
  Object.assign(form, { title: '', source_label: '', document_type: 'ACCIDENT_REPORT', document_date: '', risk_tags: '', summary: '' })
  file.value = null
  fileInputKey.value += 1
}

function submit(): void {
  if (!file.value || !form.title) {
    ElMessage.warning(t('learning.uploadValidationWarning'))
    return
  }
  emit('submit', file.value, { ...form }, resetForm)
}
</script>

<style scoped>
:global(.upload-dialog) { max-width: calc(100vw - 32px); border-radius: 20px; overflow: hidden; box-shadow: 0 24px 70px #29345b2b; }
:global(.upload-dialog .el-dialog__header) { padding: 24px 28px 16px; margin: 0; }
:global(.upload-dialog .el-dialog__body) { padding: 0 28px 4px; }
:global(.upload-dialog .el-dialog__footer) { padding: 16px 28px 22px; border-top: 1px solid #eef0f6; }
.upload-heading { display: flex; align-items: center; gap: 14px; padding-right: 28px; }
.upload-heading-icon { width: 44px; height: 44px; flex: none; display: grid; place-items: center; border-radius: 13px; background: #eeeaff; color: #7461d5; font-size: 23px; }
.upload-heading h2 { margin: 0 0 3px; font-size: 20px; color: #303950; }
.upload-heading p { margin: 0; color: #8d96a6; font-size: 12px; line-height: 1.5; }
.upload-content { max-height: min(68vh, 660px); overflow-y: auto; padding: 2px 2px 4px; }
.upload-drop-zone { position: relative; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 7px; min-height: 170px; padding: 20px 24px; text-align: center; border: 1.5px dashed #bcb8e9; border-radius: 16px; background: #f8f7ff; cursor: pointer; transition: background .2s, border-color .2s, box-shadow .2s; }
.upload-drop-zone:hover, .upload-drop-zone:focus-within { background: #f1efff; border-color: #7967d8; box-shadow: 0 0 0 3px #7967d818; }
.upload-drop-zone.has-file { background: #f4f9f8; border-color: #91c9b0; }
.upload-file-input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.upload-drop-icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 13px; background: #e9e5fc; color: #7562d0; font-size: 22px; }
.upload-drop-zone.has-file .upload-drop-icon { background: #e1f2e9; color: #39946d; }
.upload-drop-zone strong { max-width: 100%; font-size: 14px; color: #38445d; line-height: 1.5; overflow-wrap: anywhere; }
.upload-drop-subtitle { font-size: 12px; color: #929bab; }
.upload-select-button { display: inline-flex; align-items: center; justify-content: center; min-height: 30px; margin-top: 4px; padding: 0 13px; border: 1px solid #d6d0f2; border-radius: 8px; background: #fff; color: #6857be; font-size: 12px; font-weight: 600; }
.upload-divider { display: flex; align-items: center; gap: 10px; margin: 24px 0 16px; }
.upload-divider strong { font-size: 14px; color: #3f485e; }
.upload-divider span { font-size: 11px; color: #a0a8b5; }
.upload-divider:after { content: ''; height: 1px; background: #eef0f5; flex: 1; }
.upload-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 16px; }
.upload-form :deep(.el-form-item) { margin-bottom: 16px; }
.upload-form :deep(.el-form-item__label) { color: #5b6679; font-size: 12px; font-weight: 600; margin-bottom: 5px; }
.upload-form :deep(.el-input__wrapper), .upload-form :deep(.el-select__wrapper), .upload-form :deep(.el-textarea__inner) { border-radius: 9px; }
.upload-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.upload-footer > span { font-size: 11px; color: #99a2b0; }
.upload-footer > div { display: flex; gap: 8px; }
.upload-footer .el-button { margin: 0; }
.upload-footer .el-button--primary { background: #7563d4; border-color: #7563d4; }
.upload-footer .el-button--primary:hover { background: #6652c5; border-color: #6652c5; }

@media (max-width: 640px) {
  :global(.upload-dialog .el-dialog__header) { padding: 20px 18px 14px; }
  :global(.upload-dialog .el-dialog__body) { padding: 0 18px 4px; }
  :global(.upload-dialog .el-dialog__footer) { padding: 14px 18px 18px; }
  .upload-form-grid { grid-template-columns: 1fr; }
  .upload-drop-zone { min-height: 150px; }
  .upload-heading h2 { font-size: 18px; }
  .upload-footer { align-items: stretch; flex-direction: column; }
  .upload-footer > div { justify-content: flex-end; }
}
</style>
