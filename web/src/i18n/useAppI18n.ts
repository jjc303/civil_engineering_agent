import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useLocaleStore } from '@/stores/locale'
import type { SupportedLocale } from './types'
import {
  formatLocaleDate,
  formatLocaleDateTime,
  formatLocaleTime,
} from '@/utils/datetime'

/**
 * Facade composable decoupling views/components from vue-i18n internals,
 * Pinia store wiring, and Intl locale formatting details.
 */
export function useAppI18n() {
  const { t } = useI18n({ useScope: 'global' })
  const localeStore = useLocaleStore()
  const { locale, intlLocale, elementLocale } = storeToRefs(localeStore)

  function setLocale(next: SupportedLocale): void {
    localeStore.setLocale(next)
  }

  function formatDate(
    value: string | Date,
    options?: Intl.DateTimeFormatOptions,
  ): string {
    return formatLocaleDate(value, intlLocale.value, options)
  }

  function formatTime(
    value: string | Date,
    options?: Intl.DateTimeFormatOptions,
  ): string {
    return formatLocaleTime(value, intlLocale.value, options)
  }

  function formatDateTime(
    value: string | Date,
    options?: Intl.DateTimeFormatOptions,
  ): string {
    return formatLocaleDateTime(value, intlLocale.value, options)
  }

  return {
    t,
    locale: computed(() => locale.value),
    intlLocale: computed(() => intlLocale.value),
    elementLocale,
    localeOptions: localeStore.options,
    setLocale,
    toggleLocale: localeStore.toggleLocale,
    formatDate,
    formatTime,
    formatDateTime,
  }
}

/**
 * Declarative hook for views that need to refresh backend-localized dynamic data on locale change.
 */
export function useLocaleRefresh(callback: () => void | Promise<void>): void {
  const localeStore = useLocaleStore()
  watch(
    () => localeStore.locale,
    () => {
      void callback()
    },
  )
}
