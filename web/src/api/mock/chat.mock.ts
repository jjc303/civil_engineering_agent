import { mockChatResponse } from '@/mock/fixtures'
import { httpChatAdapter } from '../http/chat.http'
import type { ChatPort } from '../ports'
import type { ChatRequest, ChatResponse, ChatStreamEvent } from '@/types/contract'

function buildMockAnswer(request: ChatRequest): ChatResponse {
  const ctxHint = request.page_context?.route_title
    ? `（结合当前所在「${request.page_context.route_title}」页面上下文）`
    : ''
  return {
    ...mockChatResponse,
    request_id: 'req-' + Math.random().toString(36).substring(2, 9),
    answer: `针对您的提问 **“${request.question}”**${ctxHint}：\n\n` + mockChatResponse.answer,
  }
}

export const mockChatAdapter: ChatPort = {
  ...httpChatAdapter,
  async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    await new Promise((resolve) => setTimeout(resolve, 600))
    return buildMockAnswer(request)
  },

  async sendChatMessageStream(
    request: ChatRequest,
    onEvent: (event: ChatStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const stages: ChatStreamEvent[] = [
      { stage: 'retrieving_standards' },
      { stage: 'selecting_tool' },
      { stage: 'executing_tool', tool_name: 'get_violation_statistics', purpose: '汇总今日风险统计' },
      { stage: 'responding' },
    ]
    for (const evt of stages) {
      if (signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError')
      }
      onEvent(evt)
      await new Promise((resolve) => setTimeout(resolve, 260))
    }
    const response = buildMockAnswer(request)
    onEvent({ stage: 'completed', response })
    return response
  },
}
