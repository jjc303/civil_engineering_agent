import { computed, nextTick, onMounted, onUnmounted, reactive, ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cancelPendingAction, confirmPendingAction, getAgentConversationId, sendChatMessage } from '@/api/chat'
import { fetchAssistantUiConfig } from '@/api/uiConfig'
import { STORAGE_KEYS } from '@/config/runtime'
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import type { ChatMessageItem } from '@/types/chat'
import type { ActionExecutionResponse, AssistantUiConfig } from '@/types/contract'
import { readJsonStorage, removeStorage, writeJsonStorage } from '@/utils/storage'

function extractApiError(err: unknown, fallback: string): string {
  const typed = err as { response?: { data?: { detail?: string }; status?: number }; message?: string }
  return typed?.response?.data?.detail || typed?.message || fallback
}

export function useCopilotSession(scrollRef: Ref<HTMLDivElement | null>) {
  const { t } = useAppI18n()

  const inputQuestion = ref('')
  const thinking = ref(false)
  const waitSeconds = ref(0)
  const uiConfig = ref<AssistantUiConfig | null>(null)
  const quickQuestions = ref<string[]>([])
  const messages = reactive<ChatMessageItem[]>([])

  const hasUserMessages = computed(() => messages.some((message) => message.role === 'user'))
  const visibleMessages = computed(() => (hasUserMessages.value ? messages : []))

  let waitTimer: ReturnType<typeof setInterval> | undefined

  function stopWaitTimer(): void {
    if (waitTimer) {
      clearInterval(waitTimer)
      waitTimer = undefined
    }
  }

  function scrollToBottom(): void {
    nextTick(() => {
      if (scrollRef.value) {
        scrollRef.value.scrollTop = scrollRef.value.scrollHeight
      }
    })
  }

  function saveMessages(): void {
    // Browser-session display history is intentionally separate from server-side context.
    writeJsonStorage(STORAGE_KEYS.agentChatMessages, messages, 'session')
  }

  function restoreMessages(): void {
    const saved = readJsonStorage<ChatMessageItem[]>(STORAGE_KEYS.agentChatMessages, 'session')
    if (Array.isArray(saved) && saved.length > 0) {
      messages.splice(0, messages.length, ...saved)
    } else if (saved !== null) {
      removeStorage(STORAGE_KEYS.agentChatMessages, 'session')
    }
  }

  function appendAssistantMessage(message: ChatMessageItem): void {
    messages.push(message)
    saveMessages()
    scrollToBottom()
  }

  function actionResultText(result: ActionExecutionResponse): string {
    if (result.result.report_id) return t('copilot.resultReport', { id: result.result.report_id, status: result.result.status || '-' })
    if (result.result.training_id) return t('copilot.resultTraining', { id: result.result.training_id, status: result.result.status || '-' })
    if (result.result.task_id) return t('copilot.resultTask', { id: result.result.task_id, status: result.result.status || '-' })
    if (result.result.camera_id) return t('copilot.resultCamera', { id: result.result.camera_id, state: result.result.desired_state || '-' })
    return result.idempotent ? t('copilot.resultIdempotent') : t('copilot.resultDone')
  }

  async function handleSend(): Promise<void> {
    const question = inputQuestion.value.trim()
    if (!question || thinking.value) return

    messages.push({ role: 'user', text: question })
    saveMessages()
    inputQuestion.value = ''
    thinking.value = true
    waitSeconds.value = 0
    stopWaitTimer()
    waitTimer = setInterval(() => {
      waitSeconds.value += 1
    }, 1000)
    scrollToBottom()

    try {
      const res = await sendChatMessage({
        question,
        conversation_id: getAgentConversationId(),
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
    } catch (err: unknown) {
      const typed = err as { code?: string; response?: { status?: number } }
      const timedOut = ['ECONNABORTED', 'ETIMEDOUT'].includes(typed.code || '')
      const serverFailed = (typed.response?.status ?? 0) >= 500
      messages.push({
        role: 'assistant',
        text: timedOut ? t('copilot.timeoutErrorText') : serverFailed ? t('copilot.serverErrorText') : t('copilot.networkErrorText'),
        degraded: true,
        errorCode: timedOut ? 'REQUEST_TIMEOUT' : serverFailed ? 'REQUEST_SERVER_ERROR' : 'REQUEST_FAILED',
        retryQuestion: question,
      })
      saveMessages()
    } finally {
      stopWaitTimer()
      thinking.value = false
      scrollToBottom()
    }
  }

  function selectPrompt(question: string): void {
    if (thinking.value) return
    inputQuestion.value = question
    void handleSend()
  }

  async function confirmAction(msg: ChatMessageItem): Promise<void> {
    if (!msg.pendingAction || msg.actionBusy) return
    try {
      await ElMessageBox.confirm(t('copilot.confirmWriteBody', { summary: msg.pendingAction.summary }), t('copilot.confirmWriteTitle'), {
        confirmButtonText: t('copilot.confirmWriteOk'),
        cancelButtonText: t('copilot.confirmWriteCancel'),
        type: 'warning',
      })
    } catch {
      return
    }
    msg.actionBusy = true
    try {
      const result = await confirmPendingAction(msg.pendingAction.confirmation_id, getAgentConversationId())
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
      ElMessage.success(t('copilot.actionExecuted'))
    } catch (err: unknown) {
      ElMessage.error(extractApiError(err, t('copilot.actionIncomplete')))
    } finally {
      msg.actionBusy = false
      saveMessages()
    }
  }

  async function cancelAction(msg: ChatMessageItem): Promise<void> {
    if (!msg.pendingAction || msg.actionBusy) return
    msg.actionBusy = true
    try {
      const result = await cancelPendingAction(msg.pendingAction.confirmation_id, getAgentConversationId())
      msg.pendingAction.status = result.status
      msg.actionResult = t('copilot.actionCancelledText')
    } catch (err: unknown) {
      ElMessage.error(extractApiError(err, t('copilot.cancelFailed')))
    } finally {
      msg.actionBusy = false
      saveMessages()
    }
  }

  function loadUiConfig(): void {
    fetchAssistantUiConfig()
      .then((config) => {
        uiConfig.value = config
        quickQuestions.value = config.quick_questions
      })
      .catch(() => undefined)
  }

  useLocaleRefresh(loadUiConfig)

  onMounted(() => {
    getAgentConversationId()
    restoreMessages()
    loadUiConfig()
    if (hasUserMessages.value) scrollToBottom()
  })

  onUnmounted(stopWaitTimer)

  return {
    inputQuestion,
    thinking,
    waitSeconds,
    uiConfig,
    quickQuestions,
    hasUserMessages,
    visibleMessages,
    handleSend,
    selectPrompt,
    appendAssistantMessage,
    confirmAction,
    cancelAction,
  }
}
