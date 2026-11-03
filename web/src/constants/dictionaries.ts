import type { EventStatus, ViolationSeverity, ViolationType } from '../types/contract'

export const DEFAULT_VIOLATION_LABELS: Record<ViolationType, string> = {
  NO_HELMET: '未佩戴安全帽',
  DANGER_ZONE_INTRUSION: '危险区域入侵',
  DWELL_TIMEOUT: '危险区域停留超时',
}

export const VIOLATION_TYPE_OPTIONS: ReadonlyArray<{ code: ViolationType; label: string }> = [
  { code: 'NO_HELMET', label: DEFAULT_VIOLATION_LABELS.NO_HELMET },
  { code: 'DANGER_ZONE_INTRUSION', label: DEFAULT_VIOLATION_LABELS.DANGER_ZONE_INTRUSION },
  { code: 'DWELL_TIMEOUT', label: DEFAULT_VIOLATION_LABELS.DWELL_TIMEOUT },
]

export const DEFAULT_SEVERITY_LABELS: Record<ViolationSeverity, string> = {
  CRITICAL: '严重',
  WARNING: '警告',
  INFO: '提示',
}

export const DEFAULT_STATUS_LABELS: Record<EventStatus, string> = {
  ACTIVE: '待关注',
  RESOLVED: '已解除',
  FALSE_ALARM: '误报',
}

export function violationTypeLabel(
  type: ViolationType,
  labels: Record<string, string> = DEFAULT_VIOLATION_LABELS,
): string {
  return labels[type] || DEFAULT_VIOLATION_LABELS[type] || type
}
