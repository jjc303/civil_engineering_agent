import type { Language as ElementLocale } from 'element-plus/es/locale'

export type SupportedLocale = 'zh-CN' | 'zh-HK'

export interface LocaleStrategy {
  readonly code: SupportedLocale
  readonly shortLabel: string
  readonly label: string
  readonly htmlLang: string
  readonly intlLocale: string
  readonly elementLocale: ElementLocale
}
