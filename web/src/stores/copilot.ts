import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  cancelPendingAction,
  confirmPendingAction,
  getAgentConversationId,
  sendChatMessageStream,
} from '@/api/chat'
import { getApiNotifier, getConfirmDialog, translateApiMessage } from '@/api/ports'
import { fetchAssistantUiConfig } from '@/api/uiConfig'
import { STORAGE_KEYS } from '@/config/runtime'
import { subscribeLocaleChange } from '@/i18n/localeDetect'
import type { ChatMessageItem } from '@/types/chat'
import type {
  ActionExecutionResponse,
  AssistantUiConfig,
  ChatStreamStage,
  PageContext,
} from '@/types/contract'
import { extractApiError } from '@/utils/errors'
import { readJsonStorage, removeStorage, writeJsonStorage } from '@/utils/storage'

export type CopilotOutcome = 'idle' | 'success' | 'error'

export const useCopilotStore = defineStore('copilot', () => {
  const inputQuestion = ref('')
  const thinking = ref(false)
  const thinkingStage = ref<ChatStreamStage | null>(null)
  const activeToolName = ref<string | null>(null)
  const activeToolPurpose = ref<string | null>(null)
  const waitSeconds = ref(0)
  const uiConfig = ref<AssistantUiConfig | null>(null)
  const quickQuestions = ref<string[]>([])
  const messages = reactive<ChatMessageItem[]>([])
  const messageVersion = ref(0)
  const lastOutcome = ref<CopilotOutcome>('idle')
  const pageContext = ref<PageContext | null>(null)

  let initialized = false
  let waitTimer: ReturnType<typeof setInterval> | undefined

  const hasUserMessages = computed(() => messages.some((message) => message.role === 'user'))
  const visibleMessages = computed(() => (hasUserMessages.value ? messages : []))
  const hasPendingAction = computed(() =>
    messages.some((message) => message.pendingAction?.status === 'PENDING'),
  )
  const lastAssistantMessage = computed<ChatMessageItem | null>(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const item = messages[i]
      if (item && item.role === 'assistant') return item
    }
    return null
  })

  function stopWaitTimer(): void {
    if (waitTimer) {
      clearInterval(waitTimer)
      waitTimer = undefined
    }
  }

  function saveMessages(): void {
    writeJsonStorage(STORAGE_KEYS.agentChatMessages, messages, 'session')
  }

  function restoreMessages(): void {
    const saved = readJsonStorage<ChatMessageItem[]>(STORAGE_KEYS.agentChatMessages, 'session')
    if (Array.isArray(saved) && saved.length > 0) {
      messages.splice(0, messages.length, ...saved)
      messageVersion.value += 1
    } else if (saved !== null) {
      removeStorage(STORAGE_KEYS.agentChatMessages, 'session')
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

  function init(): void {
    if (initialized) return
    initialized = true
    getAgentConversationId()
    restoreMessages()
    loadUiConfig()

    subscribeLocaleChange(() => {
      loadUiConfig()
    })
  }

  function setPageContext(next: PageContext | null): void {
    pageContext.value = next
  }

  function appendAssistantMessage(message: ChatMessageItem): void {
    messages.push(message)
    messageVersion.value += 1
    saveMessages()
  }

  function actionResultText(result: ActionExecutionResponse): string {
    if (result.result.report_id) {
      return translateApiMessage('copilot.resultReport', {
        id: result.result.report_id,
        status: result.result.status || '-',
      })
    }
    if (result.result.training_id) {
      return translateApiMessage('copilot.resultTraining', {
        id: result.result.training_id,
        status: result.result.status || '-',
      })
    }
    if (result.result.task_id) {
      return translateApiMessage('copilot.resultTask', {
        id: result.result.task_id,
        status: result.result.status || '-',
      })
    }
    if (result.result.camera_id) {
      return translateApiMessage('copilot.resultCamera', {
        id: result.result.camera_id,
        state: result.result.desired_state || '-',
      })
    }
    return result.idempotent
      ? translateApiMessage('copilot.resultIdempotent')
      : translateApiMessage('copilot.resultDone')
  }

  async function handleSend(overrideQuestion?: string): Promise<void> {
    init()
    const explicitQuestion = typeof overrideQuestion === 'string' ? overrideQuestion : undefined
    const question = (explicitQuestion ?? inputQuestion.value).trim()
    if (!question || thinking.value) return

    messages.push({ role: 'user', text: question })
    messageVersion.value += 1
    saveMessages()
    if (explicitQuestion === undefined) {
      inputQuestion.value = ''
    }
    thinking.value = true
    thinkingStage.value = 'retrieving_standards'
    activeToolName.value = null
    activeToolPurpose.value = null
    lastOutcome.value = 'idle'
    waitSeconds.value = 0
    stopWaitTimer()
    waitTimer = setInterval(() => {
      waitSeconds.value += 1
    }, 1000)

    try {
      const res = await sendChatMessageStream(
        {
          question,
          conversation_id: getAgentConversationId(),
          page_context: pageContext.value,
        },
        (evt) => {
          thinkingStage.value = evt.stage
          activeToolName.value = evt.tool_name || null
          activeToolPurpose.value = evt.purpose || null
        },
      )

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
      messageVersion.value += 1
      lastOutcome.value = res.degraded ? 'error' : 'success'
      saveMessages()
    } catch (err: unknown) {
      const typed = err as { code?: string; response?: { status?: number } }
      const timedOut = ['ECONNABORTED', 'ETIMEDOUT'].includes(typed.code || '')
      const serverFailed = (typed.response?.status ?? 0) >= 500
      messages.push({
        role: 'assistant',
        text: timedOut
          ? translateApiMessage('copilot.timeoutErrorText')
          : serverFailed
            ? translateApiMessage('copilot.serverErrorText')
            : translateApiMessage('copilot.networkErrorText'),
        degraded: true,
        errorCode: timedOut ? 'REQUEST_TIMEOUT' : serverFailed ? 'REQUEST_SERVER_ERROR' : 'REQUEST_FAILED',
        retryQuestion: question,
      })
      messageVersion.value += 1
      lastOutcome.value = 'error'
      saveMessages()
    } finally {
      stopWaitTimer()
      thinking.value = false
      thinkingStage.value = null
      activeToolName.value = null
      activeToolPurpose.value = null
    }
  }

  function selectPrompt(question: string): void {
    if (thinking.value) return
    inputQuestion.value = question
    void handleSend()
  }

  async function confirmAction(msg: ChatMessageItem): Promise<void> {
    if (!msg.pendingAction || msg.actionBusy) return
    const confirmed = await getConfirmDialog()({
      title: translateApiMessage('copilot.confirmWriteTitle'),
      message: translateApiMessage('copilot.confirmWriteBody', { summary: msg.pendingAction.summary }),
      confirmText: translateApiMessage('copilot.confirmWriteOk'),
      cancelText: translateApiMessage('copilot.confirmWriteCancel'),
    })
    if (!confirmed) return
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
      lastOutcome.value = 'success'
      getApiNotifier().success?.(translateApiMessage('copilot.actionExecuted'))
    } catch (err: unknown) {
      lastOutcome.value = 'error'
      getApiNotifier().error(extractApiError(err, translateApiMessage('copilot.actionIncomplete')))
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
      msg.actionResult = translateApiMessage('copilot.actionCancelledText')
    } catch (err: unknown) {
      lastOutcome.value = 'error'
      getApiNotifier().error(extractApiError(err, translateApiMessage('copilot.cancelFailed')))
    } finally {
      msg.actionBusy = false
      saveMessages()
    }
  }

  return {
    inputQuestion,
    thinking,
    thinkingStage,
    activeToolName,
    activeToolPurpose,
    waitSeconds,
    uiConfig,
    quickQuestions,
    messages,
    messageVersion,
    lastOutcome,
    pageContext,
    hasUserMessages,
    visibleMessages,
    hasPendingAction,
    lastAssistantMessage,
    init,
    loadUiConfig,
    setPageContext,
    handleSend,
    selectPrompt,
    appendAssistantMessage,
    confirmAction,
    cancelAction,
  }
})
