<template>
  <div :class="['message-row', msg.role]">
    <!-- Avatar -->
    <div class="avatar">
      <el-avatar :icon="msg.role === 'user' ? UserFilled : Service" :size="36" />
    </div>

    <!-- Message content -->
    <div class="message-content">
      <div class="sender-name">{{ msg.role === 'user' ? '用户' : assistantName }}</div>

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
        <button v-if="msg.retryQuestion" class="retry-question" :disabled="thinking" @click="$emit('selectPrompt', msg.retryQuestion!)">重新提问 ↗</button>

        <!-- Report previews -->
        <section v-if="msg.reportPreviews?.length" class="report-previews" aria-label="安全报告预览">
          <div class="report-previews-heading"><strong>安全报告预览</strong><span>共 {{ msg.reportCount ?? msg.reportPreviews.length }} 份</span></div>
          <article v-for="report in msg.reportPreviews" :key="report.report_id" class="report-preview-card">
            <div class="report-preview-top"><strong>{{ reportDate(report.period_start_utc) }} — {{ reportDate(report.period_end_utc, true) }} 安全报告</strong><el-tag size="small" :type="report.status === 'CONFIRMED' ? 'success' : 'warning'">{{ report.status === 'CONFIRMED' ? '已确认' : '草稿' }}</el-tag></div>
            <div class="report-preview-meta">{{ report.event_count }} 条有效违规事件</div>
            <p>{{ report.summary || '暂无报告摘要' }}</p>
            <div class="report-preview-actions"><el-button link type="primary" @click="$emit('openReportDetail', report.report_id)">查看报告详情</el-button><el-button v-if="report.pdf_url" link type="primary" @click="$emit('previewReportPdf', report.report_id)">预览 PDF</el-button><el-button v-if="report.pdf_url" link @click="$emit('downloadReportPdf', report.report_id)">下载 PDF</el-button></div>
          </article>
          <router-link v-if="(msg.reportCount ?? 0) > msg.reportPreviews.length" to="/learning" class="report-more">前往学习中心查看全部报告 →</router-link>
        </section>

        <!-- Training previews -->
        <section v-if="msg.trainingPreviews?.length" class="report-previews" aria-label="培训任务预览">
          <div class="report-previews-heading"><strong>培训任务预览</strong><span>共 {{ msg.trainingCount ?? msg.trainingPreviews.length }} 项</span></div>
          <article v-for="training in msg.trainingPreviews" :key="training.training_id" class="report-preview-card">
            <div class="report-preview-top"><strong>{{ training.title }}</strong><el-tag size="small" :type="training.status === 'PUBLISHED' ? 'success' : 'warning'">{{ training.status === 'PUBLISHED' ? '已发布' : '草稿' }}</el-tag></div>
            <div class="report-preview-meta">目标 {{ training.target_count }} 人 · {{ training.question_count }} 道题</div>
            <p>{{ training.material_preview || '暂无学习材料摘要' }}</p>
            <div class="report-preview-actions"><el-button link type="primary" @click="$emit('openTrainingDetail', training.training_id)">查看培训详情</el-button><a v-if="training.public_url && learningPathValue(training.public_url)" class="training-link" :href="learningPathValue(training.public_url)" target="_blank" rel="noopener">打开学习页 ↗</a></div>
          </article>
          <router-link v-if="(msg.trainingCount ?? 0) > msg.trainingPreviews.length" to="/learning" class="report-more">前往学习中心查看全部培训 →</router-link>
        </section>

        <!-- Evidence cards -->
        <div v-if="showEvidence && msg.evidence && msg.evidence.length > 0" class="evidence-section">
          <div class="evidence-header">
            <el-icon><Picture /></el-icon>
            <span>关联证据快照 ({{ msg.evidence.length }} 项):</span>
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
                alt="证据快照，点击预览"
                @click.stop
              />
              <div class="evidence-info">
                <span class="ev-time">{{ formatTime(ev.occurred_at_utc) }}</span>
                <span class="ev-uuid font-mono">{{ ev.event_uuid.substring(0, 8) }}...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge citations -->
        <div v-if="msg.knowledgeCitations && msg.knowledgeCitations.length > 0" class="evidence-section">
          <div class="evidence-header"><el-icon><Document /></el-icon><span>知识资料引用 ({{ msg.knowledgeCitations.length }} 项):</span></div>
          <div v-for="citation in msg.knowledgeCitations" :key="citation.chunk_id" class="tool-item">
            <span>{{ citation.document_type === 'STANDARD' ? '规范' : '事故报告' }}：{{ citation.title }}（v{{ citation.version_no }}，{{ citation.page_or_section }}）<small v-if="citation.source_label"> · {{ citation.source_label }}</small></span>
            <el-tag size="small" type="info">相关度 {{ citation.relevance_score.toFixed(2) }}</el-tag>
          </div>
        </div>

        <!-- Guided selection -->
        <div v-if="msg.guidedSelection" class="guided-selection">
          <div class="guided-selection-title">请选择操作目标</div>
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
          <el-button v-else-if="msg.guidedSelection.kind === 'TRAINING_REPORT'" type="primary" plain size="small" @click="$emit('selectPrompt', '生成本周安全报告')">生成本周安全报告</el-button>
        </div>

        <!-- Pending action -->
        <div v-if="msg.pendingAction" class="pending-action">
          <div class="pending-action-title">请确认后执行</div>
          <div class="pending-action-summary">{{ msg.pendingAction.summary }}</div>
          <div class="pending-action-meta">
            <el-tag :type="actionTagType(msg.pendingAction.status)" size="small">{{ actionStatusText(msg.pendingAction.status) }}</el-tag>
            <span v-if="msg.pendingAction.status === 'PENDING'">有效期至 {{ formatDateTime(msg.pendingAction.expires_at_utc) }}</span>
          </div>
          <div v-if="msg.pendingAction.status === 'PENDING'" class="pending-action-buttons">
            <el-button size="small" type="primary" :loading="msg.actionBusy" @click="$emit('confirmAction', msg)">确认执行</el-button>
            <el-button size="small" :disabled="msg.actionBusy" @click="$emit('cancelAction', msg)">取消</el-button>
          </div>
          <div v-if="msg.actionResult" class="pending-action-result">{{ msg.actionResult }}</div>
          <div v-if="msg.actionReportId" class="report-preview-actions"><el-button link type="primary" @click="$emit('openReportDetail', msg.actionReportId)">查看报告详情</el-button><el-button v-if="msg.actionReportPdf" link type="primary" @click="$emit('previewReportPdf', msg.actionReportId)">预览 PDF</el-button><el-button v-if="msg.actionReportPdf" link @click="$emit('downloadReportPdf', msg.actionReportId)">下载 PDF</el-button></div>
          <div v-if="msg.actionTrainingId" class="report-preview-actions"><el-button link type="primary" @click="$emit('openTrainingDetail', msg.actionTrainingId)">查看培训详情</el-button><a v-if="msg.actionTrainingUrl && trainingLinkPath(msg.actionTrainingUrl)" class="training-link" :href="trainingLinkPath(msg.actionTrainingUrl)" target="_blank" rel="noopener">打开学习页 ↗</a></div>
        </div>

        <!-- Tool trace -->
        <div v-if="msg.toolTrace && msg.toolTrace.length > 0" class="trace-section">
          <el-collapse>
            <el-collapse-item name="trace">
              <template #title>
                <div class="trace-title">
                  <el-icon><Operation /></el-icon>
                  <span>查看查询过程 · {{ msg.toolTrace.length }} 次工具调用</span>
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
import { learningPath as learningPathValue } from '@/utils/deployment'
import type { ChatEvidence, GuidedSelection, GuidedSelectionOption, PendingAction, PendingActionStatus, ReportPreview, TrainingPreview, ToolTraceItem } from '@/types/contract'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  evidence?: ChatEvidence[]
  knowledgeCitations?: import('@/types/contract').KnowledgeCitation[]
  reportPreviews?: ReportPreview[]
  reportCount?: number
  trainingPreviews?: TrainingPreview[]
  trainingCount?: number
  toolTrace?: ToolTraceItem[]
  degraded?: boolean
  errorCode?: string | null
  retryQuestion?: string
  pendingAction?: PendingAction
  guidedSelection?: GuidedSelection
  actionBusy?: boolean
  actionResult?: string
  actionReportId?: string
  actionReportPdf?: boolean
  actionTrainingId?: string
  actionTrainingUrl?: string
}

const props = defineProps<{
  msg: ChatMessage
  thinking: boolean
  showEvidence: boolean
  assistantName: string
}>()

defineEmits<{
  selectPrompt: [question: string]
  viewEvidence: [ev: ChatEvidence]
  selectGuidedTarget: [msg: ChatMessage, option: GuidedSelectionOption]
  confirmAction: [msg: ChatMessage]
  cancelAction: [msg: ChatMessage]
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

function degradedTitle(code?: string | null): string {
  if (code === 'REQUEST_TIMEOUT') return '回答等待超时'
  if (code === 'REQUEST_SERVER_ERROR') return '服务暂时无法完成请求'
  if (code === 'REQUEST_FAILED') return '暂时无法连接服务'
  if (code === 'UNSUPPORTED_STANDARD_REFERENCE') return '规范依据不足，请核对原文'
  if (code === 'STANDARDS_RETRIEVAL_FAILED') return '规范资料暂时无法检索'
  return '回答未完整完成，请核对依据'
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return new Date(utcStr).toLocaleTimeString()
}

function formatDateTime(utcStr: string): string {
  return new Date(utcStr).toLocaleString()
}

function reportDate(value: string, exclusiveEnd = false): string {
  const utcValue = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`
  const date = new Date(new Date(utcValue).getTime() - (exclusiveEnd ? 1 : 0))
  return date.toLocaleDateString('zh-CN', { timeZone: import.meta.env.VITE_LEARNING_TIMEZONE || 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' })
}

function actionStatusText(status: PendingActionStatus): string {
  return ({ PENDING: '等待确认', EXECUTING: '执行中', EXECUTED: '已执行', CANCELLED: '已取消', EXPIRED: '已过期', FAILED: '执行失败' } as Record<PendingActionStatus, string>)[status]
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