import { apiClient } from './client'
import type { AssistantUiConfig } from '@/types/contract'

export async function fetchAssistantUiConfig(): Promise<AssistantUiConfig> {
  const response = await apiClient.get<AssistantUiConfig>('/api/v1/agent/ui-config')
  return response.data
}
