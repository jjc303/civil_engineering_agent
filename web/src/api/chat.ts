import { APP_CONFIG, STORAGE_KEYS } from '@/config/runtime'
import { readStorage, writeStorage } from '@/utils/storage'
import { getApiBundle } from './index'
import type { ActionExecutionResponse, ChatRequest, ChatResponse, ChatStreamEvent, PendingAction } from '@/types/contract'

export const CHAT_TIMEOUT_MS = APP_CONFIG.chatTimeoutMs

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
  const existing = readStorage(STORAGE_KEYS.agentConversationId, 'session')
  if (existing) return existing
  const created = createUuidV4()
  writeStorage(STORAGE_KEYS.agentConversationId, created, 'session')
  return created
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return (await getApiBundle()).chat.sendChatMessage(request)
}

export async function sendChatMessageStream(
  request: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const adapter = (await getApiBundle()).chat
  if (typeof adapter.sendChatMessageStream === 'function') {
    return adapter.sendChatMessageStream(request, onEvent, signal)
  }
  const response = await adapter.sendChatMessage(request)
  onEvent({ stage: 'completed', response })
  return response
}

export async function proposeTrainingAction(
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
  return (await getApiBundle()).chat.proposeTrainingAction(conversationId, training)
}

export async function confirmPendingAction(
  confirmationId: string,
  conversationId: string,
): Promise<ActionExecutionResponse> {
  return (await getApiBundle()).chat.confirmPendingAction(confirmationId, conversationId)
}

export async function cancelPendingAction(
  confirmationId: string,
  conversationId: string,
): Promise<ActionExecutionResponse> {
  return (await getApiBundle()).chat.cancelPendingAction(confirmationId, conversationId)
}
