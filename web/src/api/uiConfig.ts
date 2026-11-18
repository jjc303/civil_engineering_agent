import { getApiBundle } from './index'
import type { AssistantUiConfig } from '@/types/contract'

export async function fetchAssistantUiConfig(): Promise<AssistantUiConfig> {
  return (await getApiBundle()).uiConfig.fetchAssistantUiConfig()
}
