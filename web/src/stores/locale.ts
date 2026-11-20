import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { setI18nLocale } from '@/i18n'
import { notifyLocaleChanged } from '@/i18n/localeDetect'
import { writeStorage } from '@/utils/storage'
import {
  LOCALE_OPTIONS,
  LOCALE_STORAGE_KEY,
  LOCALE_STRATEGIES,
  detectInitialLocale,
  isSupportedLocale,
} from '@/i18n/strategies'
import type { LocaleStrategy, SupportedLocale } from '@/i18n/types'

export const useLocaleStore = defineStore('locale', () => {
  const currentLocale = ref<SupportedLocale>(detectInitialLocale())
  let initialized = false

  const strategy = computed<LocaleStrategy>(() => LOCALE_STRATEGIES[currentLocale.value])
  const elementLocale = computed(() => strategy.value.elementLocale)
  const intlLocale = computed(() => strategy.value.intlLocale)
  const options = LOCALE_OPTIONS

  function applyLocaleSideEffects(next: SupportedLocale, persist = true): void {
    currentLocale.value = next
    setI18nLocale(next)
    const activeStrategy = LOCALE_STRATEGIES[next]

    if (typeof document !== 'undefined') {
      document.documentElement.lang = activeStrategy.htmlLang
    }
    if (persist) {
      writeStorage(LOCALE_STORAGE_KEY, next, 'local')
    }
    notifyLocaleChanged(next)
  }

  function init(): void {
    if (initialized) return
    initialized = true
    applyLocaleSideEffects(currentLocale.value, false)

    if (typeof window !== 'undefined') {
      window.addEventListener('storage', (event: StorageEvent) => {
        if (event.key === LOCALE_STORAGE_KEY && isSupportedLocale(event.newValue)) {
          applyLocaleSideEffects(event.newValue, false)
        }
      })
    }
  }

  function setLocale(next: SupportedLocale): void {
    if (next === currentLocale.value && initialized) return
    applyLocaleSideEffects(next, true)
  }

  function toggleLocale(): void {
    const idx = LOCALE_OPTIONS.findIndex((item) => item.code === currentLocale.value)
    const next = LOCALE_OPTIONS[(idx + 1) % LOCALE_OPTIONS.length]!
    setLocale(next.code)
  }

  return {
    locale: currentLocale,
    strategy,
    elementLocale,
    intlLocale,
    options,
    init,
    setLocale,
    toggleLocale,
  }
})
