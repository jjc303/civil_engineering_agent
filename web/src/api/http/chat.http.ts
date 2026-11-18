import { APP_CONFIG } from '@/config/runtime'
import { apiClient, CHAT_ENDPOINT } from '../client'
import type { ChatPort } from '../ports'
import type { ActionExecutionResponse, ChatRequest, ChatResponse, PendingAction } from '@/types/contract'

export const httpChatAdapter: ChatPort = {
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    const res = await apiClient.post<ChatResponse>(CHAT_ENDPOINT, request, {
      timeout: APP_CONFIG.chatTimeoutMs,
    })
    return res.data
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
