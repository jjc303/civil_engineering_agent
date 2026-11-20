import type { UiConfigPort } from '../ports'
import type { AssistantUiConfig } from '@/types/contract'

export const mockUiConfigAdapter: UiConfigPort = {
  async fetchAssistantUiConfig(): Promise<AssistantUiConfig> {
    return {
      version: 1,
      assistant_name: '安全智能助手',
      welcome_message: '查询现场风险，核对安全依据，衔接报告与培训。',
      input_placeholder: '例如：查看本周安全报告，或查询长沙当前天气',
      quick_questions: ['查看所有摄像头状态', '查看最新违规事件', '查看本周安全报告'],
      show_evidence: true,
      mascot_profile: {
        enabled: true,
        persona_name: '安小盾',
        idle_greeting: '我是施工安全卫士安小盾，随时为您巡检风险与解答规范。',
        alert_reaction_enabled: true,
        voice_enabled_by_default: false,
      },
      updated_at_utc: new Date().toISOString(),
    }
  },
}
