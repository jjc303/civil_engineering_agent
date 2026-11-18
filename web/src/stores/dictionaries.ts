import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { apiClient } from '../api/client'
import { APP_CONFIG } from '../config/runtime'
import { translateAppMessage } from '../i18n'
import type { SupportedLocale } from '../i18n/types'
import { useLocaleStore } from './locale'
import type { EventStatus, ViolationSeverity, ViolationType } from '../types/contract'
import {
  DEFAULT_SEVERITY_LABELS,
  DEFAULT_STATUS_LABELS,
  DEFAULT_VIOLATION_LABELS,
} from '../constants/dictionaries'

interface DictionariesPayload {
  violation_types?: Array<{ code: ViolationType; label: string }>
  violation_labels?: Record<string, string>
  severity_labels?: Record<string, string>
  status_labels?: Record<string, string>
}

const VIOLATION_CODES: ReadonlyArray<ViolationType> = ['NO_HELMET', 'DANGER_ZONE_INTRUSION', 'DWELL_TIMEOUT']
const SEVERITY_CODES: ReadonlyArray<ViolationSeverity> = ['CRITICAL', 'WARNING', 'INFO']
const STATUS_CODES: ReadonlyArray<EventStatus> = ['ACTIVE', 'RESOLVED', 'FALSE_ALARM']

export const useDictionariesStore = defineStore('dictionaries', () => {
  const localeStore = useLocaleStore()
  const remoteByLocale = ref<Partial<Record<SupportedLocale, DictionariesPayload>>>({})
  const loadedLocale = ref<SupportedLocale | null>(null)
  let inFlightLocale: SupportedLocale | null = null

  function localizedFallbackViolationLabels(): Record<string, string> {
    return Object.fromEntries(
      VIOLATION_CODES.map((code) => [code, translateAppMessage(`enums.violation.${code}`)]),
    )
  }

  function localizedFallbackSeverityLabels(): Record<string, string> {
    return Object.fromEntries(
      SEVERITY_CODES.map((code) => [code, translateAppMessage(`enums.severity.${code}`)]),
    )
  }

  function localizedFallbackStatusLabels(): Record<string, string> {
    return Object.fromEntries(
      STATUS_CODES.map((code) => [code, translateAppMessage(`enums.eventStatus.${code}`)]),
    )
  }

  const activeRemote = computed(() => remoteByLocale.value[localeStore.locale])

  const violationLabels = computed<Record<string, string>>(() => ({
    ...localizedFallbackViolationLabels(),
    ...(activeRemote.value?.violation_labels || {}),
  }))

  const severityLabels = computed<Record<string, string>>(() => ({
    ...localizedFallbackSeverityLabels(),
    ...(activeRemote.value?.severity_labels || {}),
  }))

  const statusLabels = computed<Record<string, string>>(() => ({
    ...localizedFallbackStatusLabels(),
    ...(activeRemote.value?.status_labels || {}),
  }))

  const violationOptions = computed<Array<{ code: ViolationType; label: string }>>(() => {
    const remote = activeRemote.value?.violation_types
    if (Array.isArray(remote) && remote.length > 0) return remote
    return VIOLATION_CODES.map((code) => ({
      code,
      label: violationLabels.value[code] || DEFAULT_VIOLATION_LABELS[code] || code,
    }))
  })

  const severityOptions = computed<Array<{ code: ViolationSeverity; label: string }>>(() =>
    SEVERITY_CODES.map((code) => ({
      code,
      label: severityLabels.value[code] || DEFAULT_SEVERITY_LABELS[code] || code,
    })),
  )

  const statusOptions = computed<Array<{ code: EventStatus; label: string }>>(() =>
    STATUS_CODES.map((code) => ({
      code,
      label: statusLabels.value[code] || DEFAULT_STATUS_LABELS[code] || code,
    })),
  )

  const loaded = computed(() => loadedLocale.value === localeStore.locale)

  async function ensureLoaded(force = false): Promise<void> {
    const targetLocale = localeStore.locale
    if (!force && (remoteByLocale.value[targetLocale] || APP_CONFIG.useMock)) {
      loadedLocale.value = targetLocale
      return
    }
    if (inFlightLocale === targetLocale) return
    inFlightLocale = targetLocale
    try {
      const { data } = await apiClient.get<DictionariesPayload>('/api/v1/meta/dictionaries')
      remoteByLocale.value = {
        ...remoteByLocale.value,
        [targetLocale]: data,
      }
      loadedLocale.value = targetLocale
    } catch {
      // Keep localized frontend fallback constants if metadata endpoint is unreachable
    } finally {
      if (inFlightLocale === targetLocale) {
        inFlightLocale = null
      }
    }
  }

  watch(
    () => localeStore.locale,
    () => {
      void ensureLoaded()
    },
  )

  function violationLabel(type: ViolationType): string {
    return violationLabels.value[type] || DEFAULT_VIOLATION_LABELS[type] || type
  }

  function severityLabel(severity: ViolationSeverity): string {
    return severityLabels.value[severity] || DEFAULT_SEVERITY_LABELS[severity] || severity
  }

  function statusLabel(status: EventStatus): string {
    return statusLabels.value[status] || DEFAULT_STATUS_LABELS[status] || status
  }

  return {
    violationLabels,
    severityLabels,
    statusLabels,
    violationOptions,
    severityOptions,
    statusOptions,
    loaded,
    ensureLoaded,
    violationLabel,
    severityLabel,
    statusLabel,
  }
})
