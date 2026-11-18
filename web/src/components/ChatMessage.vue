<template>
  <div :class="['message-row', msg.role]">
    <!-- Avatar -->
    <div class="avatar">
      <el-avatar :icon="msg.role === 'user' ? UserFilled : Service" :size="36" />
    </div>

    <!-- Message content -->
    <div class="message-content">
      <div class="sender-name">{{ msg.role === 'user' ? t('copilot.userSender') : assistantName }}</div>

      <!-- User bubble -->
      <div v-if="msg.role === 'user'" class="user-bubble">
        {{ msg.text }}
      </div>

      <!-- Assistant bubble -->
      <div v-else class="agent-bubble">
        <!-- Degraded alert -->
        <el-alert
          v-if="msg.degraded"
          :title="degradedTitle(msg.errorCode)"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />

        <!-- Markdown rendered answer -->
        <div class="markdown-body" v-html="renderMarkdown(msg.text)"></div>
        <button v-if="msg.retryQuestion" class="retry-question" :disabled="thinking" @click="$emit('selectPrompt', msg.retryQuestion!)">{{ t('copilot.retryQuestion') }}</button>

        <!-- Report previews -->
        <section v-if="msg.reportPreviews?.length" class="report-previews" :aria-label="t('copilot.reportPreviewsAria')">
          <div class="report-previews-heading"><strong>{{ t('copilot.reportPreviewsTitle') }}</strong><span>{{ t('copilot.totalItemsCount', { count: msg.reportCount ?? msg.reportPreviews.length }) }}</span></div>
          <article v-for="report in msg.reportPreviews" :key="report.report_id" class="report-preview-card">
            <div class="report-preview-top"><strong>{{ t('copilot.safetyReportTitle', { range: `${reportDate(report.period_start_utc)} — ${reportDate(report.period_end_utc, true)}` }) }}</strong><el-tag size="small" :type="report.status === 'CONFIRMED' ? 'success' : 'warning'">{{ report.status === 'CONFIRMED' ? t('enums.reportStatus.CONFIRMED') : t('enums.reportStatus.DRAFT') }}</el-tag></div>
            <div class="report-preview-meta">{{ t('copilot.reportEventCount', { count: report.event_count }) }}</div>
            <p>{{ report.summary || t('copilot.noReportSummary') }}</p>
            <div class="report-preview-actions"><el-button link type="primary" @click="$emit('openReportDetail', report.report_id)">{{ t('copilot.viewReportDetail') }}</el-button><el-button v-if="report.pdf_url" link type="primary" @click="$emit('previewReportPdf', report.report_id)">{{ t('copilot.previewPdf') }}</el-button><el-button v-if="report.pdf_url" link @click="$emit('downloadReportPdf', report.report_id)">{{ t('copilot.downloadPdf') }}</el-button></div>
          </article>
          <router-link v-if="(msg.reportCount ?? 0) > msg.reportPreviews.length" to="/learning" class="report-more">{{ t('copilot.viewAllReports') }}</router-link>
        </section>

        <!-- Training previews -->
        <section v-if="msg.trainingPreviews?.length" class="report-previews" :aria-label="t('copilot.trainingPreviewsAria')">
          <div class="report-previews-heading"><strong>{{ t('copilot.trainingPreviewsTitle') }}</strong><span>{{ t('copilot.totalTasksCount', { count: msg.trainingCount ?? msg.trainingPreviews.length }) }}</span></div>
          <article v-for="training in msg.trainingPreviews" :key="training.training_id" class="report-preview-card">
            <div class="report-preview-top"><strong>{{ training.title }}</strong><el-tag size="small" :type="training.status === 'PUBLISHED' ? 'success' : 'warning'">{{ training.status === 'PUBLISHED' ? t('enums.trainingStatus.PUBLISHED') : t('enums.trainingStatus.DRAFT') }}</el-tag></div>
            <div class="report-preview-meta">{{ t('copilot.trainingPreviewMeta', { target: training.target_count, questions: training.question_count }) }}</div>
            <p>{{ training.material_preview || t('copilot.noMaterialSummary') }}</p>
            <div class="report-preview-actions"><el-button link type="primary" @click="$emit('openTrainingDetail', training.training_id)">{{ t('copilot.viewTrainingDetail') }}</el-button><a v-if="training.public_url && learningPathValue(training.public_url)" class="training-link" :href="learningPathValue(training.public_url)" target="_blank" rel="noopener">{{ t('copilot.openStudyPage') }}</a></div>
          </article>
          <router-link v-if="(msg.trainingCount ?? 0) > msg.trainingPreviews.length" to="/learning" class="report-more">{{ t('copilot.viewAllTraining') }}</router-link>
        </section>

        <!-- Evidence cards -->
        <div v-if="showEvidence && msg.evidence && msg.evidence.length > 0" class="evidence-section">
          <div class="evidence-header">
            <el-icon><Picture /></el-icon>
            <span>{{ t('copilot.evidenceHeader', { count: msg.evidence.length }) }}</span>
          </div>
          <div class="evidence-grid">
            <div
              v-for="(ev, eIdx) in msg.evidence"
              :key="eIdx"
              class="evidence-card"
              @click="$emit('viewEvidence', ev)"
            >
              <el-image
                :src="resolveMediaUrl(ev.snapshot_uri)"
                :preview-src-list="[resolveMediaUrl(ev.snapshot_uri)]"
                preview-teleported
                fit="cover"
                class="thumb-img"
                :alt="t('copilot.evidenceAlt')"
                @click.stop
              />
              <div class="evidence-info">
                <span class="ev-time">{{ formatMsgTime(ev.occurred_at_utc) }}</span>
                <span class="ev-uuid font-mono">{{ ev.event_uuid.substring(0, 8) }}...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge citations -->
        <div v-if="msg.knowledgeCitations && msg.knowledgeCitations.length > 0" class="evidence-section">
          <div class="evidence-header"><el-icon><Document /></el-icon><span>{{ t('copilot.citationsHeader', { count: msg.knowledgeCitations.length }) }}</span></div>
          <div v-for="citation in msg.knowledgeCitations" :key="citation.chunk_id" class="tool-item">
            <span>{{ citation.document_type === 'STANDARD' ? t('enums.documentType.STANDARD_SHORT') : t('enums.documentType.ACCIDENT_REPORT') }}：{{ citation.title }}（v{{ citation.version_no }}，{{ citation.page_or_section }}）<small v-if="citation.source_label"> · {{ citation.source_label }}</small></span>
            <el-tag size="small" type="info">{{ t('copilot.relevanceScore', { score: citation.relevance_score.toFixed(2) }) }}</el-tag>
          </div>
        </div>

        <!-- Guided selection -->
        <div v-if="msg.guidedSelection" class="guided-selection">
          <div class="guided-selection-title">{{ t('copilot.guidedTitle') }}</div>
          <div class="guided-selection-prompt">{{ msg.guidedSelection.prompt }}</div>
          <div v-if="msg.guidedSelection.options.length" class="guided-selection-options">
            <el-button
              v-for="option in msg.guidedSelection.options"
              :key="option.option_id"
              plain
              @click="$emit('selectGuidedTarget', msg, option)"
            >
              <span>{{ option.label }}</span><small>{{ option.description }}</small>
            </el-button>
          </div>
          <el-button v-else-if="msg.guidedSelection.kind === 'TRAINING_REPORT'" type="primary" plain size="small" @click="$emit('selectPrompt', t('copilot.generateWeeklyReport'))">{{ t('copilot.generateWeeklyReport') }}</el-button>
        </div>

        <!-- Pending action -->
        <div v-if="msg.pendingAction" class="pending-action">
          <div class="pending-action-title">{{ t('copilot.pendingConfirmTitle') }}</div>
          <div class="pending-action-summary">{{ msg.pendingAction.summary }}</div>
          <div class="pending-action-meta">
            <el-tag :type="actionTagType(msg.pendingAction.status)" size="small">{{ actionStatusText(msg.pendingAction.status) }}</el-tag>
            <span v-if="msg.pendingAction.status === 'PENDING'">{{ t('copilot.validUntil', { time: formatMsgDateTime(msg.pendingAction.expires_at_utc) }) }}</span>
          </div>
          <div v-if="msg.pendingAction.status === 'PENDING'" class="pending-action-buttons">
            <el-button size="small" type="primary" :loading="msg.actionBusy" @click="$emit('confirmAction', msg)">{{ t('tasks.confirmExecute') }}</el-button>
            <el-button size="small" :disabled="msg.actionBusy" @click="$emit('cancelAction', msg)">{{ t('common.cancel') }}</el-button>
          </div>
          <div v-if="msg.actionResult" class="pending-action-result">{{ msg.actionResult }}</div>
          <div v-if="msg.actionReportId" class="report-preview-actions"><el-button link type="primary" @click="$emit('openReportDetail', msg.actionReportId)">{{ t('copilot.viewReportDetail') }}</el-button><el-button v-if="msg.actionReportPdf" link type="primary" @click="$emit('previewReportPdf', msg.actionReportId)">{{ t('copilot.previewPdf') }}</el-button><el-button v-if="msg.actionReportPdf" link @click="$emit('downloadReportPdf', msg.actionReportId)">{{ t('copilot.downloadPdf') }}</el-button></div>
          <div v-if="msg.actionTrainingId" class="report-preview-actions"><el-button link type="primary" @click="$emit('openTrainingDetail', msg.actionTrainingId)">{{ t('copilot.viewTrainingDetail') }}</el-button><a v-if="msg.actionTrainingUrl && trainingLinkPath(msg.actionTrainingUrl)" class="training-link" :href="trainingLinkPath(msg.actionTrainingUrl)" target="_blank" rel="noopener">{{ t('copilot.openStudyPage') }}</a></div>
        </div>

        <!-- Tool trace -->
        <div v-if="msg.toolTrace && msg.toolTrace.length > 0" class="trace-section">
          <el-collapse>
            <el-collapse-item name="trace">
              <template #title>
                <div class="trace-title">
                  <el-icon><Operation /></el-icon>
                  <span>{{ t('copilot.toolTraceHeader', { count: msg.toolTrace.length }) }}</span>
                </div>
              </template>
              <el-timeline style="padding-left: 8px; margin-top: 8px">
                <el-timeline-item
                  v-for="(t, tIdx) in msg.toolTrace"
                  :key="tIdx"
                  :type="t.success ? 'primary' : 'danger'"
                  size="small"
                >
                  <div class="tool-item">
                    <span class="tool-name font-mono">{{ t.tool_name }}</span>
                    <span class="tool-purpose">{{ t.purpose }}</span>
                    <el-tag size="small" type="info">{{ t.duration_ms }} ms</el-tag>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { UserFilled, Service, Picture, Document, Operation } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { resolveMediaUrl } from '@/api/client'
import { useAppI18n } from '@/i18n/useAppI18n'
import { getLearningTimezone, utcDate } from '@/utils/datetime'
import { learningPath as learningPathValue } from '@/utils/deployment'
import type { ChatMessageItem } from '@/types/chat'
import type { ChatEvidence, GuidedSelectionOption, PendingActionStatus } from '@/types/contract'

const { t, formatTime: formatLocaleTime, formatDateTime: formatLocaleDateTime, formatDate: formatLocaleDate } = useAppI18n()

const props = defineProps<{
  msg: ChatMessageItem
  thinking: boolean
  showEvidence: boolean
  assistantName: string
}>()

defineEmits<{
  selectPrompt: [question: string]
  viewEvidence: [ev: ChatEvidence]
  selectGuidedTarget: [msg: ChatMessageItem, option: GuidedSelectionOption]
  confirmAction: [msg: ChatMessageItem]
  cancelAction: [msg: ChatMessageItem]
  openReportDetail: [id: string]
  previewReportPdf: [id: string]
  downloadReportPdf: [id: string]
  openTrainingDetail: [id: string]
  learningPath: [url: string]
}>()

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

function renderMarkdown(content: string): string {
  return md.render(content || '')
}

const DEGRADED_TITLE_KEYS: Record<string, string> = {
  REQUEST_TIMEOUT: 'copilot.degradedTimeout',
  REQUEST_SERVER_ERROR: 'copilot.degradedServer',
  REQUEST_FAILED: 'copilot.degradedNetwork',
  UNSUPPORTED_STANDARD_REFERENCE: 'copilot.degradedUnsupported',
  STANDARDS_RETRIEVAL_FAILED: 'copilot.degradedRetrieval',
}

function degradedTitle(code?: string | null): string {
  return t((code && DEGRADED_TITLE_KEYS[code]) || 'copilot.degradedDefault')
}

function formatMsgTime(utcStr: string): string {
  if (!utcStr) return '-'
  return formatLocaleTime(utcStr)
}

function formatMsgDateTime(utcStr: string): string {
  return formatLocaleDateTime(utcStr)
}

function reportDate(value: string, exclusiveEnd = false): string {
  const date = new Date(utcDate(value).getTime() - (exclusiveEnd ? 1 : 0))
  return formatLocaleDate(date, { timeZone: getLearningTimezone(), year: 'numeric', month: '2-digit', day: '2-digit' })
}

function actionStatusText(status: PendingActionStatus): string {
  return t(`enums.pendingActionStatus.${status}`)
}

function actionTagType(status: PendingActionStatus): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  return ({ PENDING: 'warning', EXECUTING: 'primary', EXECUTED: 'success', CANCELLED: 'info', EXPIRED: 'info', FAILED: 'danger' } as Record<PendingActionStatus, 'primary' | 'success' | 'warning' | 'info' | 'danger'>)[status]
}

function trainingLinkPath(publicUrl: string): string | undefined {
  return learningPathValue(publicUrl)
}
</script>

<style scoped>
.message-row {
  display: flex;
  gap: 12px;
  max-width: 94%;
  min-width: 0;
  flex-shrink: 0;
}
.message-content { min-width: 0; }
.avatar { flex-shrink: 0; padding-top: 2px; }
.assistant .avatar :deep(.el-avatar) { background: #eee8f9; color: #8b74bd; }
.user .avatar :deep(.el-avatar) { background: #f0f1f5; color: #969daf; }
.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.message-row.assistant {
  align-self: flex-start;
}
.sender-name {
  font-size: 12px;
  color: #9b9fad;
  margin-bottom: 8px;
}
.message-row.user .sender-name {
  text-align: right;
}
.user-bubble {
  background: #806acd;
  color: #ffffff;
  padding: 12px 16px;
  border-radius: 16px 4px 16px 16px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.agent-bubble {
  background: #f9f8fc;
  border: 1px solid #ede9f4;
  color: #4a5269;
  padding: 18px 20px;
  border-radius: 4px 16px 16px 16px;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.agent-bubble :deep(.el-alert) { border-radius: 10px; }
.retry-question { margin-top: 12px; color: #7962bd; background: #f0ebf9; border: 1px solid #e1d7f2; border-radius: 8px; padding: 7px 11px; cursor: pointer; font-size: 12px; }
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) { margin-top: 10px; margin-bottom: 6px; color: #0f172a; }
.markdown-body :deep(p) { margin: 6px 0; }
.markdown-body :deep(ul) { padding-left: 20px; margin: 6px 0; }
.markdown-body :deep(table) { display: block; overflow-x: auto; max-width: 100%; border-collapse: collapse; }
.markdown-body :deep(td), .markdown-body :deep(th) { border: 1px solid #e2dcec; padding: 6px 10px; }
.markdown-body :deep(pre) { overflow-x: auto; padding: 12px; border-radius: 8px; background: #f0ecf7; }
.markdown-body :deep(a) { color: #8064bd; }
.report-previews { margin-top: 16px; padding-top: 14px; border-top: 1px dashed #d8deea; display: grid; gap: 10px; }
.report-previews-heading, .report-preview-top, .report-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-previews-heading strong { font-size: 14px; color: #344054; }
.report-previews-heading span, .report-preview-meta { font-size: 12px; color: #7b8798; }
.report-preview-card { padding: 14px 16px; border: 1px solid #e1e6f1; border-radius: 12px; background: #fff; min-width: 0; }
.report-preview-top strong { font-size: 14px; color: #303b51; }
.report-preview-meta { margin-top: 7px; }
.report-preview-card p { margin: 9px 0 10px; color: #526078; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.report-preview-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.report-preview-actions .el-button { margin: 0; }
.report-more { font-size: 12px; color: #5c58bd; text-decoration: none; }
.evidence-section { margin-top: 14px; border-top: 1px dashed #e2e8f0; padding-top: 10px; }
.evidence-header { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 8px; }
.evidence-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.evidence-card { display: flex; align-items: center; gap: 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; cursor: pointer; transition: all 0.2s; }
.evidence-card:hover { border-color: #2563eb; transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
.thumb-img { width: 50px; height: 50px; object-fit: cover; border-radius: 4px; background: #0f172a; }
.thumb-img :deep(img) { width: 100%; height: 100%; }
.evidence-info { display: flex; flex-direction: column; font-size: 11px; }
.ev-time { color: #64748b; }
.ev-uuid { color: #2563eb; }
.trace-section { margin-top: 12px; }
.trace-title { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748b; }
.tool-item { display: flex; align-items: center; gap: 8px; font-size: 12px; flex-wrap: wrap; }
.tool-name { font-weight: 600; color: #0f172a; }
.tool-purpose { color: #64748b; }
.font-mono { font-family: ui-monospace, monospace; }
.pending-action { margin-top: 14px; padding: 12px; border: 1px solid #f59e0b; border-radius: 12px; background: #fffbeb; }
.pending-action-title { font-weight: 600; color: #92400e; }
.pending-action-summary { margin-top: 4px; color: #334155; }
.pending-action-meta { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 12px; color: #64748b; }
.pending-action-buttons { display: flex; gap: 8px; margin-top: 10px; }
.pending-action-result { margin-top: 8px; font-size: 12px; color: #475569; }
.guided-selection { margin-top: 14px; padding: 12px; border: 1px solid #93c5fd; border-radius: 12px; background: #f6f2fc; border-color: #d9ccef; }
.guided-selection-title { font-weight: 600; color: #8270b0; }
.guided-selection-prompt { margin-top: 4px; color: #334155; }
.guided-selection-options { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.guided-selection-options :deep(.el-button) { height: auto; min-height: 34px; text-align: left; display: flex; flex-direction: column; align-items: flex-start; }
.guided-selection-options small { color: #64748b; font-size: 11px; }
.training-link { color: #5b55bb; font-size: 12px; font-weight: 600; text-decoration: none; }
.training-link:hover { text-decoration: underline; }
@media (max-width: 760px) { .message-row { gap: 8px; max-width: 100%; } .agent-bubble { padding: 12px 14px; font-size: 13px; } }
@media (prefers-reduced-motion: reduce) { .evidence-card { transition: none; } }
</style>