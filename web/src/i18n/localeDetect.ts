import { STORAGE_KEYS } from '@/config/runtime'
import { readStorage } from '@/utils/storage'
import type { SupportedLocale } from './types'

export const DEFAULT_LOCALE: SupportedLocale = 'zh-CN'
export const LOCALE_STORAGE_KEY = STORAGE_KEYS.locale

export function isSupportedLocale(value: unknown): value is SupportedLocale {
  return value === 'zh-CN' || value === 'zh-HK'
}

export function normalizeLocaleTag(tag: string | null | undefined): SupportedLocale | null {
  if (!tag) return null
  const normalized = tag.trim().toLowerCase().replace(/_/g, '-')
  if (/^zh-(hk|tw|mo|hant)\b/.test(normalized)) return 'zh-HK'
  if (/^zh-(cn|sg|hans)\b/.test(normalized) || normalized === 'zh') return 'zh-CN'
  return null
}

export function detectInitialLocale(): SupportedLocale {
  const saved = readStorage(LOCALE_STORAGE_KEY, 'local')
  if (isSupportedLocale(saved)) return saved
  if (typeof navigator !== 'undefined') {
    const candidates = navigator.languages?.length ? navigator.languages : [navigator.language]
    for (const candidate of candidates) {
      const matched = normalizeLocaleTag(candidate)
      if (matched) return matched
    }
  }
  return DEFAULT_LOCALE
}

export function resolveActiveClientLocale(): SupportedLocale {
  if (typeof document !== 'undefined' && isSupportedLocale(document.documentElement.lang)) {
    return document.documentElement.lang
  }
  return detectInitialLocale()
}

type LocaleChangeListener = (locale: SupportedLocale) => void
const localeListeners = new Set<LocaleChangeListener>()

export function subscribeLocaleChange(listener: LocaleChangeListener): () => void {
  localeListeners.add(listener)
  return () => {
    localeListeners.delete(listener)
  }
}

export function notifyLocaleChanged(locale: SupportedLocale): void {
  for (const listener of localeListeners) {
    listener(locale)
  }
}
