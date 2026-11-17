import zhCn from 'element-plus/es/locale/lang/zh-cn'
import zhTw from 'element-plus/es/locale/lang/zh-tw'
import type { LocaleStrategy, SupportedLocale } from './types'

export const DEFAULT_LOCALE: SupportedLocale = 'zh-CN'
export const LOCALE_STORAGE_KEY = 'safety_agent_locale'

export const LOCALE_STRATEGIES: Record<SupportedLocale, LocaleStrategy> = {
  'zh-CN': {
    code: 'zh-CN',
    shortLabel: '简',
    label: '简体中文',
    htmlLang: 'zh-CN',
    intlLocale: 'zh-CN',
    elementLocale: zhCn,
  },
  'zh-HK': {
    code: 'zh-HK',
    shortLabel: '繁',
    label: '繁體中文',
    htmlLang: 'zh-HK',
    intlLocale: 'zh-HK',
    elementLocale: zhTw,
  },
}

export const LOCALE_OPTIONS: ReadonlyArray<LocaleStrategy> = Object.values(LOCALE_STRATEGIES)

export function isSupportedLocale(value: unknown): value is SupportedLocale {
  return typeof value === 'string' && value in LOCALE_STRATEGIES
}

export function normalizeLocaleTag(tag: string | null | undefined): SupportedLocale | null {
  if (!tag) return null
  const normalized = tag.trim().toLowerCase().replace(/_/g, '-')
  if (/^zh-(hk|tw|mo|hant)\b/.test(normalized)) return 'zh-HK'
  if (/^zh-(cn|sg|hans)\b/.test(normalized) || normalized === 'zh') return 'zh-CN'
  return null
}

export function detectInitialLocale(): SupportedLocale {
  if (typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY)
      if (isSupportedLocale(saved)) return saved
    } catch {
      // Ignore storage access errors in restricted contexts
    }
    if (typeof navigator !== 'undefined') {
      const candidates = navigator.languages?.length ? navigator.languages : [navigator.language]
      for (const candidate of candidates) {
        const matched = normalizeLocaleTag(candidate)
        if (matched) return matched
      }
    }
  }
  return DEFAULT_LOCALE
}
