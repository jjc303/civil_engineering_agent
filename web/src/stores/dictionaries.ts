import { ref } from 'vue'
import { defineStore } from 'pinia'
import { apiClient, isMockEnabled } from '../api/client'
import type { EventStatus, ViolationSeverity, ViolationType } from '../types/contract'
import {
  DEFAULT_SEVERITY_LABELS,
  DEFAULT_STATUS_LABELS,
  DEFAULT_VIOLATION_LABELS,
  VIOLATION_TYPE_OPTIONS,
} from '../constants/dictionaries'

interface DictionariesPayload {
  violation_types?: Array<{ code: ViolationType; label: string }>
  violation_labels?: Record<string, string>
  severity_labels?: Record<string, string>
  status_labels?: Record<string, string>
}

export const useDictionariesStore = defineStore('dictionaries', () => {
  const violationLabels = ref<Record<string, string>>({ ...DEFAULT_VIOLATION_LABELS })
  const severityLabels = ref<Record<string, string>>({ ...DEFAULT_SEVERITY_LABELS })
  const statusLabels = ref<Record<string, string>>({ ...DEFAULT_STATUS_LABELS })
  const violationOptions = ref([...VIOLATION_TYPE_OPTIONS])
  const loaded = ref(false)

  async function ensureLoaded(): Promise<void> {
    if (loaded.value || isMockEnabled) {
      loaded.value = true
      return
    }
    try {
      const { data } = await apiClient.get<DictionariesPayload>('/api/v1/meta/dictionaries')
      if (data.violation_labels) {
        violationLabels.value = { ...DEFAULT_VIOLATION_LABELS, ...data.violation_labels }
      }
      if (data.severity_labels) {
        severityLabels.value = { ...DEFAULT_SEVERITY_LABELS, ...data.severity_labels }
      }
      if (data.status_labels) {
        statusLabels.value = { ...DEFAULT_STATUS_LABELS, ...data.status_labels }
      }
      if (Array.isArray(data.violation_types) && data.violation_types.length > 0) {
        violationOptions.value = data.violation_types
      }
      loaded.value = true
    } catch {
      // Keep local fallback constants if metadata endpoint is unreachable
    }
  }

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
    loaded,
    ensureLoaded,
    violationLabel,
    severityLabel,
    statusLabel,
  }
})
