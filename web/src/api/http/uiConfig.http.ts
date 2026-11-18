import { apiClient } from '../client'
import type { UiConfigPort } from '../ports'
import type { AssistantUiConfig } from '@/types/contract'

export const httpUiConfigAdapter: UiConfigPort = {
  async fetchAssistantUiConfig(): Promise<AssistantUiConfig> {
    const response = await apiClient.get<AssistantUiConfig>('/api/v1/agent/ui-config')
    return response.data
  },
}
