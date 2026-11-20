import { APP_CONFIG } from '@/config/runtime'
import { resolveActiveClientLocale } from '@/i18n/localeDetect'
import { apiBaseUrl } from '@/utils/deployment'
import { apiClient, CHAT_ENDPOINT } from '../client'
import type { ChatPort } from '../ports'
import type {
  ActionExecutionResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  PendingAction,
} from '@/types/contract'

function parseSseFrames(
  buffer: string,
  onFrame: (eventType: string, dataRaw: string) => void,
): string {
  const normalized = buffer.replace(/\r\n/g, '\n')
  let cursor = 0
  while (true) {
    const boundary = normalized.indexOf('\n\n', cursor)
    if (boundary === -1) break
    const block = normalized.slice(cursor, boundary)
    cursor = boundary + 2
    if (!block.trim() || block.startsWith(':')) continue
    let eventType = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    if (dataLines.length > 0) {
      onFrame(eventType, dataLines.join('\n'))
    }
  }
  return normalized.slice(cursor)
}

export const httpChatAdapter: ChatPort = {
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    const res = await apiClient.post<ChatResponse>(CHAT_ENDPOINT, request, {
      timeout: APP_CONFIG.chatTimeoutMs,
    })
    return res.data
  },

  async sendChatMessageStream(
    request: ChatRequest,
    onEvent: (event: ChatStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(new Error('ETIMEDOUT')), APP_CONFIG.chatTimeoutMs)
    const forwardAbort = () => controller.abort(signal?.reason)
    signal?.addEventListener('abort', forwardAbort, { once: true })

    try {
      const response = await fetch(`${apiBaseUrl}${APP_CONFIG.chatStreamEndpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept-Language': resolveActiveClientLocale(),
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        const err = new Error(`HTTP ${response.status}`) as Error & { response?: { status: number } }
        err.response = { status: response.status }
        throw err
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let remainder = ''
      let completedResponse: ChatResponse | null = null
      let streamErrorDetail: string | null = null

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        remainder += decoder.decode(value, { stream: true })
        remainder = parseSseFrames(remainder, (_type, dataRaw) => {
          try {
            const parsed = JSON.parse(dataRaw) as ChatStreamEvent
            onEvent(parsed)
            if (parsed.stage === 'completed' && parsed.response) {
              completedResponse = parsed.response
            } else if (parsed.stage === 'error') {
              streamErrorDetail = parsed.detail || 'Chat stream failed'
            }
          } catch {
            // Ignore malformed SSE event payload
          }
        })
      }

      if (streamErrorDetail) {
        throw new Error(streamErrorDetail)
      }
      if (!completedResponse) {
        throw new Error('Chat stream ended without a completed response')
      }
      return completedResponse
    } catch (err: unknown) {
      if (controller.signal.aborted && String(controller.signal.reason || '').includes('ETIMEDOUT')) {
        const timeoutErr = new Error('Request timed out') as Error & { code?: string }
        timeoutErr.code = 'ETIMEDOUT'
        throw timeoutErr
      }
      throw err
    } finally {
      clearTimeout(timeoutId)
      signal?.removeEventListener('abort', forwardAbort)
    }
  },

  async proposeTrainingAction(
    conversationId: string,
    training: {
      report_id: string
      title: string
      document_ids: string[]
      target_count: number
      question_count: number
      pass_score: number
    },
  ): Promise<PendingAction> {
    const res = await apiClient.post<PendingAction>('/api/v1/agent/learning/training/propose', {
      conversation_id: conversationId,
      training,
    })
    return res.data
  },

  async confirmPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse> {
    const res = await apiClient.post<ActionExecutionResponse>(
      `/api/v1/agent/actions/${confirmationId}/confirm`,
      { conversation_id: conversationId },
      { timeout: APP_CONFIG.chatTimeoutMs },
    )
    return res.data
  },

  async cancelPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse> {
    const res = await apiClient.post<ActionExecutionResponse>(
      `/api/v1/agent/actions/${confirmationId}/cancel`,
      { conversation_id: conversationId },
    )
    return res.data
  },
}
