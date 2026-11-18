import { mockChatResponse } from '@/mock/fixtures'
import { httpChatAdapter } from '../http/chat.http'
import type { ChatPort } from '../ports'
import type { ChatRequest, ChatResponse } from '@/types/contract'

export const mockChatAdapter: ChatPort = {
  ...httpChatAdapter,
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    await new Promise((resolve) => setTimeout(resolve, 600))
    return {
      ...mockChatResponse,
      request_id: 'req-' + Math.random().toString(36).substring(2, 9),
      answer: `针对您的提问 **“${request.question}”**：\n\n` + mockChatResponse.answer,
    }
  },
}
