interface MetaEnv {
  BASE_URL?: string
  VITE_USE_MOCK?: string
  VITE_LOCAL_VIDEO_DEMO?: string
  VITE_API_BASE_URL?: string
  VITE_API_TIMEOUT_MS?: string
  VITE_CHAT_TIMEOUT_MS?: string
  VITE_LEARNING_TIMEOUT_MS?: string
  VITE_LEARNING_TIMEZONE?: string
}

function readEnv(): MetaEnv {
  return (import.meta as { env?: MetaEnv }).env ?? {}
}

const env = readEnv()

export const APP_CONFIG = {
  useMock: env.VITE_USE_MOCK === 'true',
  localVideoDemo: env.VITE_LOCAL_VIDEO_DEMO === 'true',
  apiTimeoutMs: Number(env.VITE_API_TIMEOUT_MS) || 20000,
  chatTimeoutMs: Number(env.VITE_CHAT_TIMEOUT_MS) || 180000,
  learningTimeoutMs: Number(env.VITE_LEARNING_TIMEOUT_MS) || 120000,
  learningTimezone: env.VITE_LEARNING_TIMEZONE || 'Asia/Shanghai',
  chatEndpoint: '/api/v1/agent/chat',
  chatStreamEndpoint: '/api/v1/agent/chat/stream',
} as const

export const STORAGE_KEYS = {
  locale: 'safety_agent_locale',
  agentConversationId: 'agent_conversation_id',
  agentChatMessages: 'agent_chat_messages',
  mascotPosition: 'safety_agent_mascot_pos',
  mascotCollapsed: 'safety_agent_mascot_collapsed',
  mascotVoiceEnabled: 'safety_agent_mascot_voice',
  zoneDraft: (cameraId: string) => `camera-zone-draft:${cameraId}`,
} as const
