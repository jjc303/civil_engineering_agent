import { apiClient, CHAT_ENDPOINT, isMockEnabled } from './client'
import type { ActionExecutionResponse, ChatRequest, ChatResponse, PendingAction } from '@/types/contract'
import { mockChatResponse } from '@/mock/fixtures'

export const CHAT_TIMEOUT_MS = Number(import.meta.env.VITE_CHAT_TIMEOUT_MS) || 180000
const AGENT_CONVERSATION_STORAGE_KEY = 'agent_conversation_id'

function createUuidV4(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes)
  } else {
    for (let i = 0; i < 16; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256)
    }
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'))
  return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
}

export function getAgentConversationId(): string {
  const existing = sessionStorage.getItem(AGENT_CONVERSATION_STORAGE_KEY)
  if (existing) return existing
  const created = createUuidV4()
  sessionStorage.setItem(AGENT_CONVERSATION_STORAGE_KEY, created)
  return created
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  if (isMockEnabled) {
    // 延迟 600ms 模拟网络
    await new Promise((resolve) => setTimeout(resolve, 600))
    return {
      ...mockChatResponse,
      request_id: 'req-' + Math.random().toString(36).substring(2, 9),
      answer: `针对您的提问 **“${request.question}”**：\n\n` + mockChatResponse.answer,
    }
  }
  // Chat includes model planning, tool execution and answer generation.
  const res = await apiClient.post<ChatResponse>(CHAT_ENDPOINT, request, { timeout: CHAT_TIMEOUT_MS })
  return res.data
}

export async function proposeTrainingAction(conversationId: string, training: {
  report_id: string; title: string; document_ids: string[]; target_count: number; question_count: number; pass_score: number
}): Promise<PendingAction> {
  const res = await apiClient.post<PendingAction>('/api/v1/agent/learning/training/propose', {
    conversation_id: conversationId,
    training,
  })
  return res.data
}

export async function confirmPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse> {
  const res = await apiClient.post<ActionExecutionResponse>(`/api/v1/agent/actions/${confirmationId}/confirm`, { conversation_id: conversationId }, { timeout: CHAT_TIMEOUT_MS })
  return res.data
}

export async function cancelPendingAction(confirmationId: string, conversationId: string): Promise<ActionExecutionResponse> {
  const res = await apiClient.post<ActionExecutionResponse>(`/api/v1/agent/actions/${confirmationId}/cancel`, { conversation_id: conversationId })
  return res.data
}
