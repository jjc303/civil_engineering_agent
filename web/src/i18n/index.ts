import { createI18n } from 'vue-i18n'
import { zhCnMessages, type MessageSchema } from './locales/zh-CN'
import { zhHkMessages } from './locales/zh-HK'
import { detectInitialLocale } from './strategies'
import type { SupportedLocale } from './types'

export type { MessageSchema }

export const i18n = createI18n({
  legacy: false,
  locale: detectInitialLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCnMessages,
    'zh-HK': zhHkMessages,
  },
})

export function setI18nLocale(next: SupportedLocale): void {
  i18n.global.locale.value = next
}

export function translateAppMessage(
  key: string,
  params?: Record<string, string | number>,
): string {
  return params ? String(i18n.global.t(key, params)) : String(i18n.global.t(key))
}
