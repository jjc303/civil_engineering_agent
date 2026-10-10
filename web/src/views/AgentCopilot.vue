<template>
  <div class="copilot-page">
    <header class="header-section">
      <div class="title-area">
        <span class="eyebrow">SAFETY COPILOT</span>
        <h2>{{ uiConfig?.assistant_name || '智能助手' }}</h2>
        <p class="subtitle">查询现场风险，核对安全依据，衔接报告与培训。</p>
      </div>
      <router-link to="/learning" class="learning-entry"><el-icon><Document /></el-icon>进入学习中心 ↗</router-link>
    </header>

    <!-- 问答主体区 -->
    <div class="copilot-layout">
    <div class="chat-container">
      <div class="chat-heading"><div><span class="assistant-dot" /><strong>安全咨询</strong><span class="chat-heading-note">现场 · 规范 · 教育</span></div><span class="session-label">{{ thinking ? '正在处理' : '当前会话' }}</span></div>
      <!-- 消息列表 -->
      <div class="messages-scroll" ref="scrollRef" role="log" aria-label="安全助手对话" :aria-busy="thinking">
        <section v-if="!hasUserMessages" class="welcome-panel">
          <span class="welcome-icon"><el-icon><Service /></el-icon></span>
          <span class="section-kicker">你的施工安全助手</span>
          <h3>从现场风险，到安全教育</h3>
          <p>从一个问题开始，查看现场数据、报告与培训任务。<br />涉及执行的操作，会先请你确认。</p>
          <div class="starter-grid">
            <button v-for="starter in starters" :key="starter.question" :disabled="thinking" @click="selectPrompt(starter.question)"><el-icon><component :is="starter.icon" /></el-icon><strong>{{ starter.title }}</strong><span>{{ starter.description }}</span><b aria-hidden="true">↗</b></button>
          </div>
        </section>
        <div v-for="(msg, idx) in visibleMessages" :key="idx" :class="['message-row', msg.role]">
          <!-- 头像 -->
          <div class="avatar">
            <el-avatar :icon="msg.role === 'user' ? UserFilled : Service" :size="36" />
          </div>

          <!-- 消息内容 -->
          <div class="message-content">
            <div class="sender-name">{{ msg.role === 'user' ? '用户' : (uiConfig?.assistant_name || '智能助手') }}</div>

            <!-- 用户气泡 -->
            <div v-if="msg.role === 'user'" class="user-bubble">
              {{ msg.text }}
            </div>

            <!-- 智能体回答气泡 -->
            <div v-else class="agent-bubble">
              <!-- 降级提醒 -->
              <el-alert
                v-if="msg.degraded"
                :title="degradedTitle(msg.errorCode)"
                type="warning"
                show-icon
                :closable="false"
                style="margin-bottom: 12px"
              />

              <!-- Markdown 渲染的主回答 -->
              <div class="markdown-body" v-html="renderMarkdown(msg.text)"></div>
              <button v-if="msg.retryQuestion" class="retry-question" :disabled="thinking" @click="selectPrompt(msg.retryQuestion)">重新提问 ↗</button>

              <section v-if="msg.reportPreviews?.length" class="report-previews" aria-label="安全报告预览">
                <div class="report-previews-heading"><strong>安全报告预览</strong><span>共 {{ msg.reportCount ?? msg.reportPreviews.length }} 份</span></div>
                <article v-for="report in msg.reportPreviews" :key="report.report_id" class="report-preview-card">
                  <div class="report-preview-top"><strong>{{ reportDate(report.period_start_utc) }} — {{ reportDate(report.period_end_utc, true) }} 安全报告</strong><el-tag size="small" :type="report.status === 'CONFIRMED' ? 'success' : 'warning'">{{ report.status === 'CONFIRMED' ? '已确认' : '草稿' }}</el-tag></div>
                  <div class="report-preview-meta">{{ report.event_count }} 条有效违规事件</div>
                  <p>{{ report.summary || '暂无报告摘要' }}</p>
                  <div class="report-preview-actions"><el-button link type="primary" @click="openReportDetail(report.report_id)">查看报告详情</el-button><el-button v-if="report.pdf_url" link type="primary" @click="previewReportPdf(report.report_id)">预览 PDF</el-button><el-button v-if="report.pdf_url" link @click="downloadReportPdf(report.report_id)">下载 PDF</el-button></div>
                </article>
                <router-link v-if="(msg.reportCount ?? 0) > msg.reportPreviews.length" to="/learning" class="report-more">前往学习中心查看全部报告 →</router-link>
              </section>

              <section v-if="msg.trainingPreviews?.length" class="report-previews" aria-label="培训任务预览">
                <div class="report-previews-heading"><strong>培训任务预览</strong><span>共 {{ msg.trainingCount ?? msg.trainingPreviews.length }} 项</span></div>
                <article v-for="training in msg.trainingPreviews" :key="training.training_id" class="report-preview-card">
                  <div class="report-preview-top"><strong>{{ training.title }}</strong><el-tag size="small" :type="training.status === 'PUBLISHED' ? 'success' : 'warning'">{{ training.status === 'PUBLISHED' ? '已发布' : '草稿' }}</el-tag></div>
                  <div class="report-preview-meta">目标 {{ training.target_count }} 人 · {{ training.question_count }} 道题</div>
                  <p>{{ training.material_preview || '暂无学习材料摘要' }}</p>
                  <div class="report-preview-actions"><el-button link type="primary" @click="openTrainingDetail(training.training_id)">查看培训详情</el-button><a v-if="training.public_url && learningPath(training.public_url)" class="training-link" :href="learningPath(training.public_url)" target="_blank" rel="noopener">打开学习页 ↗</a></div>
                </article>
                <router-link v-if="(msg.trainingCount ?? 0) > msg.trainingPreviews.length" to="/learning" class="report-more">前往学习中心查看全部培训 →</router-link>
              </section>

              <!-- 证据卡片区 -->
              <div v-if="uiConfig?.show_evidence !== false && msg.evidence && msg.evidence.length > 0" class="evidence-section">
                <div class="evidence-header">
                  <el-icon><Picture /></el-icon>
                  <span>关联证据快照 ({{ msg.evidence.length }} 项):</span>
                </div>
                <div class="evidence-grid">
                  <div
                    v-for="(ev, eIdx) in msg.evidence"
                    :key="eIdx"
                    class="evidence-card"
                    @click="viewEvidence(ev)"
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

              <div v-if="msg.knowledgeCitations && msg.knowledgeCitations.length > 0" class="evidence-section">
                <div class="evidence-header"><el-icon><Document /></el-icon><span>知识资料引用 ({{ msg.knowledgeCitations.length }} 项):</span></div>
                <div v-for="citation in msg.knowledgeCitations" :key="citation.chunk_id" class="tool-item">
                  <span>{{ citation.document_type === 'STANDARD' ? '规范' : '事故报告' }}：{{ citation.title }}（v{{ citation.version_no }}，{{ citation.page_or_section }}）<small v-if="citation.source_label"> · {{ citation.source_label }}</small></span>
                  <el-tag size="small" type="info">相关度 {{ citation.relevance_score.toFixed(2) }}</el-tag>
                </div>
              </div>

              <div v-if="msg.guidedSelection" class="guided-selection">
                <div class="guided-selection-title">请选择操作目标</div>
                <div class="guided-selection-prompt">{{ msg.guidedSelection.prompt }}</div>
                <div v-if="msg.guidedSelection.options.length" class="guided-selection-options">
                  <el-button
                    v-for="option in msg.guidedSelection.options"
                    :key="option.option_id"
                    plain
                    @click="selectGuidedTarget(msg, option)"
                  >
                    <span>{{ option.label }}</span><small>{{ option.description }}</small>
                  </el-button>
                </div>
                <el-button v-else-if="msg.guidedSelection.kind === 'TRAINING_REPORT'" type="primary" plain size="small" @click="selectPrompt('生成本周安全报告')">生成本周安全报告</el-button>
              </div>

              <div v-if="msg.pendingAction" class="pending-action">
                <div class="pending-action-title">请确认后执行</div>
                <div class="pending-action-summary">{{ msg.pendingAction.summary }}</div>
                <div class="pending-action-meta">
                  <el-tag :type="actionTagType(msg.pendingAction.status)" size="small">{{ actionStatusText(msg.pendingAction.status) }}</el-tag>
                  <span v-if="msg.pendingAction.status === 'PENDING'">有效期至 {{ formatDateTime(msg.pendingAction.expires_at_utc) }}</span>
                </div>
                <div v-if="msg.pendingAction.status === 'PENDING'" class="pending-action-buttons">
                  <el-button size="small" type="primary" :loading="msg.actionBusy" @click="confirmAction(msg)">确认执行</el-button>
                  <el-button size="small" :disabled="msg.actionBusy" @click="cancelAction(msg)">取消</el-button>
                </div>
                <div v-if="msg.actionResult" class="pending-action-result">{{ msg.actionResult }}</div>
                <div v-if="msg.actionReportId" class="report-preview-actions"><el-button link type="primary" @click="openReportDetail(msg.actionReportId)">查看报告详情</el-button><el-button v-if="msg.actionReportPdf" link type="primary" @click="previewReportPdf(msg.actionReportId)">预览 PDF</el-button><el-button v-if="msg.actionReportPdf" link @click="downloadReportPdf(msg.actionReportId)">下载 PDF</el-button></div>
                <div v-if="msg.actionTrainingId" class="report-preview-actions"><el-button link type="primary" @click="openTrainingDetail(msg.actionTrainingId)">查看培训详情</el-button><a v-if="msg.actionTrainingUrl && learningPath(msg.actionTrainingUrl)" class="training-link" :href="learningPath(msg.actionTrainingUrl)" target="_blank" rel="noopener">打开学习页 ↗</a></div>
              </div>

              <!-- 智能体执行链路 (Tool Trace) -->
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

        <!-- 思考中指示器 -->
        <div v-if="thinking" class="message-row assistant">
          <div class="avatar">
            <el-avatar :icon="Service" :size="36" />
          </div>
          <div class="message-content">
            <div class="sender-name">{{ uiConfig?.assistant_name || '智能助手' }}</div>
            <div class="agent-bubble thinking-bubble">
              <el-icon class="is-loading"><Loading /></el-icon>
              <div><strong>{{ waitSeconds >= 20 ? '回答仍在准备中，请稍候' : '正在查询并整理回答' }}</strong><small>已等待 {{ waitSeconds }} 秒{{ waitSeconds >= 20 ? ' · 模型和工具查询可能需要一些时间，请勿重复提交。' : ' · 完成后会显示在这里。' }}</small></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷提问推荐 -->
      <div class="quick-prompts">
        <span v-if="quickQuestions.length" class="prompt-hint">快捷提问：</span>
        <button
          v-for="(q, qIdx) in quickQuestions"
          :key="qIdx"
          class="prompt-chip"
          :disabled="thinking"
          @click="selectPrompt(q)"
        >
          {{ q }}
        </button>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <el-input
          v-model="inputQuestion"
          :placeholder="uiConfig?.input_placeholder || '例如：查看本周安全报告，或查询长沙当前天气'"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          aria-label="输入安全问题"
          :disabled="thinking"
          @keydown.enter="handleComposerEnter"
        />
        <div class="composer-footer"><span>Enter 发送 · Shift + Enter 换行</span><el-button type="primary" :loading="thinking" :disabled="!inputQuestion.trim() && !thinking" @click="handleSend">{{ thinking ? '正在处理' : '发送提问' }} <span v-if="!thinking" aria-hidden="true">↗</span></el-button></div>
      </div>
    </div>
    <aside class="copilot-aside" aria-label="安全教育工作流">
      <section class="education-guide"><span class="guide-icon"><el-icon><Document /></el-icon></span><span class="section-kicker">连接学习中心</span><h3>让风险有跟进，<br />让学习有依据。</h3><p>将现场问题带入安全报告，再通过案例与规范组织培训。</p><router-link to="/learning">打开安全教育工作台 <span>↗</span></router-link></section>
      <section class="workflow-card"><span class="section-kicker">建议工作顺序</span><h3>把问题落到行动</h3><ol><li><b>01</b><div><strong>了解现场风险</strong><span>查询事件、摄像头与当前天气</span></div></li><li><b>02</b><div><strong>核对证据和资料</strong><span>查看快照与已检索的规范引用</span></div></li><li><b>03</b><div><strong>衔接报告与培训</strong><span>确认方案后，跟进学习任务</span></div></li></ol><router-link to="/violations">查看违规事件 →</router-link></section>
      <p class="aside-note">天气查询提供当前状况；全天预报和预警需另行核实。规范依据以回答中的文档引用为准。</p>
    </aside>
    </div>

    <!-- 证据弹窗 -->
    <EvidenceModal v-model="modalVisible" :record="selectedViolation" />

    <el-dialog v-model="reportDetailOpen" title="安全报告详情" width="800px" destroy-on-close>
      <div v-loading="reportLoading">
        <template v-if="selectedReport">
          <div class="report-detail-head"><strong>{{ reportDate(selectedReport.period_start_utc) }} — {{ reportDate(selectedReport.period_end_utc, true) }}</strong><el-tag :type="selectedReport.status === 'CONFIRMED' ? 'success' : 'warning'">{{ selectedReport.status === 'CONFIRMED' ? '已确认' : '草稿' }}</el-tag></div>
          <p>有效违规 {{ selectedReport.statistics.total }} 条 · 重复出现 {{ selectedReport.statistics.repeat_occurrences }} 次</p>
          <h4>总结</h4><p class="report-detail-text">{{ selectedReport.content.summary }}</p>
          <h4>风险分析</h4><p class="report-detail-text">{{ selectedReport.content.risk_analysis }}</p>
          <h4>整改建议</h4><p class="report-detail-text">{{ selectedReport.content.remediation }}</p>
          <template v-if="selectedReport.citations.length"><h4>规范引用</h4><p v-for="citation in selectedReport.citations" :key="citation.chunk_id" class="report-citation">{{ citation.title }} · {{ citation.page_or_section }}</p></template>
        </template>
      </div>
      <template #footer><el-button @click="reportDetailOpen = false">关闭</el-button><el-button v-if="selectedReport?.pdf_url" type="primary" @click="previewReportPdf(selectedReport.report_id)">预览 PDF</el-button></template>
    </el-dialog>

    <el-dialog v-model="trainingDetailOpen" title="培训任务详情" width="800px" destroy-on-close @closed="clearTrainingQr">
      <div v-loading="trainingLoading">
        <template v-if="selectedTraining">
          <div class="report-detail-head"><strong>{{ selectedTraining.title }}</strong><el-tag :type="selectedTraining.status === 'PUBLISHED' ? 'success' : 'warning'">{{ selectedTraining.status === 'PUBLISHED' ? '已发布' : '草稿' }}</el-tag></div>
          <p>目标 {{ selectedTraining.target_count }} 人 · {{ selectedTraining.question_count }} 道题 · 及格分 {{ selectedTraining.pass_score }}</p>
          <div v-if="trainingStats" class="training-detail-stats">已完成 {{ trainingStats.completed_count }}/{{ trainingStats.target_count }} 人 · 完成率 {{ trainingStats.completion_rate }}% · 平均分 {{ trainingStats.average_score }}</div>
          <h4>学习材料</h4><p class="report-detail-text">{{ selectedTraining.material }}</p>
          <h4>选择题</h4><div v-for="(question, index) in selectedTraining.questions" :key="index" class="training-question"><strong>{{ index + 1 }}. {{ question.stem }}</strong><p v-for="(option, optionIndex) in question.options" :key="optionIndex" :class="{ 'correct-option': optionIndex === question.answer }">{{ String.fromCharCode(65 + optionIndex) }}. {{ option }}</p><small v-if="question.evidence">出题依据：{{ question.evidence }}</small></div>
          <div v-if="selectedTraining.public_url" class="training-access"><img v-if="trainingQrUrl" :src="trainingQrUrl" alt="培训任务二维码" /><a v-if="learningPath(selectedTraining.public_url)" :href="learningPath(selectedTraining.public_url)" target="_blank" rel="noopener">打开工人学习页 ↗</a></div>
        </template>
      </div>
      <template #footer><el-button @click="trainingDetailOpen = false">关闭</el-button><router-link to="/learning" class="training-link" @click="trainingDetailOpen = false">前往学习中心管理 →</router-link></template>
    </el-dialog>

    <el-dialog v-model="rectificationDialogVisible" title="创建整改任务" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="已选违规">
          <el-input :model-value="selectedRectificationTarget?.label || ''" disabled />
        </el-form-item>
        <el-form-item label="整改要求" required>
          <el-input v-model="rectificationForm.title" placeholder="例如：立即补发并佩戴安全帽" />
        </el-form-item>
        <el-form-item label="负责人" required>
          <el-input v-model="rectificationForm.owner" placeholder="例如：张三" />
        </el-form-item>
        <el-form-item label="截止时间" required>
          <el-date-picker v-model="rectificationForm.dueAt" type="datetime" placeholder="选择截止时间" style="width: 100%" />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="rectificationForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rectificationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRectification">生成待确认操作</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="trainingSetupDialogVisible" title="生成培训任务" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="依据报告">
          <el-input :model-value="selectedTrainingReport?.label || ''" disabled />
        </el-form-item>
        <el-form-item label="培训主题" required>
          <el-input v-model="trainingSetupForm.title" maxlength="255" show-word-limit placeholder="例如：本周施工安全教育" />
        </el-form-item>
        <el-form-item label="目标人数" required>
          <el-input-number v-model="trainingSetupForm.targetCount" :min="1" :step="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="题目数量">
          <el-input-number v-model="trainingSetupForm.questionCount" :min="1" :max="20" :step="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="及格分">
          <el-input-number v-model="trainingSetupForm.passScore" :min="0" :max="100" :step="1" controls-position="right" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="trainingSetupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="trainingSetupBusy" @click="submitTrainingSetup">生成待确认操作</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled,
  Service,
  Picture,
  Document,
  Operation,
  Loading,
} from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { cancelPendingAction, confirmPendingAction, proposeTrainingAction, sendChatMessage } from '@/api/chat'
import * as learningApi from '@/api/learning'
import { fetchAssistantUiConfig } from '@/api/uiConfig'
import { resolveMediaUrl } from '@/api/client'
import type { AssistantUiConfig, ChatEvidence, GuidedSelection, GuidedSelectionOption, PendingAction, PendingActionStatus, ReportPreview, TrainingPreview, ToolTraceItem, ViolationRecord } from '@/types/contract'
import EvidenceModal from '@/components/EvidenceModal.vue'

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

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const scrollRef = ref<HTMLDivElement | null>(null)
const inputQuestion = ref('')
const thinking = ref(false)
const waitSeconds = ref(0)
let waitTimer: ReturnType<typeof setInterval> | undefined
const starters = [
  { title: '现场状态', description: '查看摄像头运行情况', question: '查看所有摄像头状态', icon: Picture },
  { title: '安全报告', description: '查阅已有风险总结', question: '查看安全报告', icon: Document },
  { title: '培训任务', description: '跟进安全教育安排', question: '查看培训任务', icon: Operation },
]

const modalVisible = ref(false)
const reportDetailOpen = ref(false)
const reportLoading = ref(false)
const selectedReport = ref<learningApi.Report | null>(null)
const trainingDetailOpen = ref(false)
const trainingLoading = ref(false)
const selectedTraining = ref<learningApi.Training | null>(null)
const trainingStats = ref<learningApi.TrainingStatistics | null>(null)
const trainingQrUrl = ref('')
const selectedViolation = ref<ViolationRecord | null>(null)
const rectificationDialogVisible = ref(false)
const selectedRectificationTarget = ref<GuidedSelectionOption | null>(null)
const rectificationForm = reactive({ title: '', owner: '', dueAt: null as Date | null, description: '' })
const trainingSetupDialogVisible = ref(false)
const trainingSetupBusy = ref(false)
const selectedTrainingReport = ref<GuidedSelectionOption | null>(null)
const trainingSetupForm = reactive({ title: '', targetCount: undefined as number | undefined, questionCount: 5, passScore: 80 })

const uiConfig = ref<AssistantUiConfig | null>(null)
const quickQuestions = ref<string[]>([])

const messages = reactive<ChatMessage[]>([])
const hasUserMessages = computed(() => messages.some(message => message.role === 'user'))
const visibleMessages = computed(() => hasUserMessages.value ? messages : [])

const chatHistoryKey = 'agent_chat_messages'

function renderMarkdown(content: string): string {
  return md.render(content || '')
}

function selectPrompt(q: string) {
  if (thinking.value) return
  inputQuestion.value = q
  handleSend()
}

function handleComposerEnter(event: KeyboardEvent) {
  if (event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  handleSend()
}

function degradedTitle(code?: string | null): string {
  if (code === 'REQUEST_TIMEOUT') return '回答等待超时'
  if (code === 'REQUEST_SERVER_ERROR') return '服务暂时无法完成请求'
  if (code === 'REQUEST_FAILED') return '暂时无法连接服务'
  if (code === 'UNSUPPORTED_STANDARD_REFERENCE') return '规范依据不足，请核对原文'
  if (code === 'STANDARDS_RETRIEVAL_FAILED') return '规范资料暂时无法检索'
  return '回答未完整完成，请核对依据'
}

function stopWaitTimer() {
  if (waitTimer) clearInterval(waitTimer)
  waitTimer = undefined
}

async function handleSend() {
  const q = inputQuestion.value.trim()
  if (!q || thinking.value) return

  messages.push({ role: 'user', text: q })
  saveMessages()
  inputQuestion.value = ''
  thinking.value = true
  waitSeconds.value = 0
  stopWaitTimer()
  waitTimer = setInterval(() => { waitSeconds.value += 1 }, 1000)
  scrollToBottom()

  try {
    const res = await sendChatMessage({
      question: q,
      conversation_id: getConversationId(),
    })

    messages.push({
      role: 'assistant',
      text: res.answer,
      evidence: res.evidence,
      knowledgeCitations: res.knowledge_citations,
      reportPreviews: res.report_previews,
      reportCount: res.report_count,
      trainingPreviews: res.training_previews,
      trainingCount: res.training_count,
      toolTrace: res.tool_trace,
      degraded: res.degraded,
      errorCode: res.error_code,
      pendingAction: res.pending_action || undefined,
      guidedSelection: res.guided_selection || undefined,
    })
    saveMessages()
  } catch (err: any) {
    const timedOut = ['ECONNABORTED', 'ETIMEDOUT'].includes(err.code)
    const serverFailed = err.response?.status >= 500
    messages.push({
      role: 'assistant',
      text: timedOut ? '等待回答超过 3 分钟。服务可能仍在处理，请稍后重新提问。涉及执行的操作，请先查看已有待确认卡片。' : serverFailed ? '后台暂时未能完成请求，请稍后再试。如果持续出现，请检查服务日志及磁盘剩余空间。' : '未能连接到助手服务，请检查网络和后台运行状态后重新提问。',
      degraded: true,
      errorCode: timedOut ? 'REQUEST_TIMEOUT' : serverFailed ? 'REQUEST_SERVER_ERROR' : 'REQUEST_FAILED',
      retryQuestion: q,
    })
    saveMessages()
  } finally {
    stopWaitTimer()
    thinking.value = false
    scrollToBottom()
  }
}

function selectGuidedTarget(msg: ChatMessage, option: GuidedSelectionOption) {
  if (msg.guidedSelection?.kind === 'CAMERA_TARGET' && option.follow_up_question) {
    inputQuestion.value = option.follow_up_question
    handleSend()
    return
  }
  if (msg.guidedSelection?.kind === 'TRAINING_REPORT') {
    selectedTrainingReport.value = option
    trainingSetupForm.title = '本期施工安全教育'
    trainingSetupForm.targetCount = undefined
    trainingSetupForm.questionCount = 5
    trainingSetupForm.passScore = 80
    trainingSetupDialogVisible.value = true
    return
  }
  selectedRectificationTarget.value = option
  rectificationForm.title = ''
  rectificationForm.owner = ''
  rectificationForm.dueAt = null
  rectificationForm.description = ''
  rectificationDialogVisible.value = true
}

async function submitTrainingSetup() {
  const report = selectedTrainingReport.value
  const title = trainingSetupForm.title.trim()
  const targetCount = trainingSetupForm.targetCount
  if (!report || !title || !targetCount || !Number.isInteger(targetCount) || targetCount < 1) {
    ElMessage.warning('请填写培训主题和目标人数')
    return
  }
  trainingSetupBusy.value = true
  try {
    const pending = await proposeTrainingAction(getConversationId(), {
      report_id: report.option_id,
      title,
      document_ids: [],
      target_count: targetCount,
      question_count: trainingSetupForm.questionCount,
      pass_score: trainingSetupForm.passScore,
    })
    trainingSetupDialogVisible.value = false
    messages.push({ role: 'assistant', text: '已根据选定报告生成培训待确认操作。请确认后生成草稿。', pendingAction: pending })
    saveMessages()
    scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '培训操作创建失败')
  } finally {
    trainingSetupBusy.value = false
  }
}

function submitRectification() {
  const target = selectedRectificationTarget.value
  if (!target || !rectificationForm.title.trim() || !rectificationForm.owner.trim() || !rectificationForm.dueAt) {
    ElMessage.warning('请填写整改要求、负责人和截止时间')
    return
  }
  const description = rectificationForm.description.trim() ? `，补充说明：${rectificationForm.description.trim()}` : ''
  inputQuestion.value = `创建整改任务：关联违规 ${target.option_id}，整改内容为 ${rectificationForm.title.trim()}，负责人 ${rectificationForm.owner.trim()}，截止 ${rectificationForm.dueAt.toISOString()}${description}`
  rectificationDialogVisible.value = false
  handleSend()
}

async function confirmAction(msg: ChatMessage) {
  if (!msg.pendingAction || msg.actionBusy) return
  try {
    await ElMessageBox.confirm(`将执行：${msg.pendingAction.summary}`, '确认执行写操作', {
      confirmButtonText: '确认执行', cancelButtonText: '返回', type: 'warning',
    })
  } catch {
    return
  }
  msg.actionBusy = true
  try {
    const result = await confirmPendingAction(msg.pendingAction.confirmation_id, getConversationId())
    msg.pendingAction.status = result.status
    msg.actionResult = actionResultText(result)
    if (result.result.report_id && result.result.status !== 'DELETED') {
      msg.actionReportId = result.result.report_id
      msg.actionReportPdf = Boolean(result.result.pdf_url)
    }
    if (result.result.training_id && result.result.status !== 'DELETED') {
      msg.actionTrainingId = result.result.training_id
      msg.actionTrainingUrl = result.result.public_url || undefined
    }
    ElMessage.success('操作已执行')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '操作未完成')
  } finally {
    msg.actionBusy = false
    saveMessages()
  }
}

async function cancelAction(msg: ChatMessage) {
  if (!msg.pendingAction || msg.actionBusy) return
  msg.actionBusy = true
  try {
    const result = await cancelPendingAction(msg.pendingAction.confirmation_id, getConversationId())
    msg.pendingAction.status = result.status
    msg.actionResult = '已取消，未执行任何写操作。'
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '取消失败')
  } finally {
    msg.actionBusy = false
    saveMessages()
  }
}

function actionResultText(result: import('@/types/contract').ActionExecutionResponse): string {
  if (result.result.report_id) return `已执行：安全报告 ${result.result.report_id}，状态 ${result.result.status || '-'}。`
  if (result.result.training_id) return `已执行：培训任务 ${result.result.training_id}，状态 ${result.result.status || '-'}。`
  if (result.result.task_id) return `已执行：整改任务 ${result.result.task_id}，当前状态 ${result.result.status || '-'}。`
  if (result.result.camera_id) return `已执行：摄像头 ${result.result.camera_id} 当前为 ${result.result.desired_state || '-'}。`
  return result.idempotent ? '该操作此前已执行。' : '操作已执行。'
}

function actionStatusText(status: PendingActionStatus): string {
  return ({ PENDING: '等待确认', EXECUTING: '执行中', EXECUTED: '已执行', CANCELLED: '已取消', EXPIRED: '已过期', FAILED: '执行失败' } as Record<PendingActionStatus, string>)[status]
}

function actionTagType(status: PendingActionStatus): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  return ({ PENDING: 'warning', EXECUTING: 'primary', EXECUTED: 'success', CANCELLED: 'info', EXPIRED: 'info', FAILED: 'danger' } as Record<PendingActionStatus, 'primary' | 'success' | 'warning' | 'info' | 'danger'>)[status]
}

function getConversationId(): string {
  const key = 'agent_conversation_id'
  const existing = sessionStorage.getItem(key)
  if (existing) return existing
  const created = crypto.randomUUID()
  sessionStorage.setItem(key, created)
  return created
}

function saveMessages() {
  // Browser-session display history is intentionally separate from the
  // server-side 24-hour summarized context and never leaves this tab.
  sessionStorage.setItem(chatHistoryKey, JSON.stringify(messages))
}

function restoreMessages() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(chatHistoryKey) || '[]')
    if (Array.isArray(saved) && saved.length > 0) {
      messages.splice(0, messages.length, ...saved)
    }
  } catch {
    sessionStorage.removeItem(chatHistoryKey)
  }
}

function viewEvidence(ev: ChatEvidence) {
  selectedViolation.value = {
    event_uuid: ev.event_uuid,
    camera_id: '证据快照',
    monitor_session_id: '-',
    track_id: 0,
    violation_type: 'NO_HELMET',
    severity: 'INFO',
    status: 'ACTIVE',
    zone_id: null,
    zone_name: null,
    occurred_at_utc: ev.occurred_at_utc,
    resolved_at_utc: null,
    duration_seconds: 0,
    snapshot_uri: ev.snapshot_uri,
    model_name: null,
    model_version: null,
    extra_details: {},
  }
  modalVisible.value = true
}

function reportDate(value: string, exclusiveEnd = false): string {
  const utcValue = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`
  const date = new Date(new Date(utcValue).getTime() - (exclusiveEnd ? 1 : 0))
  return date.toLocaleDateString('zh-CN', { timeZone: import.meta.env.VITE_LEARNING_TIMEZONE || 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' })
}

async function openReportDetail(id: string) {
  reportDetailOpen.value = true
  reportLoading.value = true
  selectedReport.value = null
  try {
    selectedReport.value = await learningApi.getReport(id)
  } catch {
    ElMessage.error('报告详情加载失败')
  } finally {
    reportLoading.value = false
  }
}

async function previewReportPdf(id: string) {
  const tab = window.open('', '_blank')
  if (!tab) return ElMessage.warning('浏览器阻止了新标签页，请使用下载 PDF')
  try {
    const url = URL.createObjectURL(await learningApi.downloadReport(id))
    tab.location.href = url
    window.setTimeout(() => URL.revokeObjectURL(url), 300000)
  } catch {
    tab.close()
    ElMessage.error('PDF 预览失败')
  }
}

async function downloadReportPdf(id: string) {
  try {
    const url = URL.createObjectURL(await learningApi.downloadReport(id))
    const link = document.createElement('a')
    link.href = url
    link.download = `safety-report-${id}.pdf`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch {
    ElMessage.error('PDF 下载失败')
  }
}

function learningPath(publicUrl: string): string | undefined {
  try {
    const path = new URL(publicUrl).pathname
    return /^\/learn\/[A-Za-z0-9_-]+\/?$/.test(path) ? path : undefined
  } catch {
    return undefined
  }
}

function clearTrainingQr() {
  if (trainingQrUrl.value) URL.revokeObjectURL(trainingQrUrl.value)
  trainingQrUrl.value = ''
}

async function openTrainingDetail(id: string) {
  clearTrainingQr()
  selectedTraining.value = null
  trainingStats.value = null
  trainingDetailOpen.value = true
  trainingLoading.value = true
  try {
    const task = await learningApi.getTraining(id)
    if (!trainingDetailOpen.value) return
    selectedTraining.value = task
    if (task.status === 'PUBLISHED') {
      const [statistics, qr] = await Promise.allSettled([learningApi.getTrainingStats(id), learningApi.getTrainingQr(id)])
      if (!trainingDetailOpen.value || selectedTraining.value?.task_id !== id) return
      if (statistics.status === 'fulfilled') trainingStats.value = statistics.value
      if (qr.status === 'fulfilled') trainingQrUrl.value = URL.createObjectURL(qr.value)
    }
  } catch {
    ElMessage.error('培训详情加载失败')
  } finally {
    trainingLoading.value = false
  }
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return new Date(utcStr).toLocaleTimeString()
}

function formatDateTime(utcStr: string): string {
  return new Date(utcStr).toLocaleString()
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  getConversationId()
  restoreMessages()
  fetchAssistantUiConfig().then((config) => {
    uiConfig.value = config
    quickQuestions.value = config.quick_questions
  }).catch(() => undefined)
  if (hasUserMessages.value) scrollToBottom()
})
onUnmounted(() => { clearTrainingQr(); stopWaitTimer() })
</script>

<style scoped>
.copilot-page {
  --el-color-primary: #7563d4;
  --el-color-primary-light-3: #9b8dde;
  --el-color-primary-light-5: #bab0ea;
  --el-color-primary-light-7: #d7d0f4;
  --el-color-primary-light-9: #f2effb;
  --el-color-primary-dark-2: #6150b5;
  padding: 8px 8px 0;
  display: flex;
  flex-direction: column;
  max-width: 1440px;
  margin: 0 auto;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  color: #39425b;
}
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 26px;
}
.eyebrow { display: block; color: #9382ca; font-size: 10px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px; }
.title-area h2 {
  margin: 0;
  font-size: 27px;
  color: #323a50;
  letter-spacing: -.6px;
}
.subtitle {
  margin: 10px 0 0;
  font-size: 13px;
  color: #8590a0;
}
.learning-entry { display: inline-flex; align-items: center; gap: 8px; padding: 11px 15px; background: #fff; border: 1px solid #e3ddf5; border-radius: 12px; font-size: 12px; color: #7563bf; text-decoration: none; white-space: nowrap; }
.learning-entry:hover { background: #f1edfb; }
.copilot-layout { display: grid; grid-template-columns: minmax(0, 1fr) 276px; gap: 22px; flex: 1; min-height: 0; }
.chat-container {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #ececf4;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 6px 24px #41336b03;
}
.chat-heading { display: flex; justify-content: space-between; gap: 12px; padding: 20px 24px; border-bottom: 1px solid #f0eef6; font-size: 13px; flex-shrink: 0; }
.chat-heading > div { display: flex; gap: 9px; align-items: center; }
.assistant-dot { width: 7px; height: 7px; border-radius: 50%; background: #9481d8; box-shadow: 0 0 0 4px #f1edfb; margin-right: 5px; }
.chat-heading-note, .session-label { font-size: 11px; color: #9a9eaf; }
.chat-heading-note { margin-left: 9px; }
.messages-scroll {
  flex: 1;
  min-height: 0;
  padding: 26px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  scrollbar-width: thin;
  scrollbar-color: #ded8ec transparent;
}
.welcome-panel { margin: auto 0; padding: 24px 8px 38px; text-align: center; flex-shrink: 0; }
.welcome-icon { display: grid; place-items: center; width: 62px; height: 62px; margin: 0 auto 22px; background: linear-gradient(140deg, #f1edfb, #faf8ff); border: 1px solid #e8e1f8; border-radius: 20px; color: #8972d0; font-size: 29px; }
.section-kicker { display: block; color: #9b8abc; font-size: 11px; letter-spacing: .5px; }
.welcome-panel h3 { font-size: 27px; margin: 12px 0; letter-spacing: -.6px; color: #3d4059; }
.welcome-panel p { font-size: 13px; line-height: 1.9; color: #8c94a4; margin: 0 0 26px; }
.starter-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; max-width: 670px; margin: 0 auto; }
.starter-grid button { position: relative; display: flex; flex-direction: column; gap: 8px; padding: 18px 15px; text-align: left; border: 1px solid #ebe6f4; background: #fdfcfe; border-radius: 14px; cursor: pointer; color: #5d526f; font: inherit; }
.starter-grid button > .el-icon { font-size: 20px; color: #9a86cc; margin-bottom: 6px; }
.starter-grid strong { font-size: 13px; font-weight: 600; }
.starter-grid span { font-size: 11px; color: #9b94a8; }
.starter-grid b { position: absolute; top: 17px; right: 16px; font-size: 13px; color: #b7a8cf; font-weight: 400; }
.starter-grid button:hover { border-color: #c9bbe9; background: #f6f2fd; }
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
.thinking-bubble {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #8873bb;
}
.thinking-bubble strong { font-size: 13px; font-weight: 500; }
.thinking-bubble small { display: block; font-size: 11px; color: #a29bad; }
.copilot-aside { display: flex; flex-direction: column; gap: 18px; overflow: auto; scrollbar-width: thin; }
.education-guide { padding: 26px 23px 24px; color: #fff; background: linear-gradient(148deg, #6355be, #8c77d8); border-radius: 20px; position: relative; overflow: hidden; }
.education-guide:after { content: ''; position: absolute; width: 170px; height: 170px; border: 1px solid #ffffff18; border-radius: 50%; top: -74px; right: -61px; pointer-events: none; }
.guide-icon { display: grid; place-items: center; width: 38px; height: 38px; background: #ffffff1a; border: 1px solid #ffffff26; border-radius: 12px; margin-bottom: 22px; font-size: 20px; }
.education-guide .section-kicker { color: #e0d9f5; }
.education-guide h3 { font-size: 22px; line-height: 1.5; letter-spacing: -.3px; margin: 12px 0; font-weight: 600; }
.education-guide p { font-size: 12px; line-height: 1.9; color: #e3def3; margin: 0 0 24px; }
.education-guide a { display: flex; justify-content: space-between; background: #ffffff18; color: #fff; text-decoration: none; font-size: 12px; padding: 12px 13px; border-radius: 10px; border: 1px solid #ffffff22; }
.education-guide a:hover { background: #ffffff28; }
.workflow-card { padding: 24px 22px; background: #fff; border: 1px solid #eeebf5; border-radius: 20px; }
.workflow-card h3 { font-size: 16px; font-weight: 600; margin: 10px 0 22px; }
.workflow-card ol { margin: 0; padding: 0; list-style: none; display: grid; gap: 22px; }
.workflow-card li { display: flex; gap: 12px; }
.workflow-card li > b { font-size: 11px; color: #a694c9; font-weight: 500; background: #f6f2fc; border-radius: 8px; padding: 7px; align-self: flex-start; }
.workflow-card strong { font-size: 12px; font-weight: 500; }
.workflow-card li span { display: block; margin-top: 5px; font-size: 11px; line-height: 1.6; color: #9a9fac; }
.workflow-card > a { display: block; margin-top: 24px; padding-top: 18px; border-top: 1px solid #f0edf6; font-size: 12px; color: #9380bd; text-decoration: none; }
.aside-note { margin: 0; padding: 0 10px 14px; font-size: 11px; line-height: 1.9; color: #aaa5b4; }
.education-guide, .workflow-card, .aside-note { flex-shrink: 0; }
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 10px;
  margin-bottom: 6px;
  color: #0f172a;
}
.markdown-body :deep(p) {
  margin: 6px 0;
}
.markdown-body :deep(ul) {
  padding-left: 20px;
  margin: 6px 0;
}
.report-previews{margin-top:16px;padding-top:14px;border-top:1px dashed #d8deea;display:grid;gap:10px}
.report-previews-heading,.report-preview-top,.report-detail-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.report-previews-heading strong{font-size:14px;color:#344054}
.report-previews-heading span,.report-preview-meta{font-size:12px;color:#7b8798}
.report-preview-card{padding:14px 16px;border:1px solid #e1e6f1;border-radius:12px;background:#fff;min-width:0}
.report-preview-top strong{font-size:14px;color:#303b51}
.report-preview-meta{margin-top:7px}
.report-preview-card p{margin:9px 0 10px;color:#526078;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
.report-preview-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.report-preview-actions .el-button{margin:0}
.report-more{font-size:12px;color:#5c58bd;text-decoration:none}
.report-detail-text{line-height:1.75;white-space:pre-wrap;overflow-wrap:anywhere}
.report-citation{font-size:12px;color:#718096;border-left:2px solid #aea6df;padding-left:9px}
.training-link{color:#5b55bb;font-size:12px;font-weight:600;text-decoration:none}.training-link:hover{text-decoration:underline}
.training-detail-stats{padding:10px 12px;background:#f0f3ff;border-radius:9px;color:#555cac;font-size:13px}
.training-question{padding:14px 0;border-top:1px solid #e7eaf0}.training-question strong{display:block;margin-bottom:8px}.training-question p{margin:4px 0 4px 16px}.training-question .correct-option{color:#278263;font-weight:600}.training-question small{display:block;color:#7a8596;margin-top:8px}
.training-access{display:flex;align-items:center;gap:20px;margin-top:18px}.training-access img{width:150px;height:150px;object-fit:contain}
.evidence-section {
  margin-top: 14px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
}
.evidence-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}
.evidence-grid {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.evidence-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.evidence-card:hover {
  border-color: #2563eb;
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.thumb-img {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border-radius: 4px;
  background: #0f172a;
}
.thumb-img :deep(img) { width: 100%; height: 100%; }
.evidence-info {
  display: flex;
  flex-direction: column;
  font-size: 11px;
}
.ev-time {
  color: #64748b;
}
.ev-uuid {
  color: #2563eb;
}
.trace-section {
  margin-top: 12px;
}
.pending-action {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  background: #fffbeb;
}
.pending-action-title { font-weight: 600; color: #92400e; }
.pending-action-summary { margin-top: 4px; color: #334155; }
.pending-action-meta { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 12px; color: #64748b; }
.pending-action-buttons { display: flex; gap: 8px; margin-top: 10px; }
.pending-action-result { margin-top: 8px; font-size: 12px; color: #475569; }
.guided-selection {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  background: #eff6ff;
}
.guided-selection-title { font-weight: 600; color: #1d4ed8; }
.guided-selection-prompt { margin-top: 4px; color: #334155; }
.guided-selection-options { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.guided-selection-options :deep(.el-button) { height: auto; min-height: 34px; text-align: left; display: flex; flex-direction: column; align-items: flex-start; }
.guided-selection-options small { color: #64748b; font-size: 11px; }
.trace-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}
.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.tool-name {
  font-weight: 600;
  color: #0f172a;
}
.tool-purpose {
  color: #64748b;
}
.font-mono {
  font-family: ui-monospace, monospace;
}
.quick-prompts {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 22px 0;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.prompt-hint {
  font-size: 12px;
  color: #64748b;
}
.prompt-chip {
  font: inherit;
  font-size: 11px;
  color: #8b7ca5;
  background: #faf8fd;
  border: 1px solid #ece5f5;
  border-radius: 8px;
  padding: 7px 9px;
  cursor: pointer;
  transition: all 0.2s;
}
.prompt-chip:hover {
  border-color: #c8b9e5;
  color: #7861ad;
}
.input-area {
  padding: 14px 22px 18px;
  background: #ffffff;
  flex-shrink: 0;
}
.input-area :deep(.el-textarea__inner) { padding: 14px 16px; border-radius: 12px; background: #faf9fc; box-shadow: 0 0 0 1px #e9e3f2 inset; resize: none; font-size: 13px; line-height: 1.7; }
.input-area :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #a18acd inset; }
.composer-footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-top: 12px; }
.composer-footer > span { font-size: 10px; color: #aaa4b3; }
.composer-footer :deep(.el-button) { border-radius: 10px; font-size: 12px; min-height: 35px; }
.composer-footer :deep(.el-button span) { gap: 12px; }
.markdown-body :deep(table) { display: block; overflow-x: auto; max-width: 100%; border-collapse: collapse; }
.markdown-body :deep(td), .markdown-body :deep(th) { border: 1px solid #e2dcec; padding: 6px 10px; }
.markdown-body :deep(pre) { overflow-x: auto; padding: 12px; border-radius: 8px; background: #f0ecf7; }
.markdown-body :deep(a) { color: #8064bd; }
.guided-selection { background: #f6f2fc; border-color: #d9ccef; border-radius: 12px; }
.guided-selection-title { color: #8270b0; }
.pending-action { border-radius: 12px; }
.tool-item { flex-wrap: wrap; }
.copilot-page button:disabled { cursor: default; opacity: .6; }
.copilot-page a:focus-visible, .copilot-page button:focus-visible { outline: 2px solid #9b86d2; outline-offset: 3px; }
@media (max-width: 1180px) { .copilot-layout { grid-template-columns: minmax(0, 1fr) 240px; gap: 16px; } .education-guide, .workflow-card { padding: 22px 18px; } .chat-heading-note { display: none; } }
@media (max-width: 1000px) { .copilot-layout { grid-template-columns: minmax(0, 1fr); } .copilot-aside { display: none; } }
@media (max-width: 760px) { .copilot-page { padding: 4px 0 0; min-height: 520px; } .header-section { margin-bottom: 16px; align-items: flex-start; } .title-area h2 { font-size: 23px; } .subtitle { font-size: 11px; line-height: 1.7; } .learning-entry { font-size: 11px; padding: 9px 10px; margin-top: 18px; } .eyebrow { font-size: 9px; margin-bottom: 7px; } .chat-heading { padding: 16px; } .messages-scroll { padding: 20px 12px; } .message-row { gap: 8px; max-width: 100%; } .agent-bubble { padding: 12px 14px; font-size: 13px; } .welcome-panel { padding: 10px 0 22px; } .welcome-panel h3 { font-size: 23px; } .welcome-panel p { font-size: 12px; } .starter-grid { gap: 7px; } .starter-grid button { padding: 13px 10px; } .starter-grid span { font-size: 10px; line-height: 1.6; } .starter-grid b { display: none; } .quick-prompts { padding: 10px 14px 0; gap: 6px; } .input-area { padding: 12px 14px 14px; } .composer-footer > span { font-size: 9px; } }
@media (prefers-reduced-motion: reduce) { .prompt-chip, .evidence-card { transition: none; } }
@media (max-width: 760px) { .title-area { flex: 1; min-width: 0; } }
@media (max-height: 800px) { .welcome-panel { padding-top: 2px; padding-bottom: 8px; } .welcome-icon { display: none; } .welcome-panel h3 { font-size: 22px; margin: 8px 0; } .welcome-panel p { margin-bottom: 16px; font-size: 12px; } .starter-grid button { padding: 13px; gap: 6px; } .starter-grid button > .el-icon { margin-bottom: 2px; } .header-section { margin-bottom: 18px; } }
</style>
