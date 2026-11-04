<template>
  <div class="copilot-page">
    <ErrorBoundary>
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
          <WelcomePanel v-if="!hasUserMessages" :thinking="thinking" @select-prompt="selectPrompt" />

          <ChatMessage
            v-for="(msg, idx) in visibleMessages"
            :key="idx"
            :msg="msg"
            :thinking="thinking"
            :show-evidence="uiConfig?.show_evidence !== false"
            :assistant-name="uiConfig?.assistant_name || '智能助手'"
            @select-prompt="selectPrompt"
            @view-evidence="viewEvidence"
            @select-guided-target="selectGuidedTarget"
            @confirm-action="confirmAction"
            @cancel-action="cancelAction"
            @open-report-detail="openReportDetail"
            @preview-report-pdf="previewReportPdf"
            @download-report-pdf="downloadReportPdf"
            @open-training-detail="openTrainingDetail"
          />

          <ThinkingIndicator v-if="thinking" :wait-seconds="waitSeconds" :assistant-name="uiConfig?.assistant_name || '智能助手'" />
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

      <!-- 侧边栏 -->
      <aside class="copilot-aside" aria-label="安全教育工作流">
        <section class="education-guide"><span class="guide-icon"><el-icon><Document /></el-icon></span><span class="section-kicker">连接学习中心</span><h3>让风险有跟进，<br />让学习有依据。</h3><p>将现场问题带入安全报告，再通过案例与规范组织培训。</p><router-link to="/learning">打开安全教育工作台 <span>↗</span></router-link></section>
        <section class="workflow-card"><span class="section-kicker">建议工作顺序</span><h3>把问题落到行动</h3><ol><li><b>01</b><div><strong>了解现场风险</strong><span>查询事件、摄像头与当前天气</span></div></li><li><b>02</b><div><strong>核对证据和资料</strong><span>查看快照与已检索的规范引用</span></div></li><li><b>03</b><div><strong>衔接报告与培训</strong><span>确认方案后，跟进学习任务</span></div></li></ol><router-link to="/violations">查看违规事件 →</router-link></section>
        <p class="aside-note">天气查询提供当前状况；全天预报和预警需另行核实。规范依据以回答中的文档引用为准。</p>
      </aside>
      </div>

      <!-- 证据弹窗 -->
      <EvidenceModal v-model="modalVisible" :record="selectedViolation" />

      <!-- 报告详情对话框 -->
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

      <!-- 培训详情对话框 -->
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

      <!-- 整改对话框 -->
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

      <!-- 培训设置对话框 -->
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
    </ErrorBoundary>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { cancelPendingAction, confirmPendingAction, getAgentConversationId, proposeTrainingAction, sendChatMessage } from '@/api/chat'
import * as learningApi from '@/api/learning'
import { fetchAssistantUiConfig } from '@/api/uiConfig'
import { learningPath } from '@/utils/deployment'
import type { AssistantUiConfig, ChatEvidence, GuidedSelection, GuidedSelectionOption, PendingAction, ReportPreview, TrainingPreview, ToolTraceItem, ViolationRecord } from '@/types/contract'
import ChatMessage from '@/components/ChatMessage.vue'
import WelcomePanel from '@/components/WelcomePanel.vue'
import ThinkingIndicator from '@/components/ThinkingIndicator.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import EvidenceModal from '@/components/EvidenceModal.vue'

interface ChatMessageItem {
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

const scrollRef = ref<HTMLDivElement | null>(null)
const inputQuestion = ref('')
const thinking = ref(false)
const waitSeconds = ref(0)
let waitTimer: ReturnType<typeof setInterval> | undefined

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

const messages = reactive<ChatMessageItem[]>([])
const hasUserMessages = computed(() => messages.some(message => message.role === 'user'))
const visibleMessages = computed(() => hasUserMessages.value ? messages : [])

const chatHistoryKey = 'agent_chat_messages'

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

function selectGuidedTarget(msg: ChatMessageItem, option: GuidedSelectionOption) {
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

async function confirmAction(msg: ChatMessageItem) {
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

async function cancelAction(msg: ChatMessageItem) {
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

function getConversationId(): string {
  return getAgentConversationId()
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
/* Sidebar */
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
/* Dialog content styles */
.report-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-detail-head strong { font-size: 14px; color: #303b51; }
.report-detail-text { line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.report-citation { font-size: 12px; color: #718096; border-left: 2px solid #aea6df; padding-left: 9px; }
.training-link { color: #5b55bb; font-size: 12px; font-weight: 600; text-decoration: none; }
.training-link:hover { text-decoration: underline; }
.training-detail-stats { padding: 10px 12px; background: #f0f3ff; border-radius: 9px; color: #555cac; font-size: 13px; }
.training-question { padding: 14px 0; border-top: 1px solid #e7eaf0; }
.training-question strong { display: block; margin-bottom: 8px; }
.training-question p { margin: 4px 0 4px 16px; }
.training-question .correct-option { color: #278263; font-weight: 600; }
.training-question small { display: block; color: #7a8596; margin-top: 8px; }
.training-access { display: flex; align-items: center; gap: 20px; margin-top: 18px; }
.training-access img { width: 150px; height: 150px; object-fit: contain; }
/* Quick prompts & input */
.quick-prompts {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 22px 0;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.prompt-hint { font-size: 12px; color: #64748b; }
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
.prompt-chip:hover { border-color: #c8b9e5; color: #7861ad; }
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
.section-kicker { display: block; color: #9b8abc; font-size: 11px; letter-spacing: .5px; }
/* Responsive */
.copilot-page button:disabled { cursor: default; opacity: .6; }
.copilot-page a:focus-visible, .copilot-page button:focus-visible { outline: 2px solid #9b86d2; outline-offset: 3px; }
@media (max-width: 1180px) { .copilot-layout { grid-template-columns: minmax(0, 1fr) 240px; gap: 16px; } .education-guide, .workflow-card { padding: 22px 18px; } .chat-heading-note { display: none; } }
@media (max-width: 1000px) { .copilot-layout { grid-template-columns: minmax(0, 1fr); } .copilot-aside { display: none; } }
@media (max-width: 760px) { .copilot-page { padding: 4px 0 0; min-height: 520px; } .header-section { margin-bottom: 16px; align-items: flex-start; } .title-area h2 { font-size: 23px; } .subtitle { font-size: 11px; line-height: 1.7; } .learning-entry { font-size: 11px; padding: 9px 10px; margin-top: 18px; } .eyebrow { font-size: 9px; margin-bottom: 7px; } .chat-heading { padding: 16px; } .messages-scroll { padding: 20px 12px; } .quick-prompts { padding: 10px 14px 0; gap: 6px; } .input-area { padding: 12px 14px 14px; } .composer-footer > span { font-size: 9px; } }
@media (prefers-reduced-motion: reduce) { .prompt-chip { transition: none; } }
@media (max-width: 760px) { .title-area { flex: 1; min-width: 0; } }
</style>
