import { apiClient, isMockEnabled } from './client'
import type { ChatRequest, ChatResponse } from '@/types/contract'
import { mockChatResponse } from '@/mock/fixtures'

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
  const res = await apiClient.post<ChatResponse>('/api/v1/agent/chat', request)
  return res.data
}
