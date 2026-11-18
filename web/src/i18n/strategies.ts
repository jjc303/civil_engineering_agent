import zhCn from 'element-plus/es/locale/lang/zh-cn'
import zhTw from 'element-plus/es/locale/lang/zh-tw'
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  detectInitialLocale,
  isSupportedLocale,
  normalizeLocaleTag,
} from './localeDetect'
import type { LocaleStrategy, SupportedLocale } from './types'

export {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  detectInitialLocale,
  isSupportedLocale,
  normalizeLocaleTag,
}

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
