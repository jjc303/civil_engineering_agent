<template>
  <div class="education-workbench">
    <header class="page-header">
      <div>
        <span class="eyebrow">SAFETY EDUCATION</span>
        <h1>{{ t('learning.title') }}</h1>
        <p>{{ t('learning.subtitle') }}</p>
      </div>
      <el-button text :loading="overviewLoading" @click="refresh">{{ t('learning.refreshData') }}</el-button>
    </header>

    <LearningOverviewSection
      :overview="overview"
      :week-label="weekLabel"
      :busy="busy"
      :error="overviewError"
      @open-custom-report="reportFormOpen = true"
      @create-weekly-report="makeWeeklyReport"
      @open-training-composer="openTrainingComposer()"
      @retry="loadOverview"
    />

    <div class="content-grid">
      <main class="primary-column">
        <LearningRecommendSection
          :insights="currentInsights"
          :loading="insightsLoading"
          :has-main-risks="Boolean(overview?.main_risks.length)"
          :format-day="formatDay"
          @open-document="openDocument"
          @add-to-training="addToTraining"
        />

        <LearningLibrarySection
          v-model:doc-query="docQuery"
          v-model:doc-type="docType"
          v-model:risk-type="riskType"
          v-model:document-range="documentRange"
          :documents="documents"
          :document-total="documentTotal"
          :document-offset="documentOffset"
          :available-risk-tags="availableRiskTags"
          :format-day="formatDay"
          @filter="searchLibrary"
          @page-change="changeDocumentPage"
          @open-document="openDocument"
          @open-upload="uploadOpen = true"
        />
      </main>

      <LearningSideColumn
        :weekly-training="weeklyTraining"
        :insights="currentInsights"
        :insights-loading="insightsLoading"
        :format-insight-time="formatInsightTime"
        @open-training-composer="openTrainingComposer()"
        @show-training="showTraining"
        @refresh-insights="loadInsights(true)"
      />
    </div>

    <LearningHistorySection
      :reports="reports"
      :trainings="trainings"
      :report-day="reportDay"
      @show-report="showReport"
      @download-pdf="downloadPdf"
      @show-training="showTraining"
    />

    <CustomReportDialog v-model="reportFormOpen" :busy="busy" @submit="makeReport" />
    <ReportDetailDialog
      v-model="reportDetailOpen"
      :report="selectedReport"
      :busy="busy"
      :report-day="reportDay"
      @save="saveReport"
      @confirm="approveReport"
      @download-pdf="downloadPdf"
      @delete="removeReport"
    />
    <TrainingBuilderDialog
      v-model="trainingFormOpen"
      :form="trainingForm"
      :confirmed-reports="confirmedReports"
      :all-documents="allDocuments"
      :busy="busy"
      :report-day="reportDay"
      @search-docs="(q) => loadDocumentOptions(q, trainingForm.document_ids)"
      @submit="makeTraining"
    />
    <TrainingDetailDialog
      v-model="trainingDetailOpen"
      :training="selectedTraining"
      :busy="busy"
      @save="saveTraining"
      @publish="approveTraining"
      @delete="removeTraining"
    />
    <DocumentDetailDialog
      v-model="documentDetailOpen"
      :document="selectedDocument"
      :case-detail="caseDetail"
      :fragments="documentFragments"
      :busy="busy"
      :format-day="formatDay"
      @save="saveDocument"
      @regenerate-summary="generateSummary"
      @add-to-training="addToTraining"
      @generate-case="generateCase"
      @load-fragments="loadFragments"
      @retire="removeDocument"
    />
    <DocumentUploadDialog v-model="uploadOpen" :busy="busy" @submit="submitUpload" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/learning'
import { LEARNING_PAGE_SIZE, useLearningCenter } from '@/composables/useLearningCenter'
import { useAppI18n } from '@/i18n/useAppI18n'
import { zonedDateBoundaryToIso } from '@/utils/datetime'
import CustomReportDialog from '@/components/learning/CustomReportDialog.vue'
import DocumentDetailDialog, { type DocumentEditPayload } from '@/components/learning/DocumentDetailDialog.vue'
import DocumentUploadDialog, { type UploadDocumentFields } from '@/components/learning/DocumentUploadDialog.vue'
import LearningHistorySection from '@/components/learning/LearningHistorySection.vue'
import LearningLibrarySection from '@/components/learning/LearningLibrarySection.vue'
import LearningOverviewSection from '@/components/learning/LearningOverviewSection.vue'
import LearningRecommendSection from '@/components/learning/LearningRecommendSection.vue'
import LearningSideColumn from '@/components/learning/LearningSideColumn.vue'
import ReportDetailDialog from '@/components/learning/ReportDetailDialog.vue'
import TrainingBuilderDialog, { type TrainingBuilderFormState } from '@/components/learning/TrainingBuilderDialog.vue'
import TrainingDetailDialog from '@/components/learning/TrainingDetailDialog.vue'

const { t } = useAppI18n()
const {
  timezone, busy, overviewLoading, overviewError, insightsLoading, overview, reports, trainings, documents,
  allDocuments, documentTotal, documentOffset, docQuery, riskType, docType, documentRange, confirmedReports,
  currentInsights, weeklyTraining, availableRiskTags, weekLabel, formatDay, formatInsightTime, reportDay,
  runTask, downloadPdf, loadOverview, loadInsights, loadDocuments, loadDocumentOptions, reloadReports, reloadTrainings, refresh,
} = useLearningCenter()

const reportFormOpen = ref(false), reportDetailOpen = ref(false), trainingFormOpen = ref(false)
const trainingDetailOpen = ref(false), documentDetailOpen = ref(false), uploadOpen = ref(false)
const selectedReport = ref<api.Report | null>(null), selectedTraining = ref<api.Training | null>(null)
const selectedDocument = ref<api.KnowledgeDocument | null>(null), caseDetail = ref<api.CaseDetail | null>(null)
const documentFragments = ref<Array<{ content: string; citation: api.Citation }>>([])
const trainingForm = ref<TrainingBuilderFormState>({ report_id: '', title: '', document_ids: [], target_count: 1, question_count: 5, pass_score: 80 })

const searchLibrary = () => { documentOffset.value = 0; void loadDocuments() }
const changeDocumentPage = (page: number) => { documentOffset.value = (page - 1) * LEARNING_PAGE_SIZE; void loadDocuments() }
const showReport = (report: api.Report) => { selectedReport.value = JSON.parse(JSON.stringify(report)) as api.Report; reportDetailOpen.value = true }
const makeWeeklyReport = () => {
  if (!overview.value) return ElMessage.warning(t('learning.overviewNotReady'))
  void runTask(async () => { const report = await api.createReport(overview.value!.period_start_utc, overview.value!.period_end_utc); await reloadReports(); showReport(report); ElMessage.success(t('learning.weeklyReportDraftCreated')) })
}
const makeReport = (range: [string, string]) => {
  void runTask(async () => { const report = await api.createReport(zonedDateBoundaryToIso(range[0], timezone), zonedDateBoundaryToIso(range[1], timezone, true)); await reloadReports(); reportFormOpen.value = false; showReport(report); ElMessage.success(t('learning.reportDraftCreated')) })
}
const saveReport = (report: api.Report) => { void runTask(async () => { selectedReport.value = await api.editReport(report.report_id, report.content); await reloadReports(); ElMessage.success(t('learning.savedSuccess')) }) }
const approveReport = (report: api.Report) => { void runTask(async () => { await api.editReport(report.report_id, report.content); selectedReport.value = await api.confirmReport(report.report_id); await reloadReports(); ElMessage.success(t('learning.reportConfirmedSuccess')) }) }
async function removeReport(report: api.Report) {
  if (trainings.value.some((task) => task.report_id === report.report_id)) return ElMessage.warning(t('learning.deleteReferencedWarning'))
  try { await ElMessageBox.confirm(report.status === 'CONFIRMED' ? t('learning.deleteConfirmedReportWarn') : t('learning.deleteDraftReportWarn'), t('learning.confirmDeleteReportTitle'), { type: 'warning', confirmButtonText: t('learning.confirmDeleteBtn') }) } catch { return }
  await runTask(async () => { await api.deleteReport(report.report_id); reportDetailOpen.value = false; selectedReport.value = null; if (trainingForm.value.report_id === report.report_id) trainingForm.value.report_id = ''; await reloadReports(); ElMessage.success(t('learning.reportDeletedSuccess')) })
}

const openDocument = (doc: api.KnowledgeDocument) => { selectedDocument.value = doc; caseDetail.value = null; documentFragments.value = []; documentDetailOpen.value = true }
const generateSummary = (doc: api.KnowledgeDocument) => { void runTask(async () => { selectedDocument.value = await api.regenerateDocumentSummary(doc.document_id); await loadDocuments(); ElMessage.success(t('learning.summaryGeneratedSuccess')) }) }
const loadFragments = (doc: api.KnowledgeDocument) => { void runTask(async () => { documentFragments.value = (await api.getDocumentFragments(doc.document_id)).items }) }
const generateCase = (doc: api.KnowledgeDocument) => { void runTask(async () => { caseDetail.value = await api.getCaseDetail(doc.document_id) }) }
const saveDocument = (doc: api.KnowledgeDocument, form: DocumentEditPayload) => {
  void runTask(async () => {
    let updated = await api.updateDocumentMetadata(doc.document_id, { document_date: form.document_date ? zonedDateBoundaryToIso(form.document_date, timezone) : null, risk_tags: form.risk_tags.split(',').map((s) => s.trim()).filter(Boolean), source_display: form.source_label, summary: form.summary })
    if (doc.document_type === 'STANDARD') updated = await api.updateStandardValidity(doc.document_id, form.validity_status)
    selectedDocument.value = updated as api.KnowledgeDocument; await loadDocuments(); ElMessage.success(t('learning.metadataSavedSuccess'))
  })
}
async function removeDocument(doc: api.KnowledgeDocument) {
  try { await ElMessageBox.confirm(t('learning.retireDocConfirm'), t('learning.retireDocTitle')) } catch { return }
  await runTask(async () => { await api.retireDocument(doc.document_id); documentDetailOpen.value = false; selectedDocument.value = null; await loadDocuments(); void loadInsights(true); ElMessage.success(t('learning.docRetiredSuccess')) })
}
const submitUpload = (file: File, fields: UploadDocumentFields, done: () => void) => {
  void runTask(async () => { await api.uploadDocument(file, fields); uploadOpen.value = false; done(); await loadDocuments(); void loadInsights(true); ElMessage.success(t('learning.docUploadedSuccess')) })
}

function openTrainingComposer(doc?: api.KnowledgeDocument) {
  if (!trainingForm.value.report_id) trainingForm.value.report_id = confirmedReports.value[0]?.report_id || ''
  if (!trainingForm.value.title) trainingForm.value.title = overview.value?.main_risks[0] ? t('learning.defaultTrainingTitleWithRisk', { risk: overview.value.main_risks[0].label }) : t('learning.defaultTrainingTitle')
  if (!trainingForm.value.document_ids.length) {
    const recs = currentInsights.value?.recommended_cases.slice(0, 2) || []
    trainingForm.value.document_ids = recs.map((item) => item.document_id)
    allDocuments.value = [...recs.filter((item) => !allDocuments.value.some((d) => d.document_id === item.document_id)), ...allDocuments.value]
  }
  if (doc && !trainingForm.value.document_ids.includes(doc.document_id)) {
    if (trainingForm.value.document_ids.length >= 10) return ElMessage.warning(t('learning.maxDocsWarning'))
    trainingForm.value.document_ids.push(doc.document_id)
    if (!allDocuments.value.some((item) => item.document_id === doc.document_id)) allDocuments.value = [doc, ...allDocuments.value]
  }
  trainingFormOpen.value = true
  void loadDocumentOptions('', trainingForm.value.document_ids).catch(() => ElMessage.warning(t('learning.docOptionsFailed')))
}
const addToTraining = (doc: api.KnowledgeDocument) => { openTrainingComposer(doc); ElMessage.success(t('learning.addedToTrainingMsg')) }
const showTraining = (task: api.Training) => { selectedTraining.value = JSON.parse(JSON.stringify(task)) as api.Training; trainingDetailOpen.value = true }
const makeTraining = () => { void runTask(async () => { const task = await api.createTraining(trainingForm.value); await reloadTrainings(); trainingFormOpen.value = false; await loadOverview(); showTraining(task); ElMessage.success(t('learning.trainingDraftCreated')) }) }
const saveTraining = (task: api.Training) => { void runTask(async () => { selectedTraining.value = await api.editTraining(task.task_id, task); await reloadTrainings(); ElMessage.success(t('learning.trainingDraftSaved')) }) }
const approveTraining = (task: api.Training) => { void runTask(async () => { await api.editTraining(task.task_id, task); const published = await api.publishTraining(task.task_id); await reloadTrainings(); await loadOverview(); showTraining(published); ElMessage.success(t('learning.trainingPublishedMsg')) }) }
async function removeTraining(task: api.Training, completedCount?: number) {
  const published = task.status === 'PUBLISHED'
  const records = completedCount === undefined ? t('learning.existingRecordsFallback') : t('learning.existingRecordsCount', { count: completedCount })
  try { await ElMessageBox.confirm(published ? t('learning.deletePublishedTrainingWarn', { records }) : t('learning.deleteTrainingDraftWarn'), published ? t('learning.deletePublishedTrainingTitle') : t('learning.deleteTrainingDraftTitle'), { type: 'warning', confirmButtonText: t('learning.confirmDeleteBtn') }) } catch { return }
  await runTask(async () => { await api.deleteTraining(task.task_id); trainingDetailOpen.value = false; selectedTraining.value = null; await reloadTrainings(); await loadOverview(); ElMessage.success(t('learning.trainingDeletedMsg')) })
}

onMounted(() => { void refresh() })
</script>

<style scoped>
.education-workbench { max-width: 1480px; margin: 0 auto; padding: 14px 20px 48px; color: #384257; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin: 2px 0 22px; }
.page-header h1 { font-size: 28px; letter-spacing: -.03em; margin: 6px 0; }
.page-header p { color: #8a92a3; margin: 0; font-size: 13px; }
.eyebrow { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.content-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr); gap: 20px; align-items: start; margin-top: 22px; }
.primary-column { display: grid; gap: 20px; min-width: 0; }

@media (max-width: 1080px) { .content-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .education-workbench { padding: 10px 4px 36px; } .page-header h1 { font-size: 23px; } }
</style>
