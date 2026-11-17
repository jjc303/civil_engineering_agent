/**
 * Shared UTC parsing and locale-aware date/time formatting utilities.
 */

export function utcDate(value: string | Date): Date {
  if (value instanceof Date) return value
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
}

export function getLearningTimezone(): string {
  return import.meta.env.VITE_LEARNING_TIMEZONE || 'Asia/Shanghai'
}

export function formatLocaleDate(
  value: string | Date,
  intlLocale: string,
  options: Intl.DateTimeFormatOptions = { year: 'numeric', month: '2-digit', day: '2-digit' },
): string {
  if (!value) return '-'
  return utcDate(value).toLocaleDateString(intlLocale, options)
}

export function formatLocaleTime(
  value: string | Date,
  intlLocale: string,
  options: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false },
): string {
  if (!value) return '-'
  return utcDate(value).toLocaleTimeString(intlLocale, options)
}

export function formatLocaleDateTime(
  value: string | Date,
  intlLocale: string,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (!value) return '-'
  return utcDate(value).toLocaleString(intlLocale, options)
}

/**
 * Convert a local YYYY-MM-DD calendar date in `timeZone` to the UTC Date
 * representing 00:00:00 on that day (or the start of the next day if `endExclusive` is true).
 */
export function zonedDateBoundaryToIso(
  dateStr: string,
  timeZone = getLearningTimezone(),
  endExclusive = false,
): string {
  const parts = dateStr.split('-').map(Number)
  const year = parts[0] || 1970
  const month = parts[1] || 1
  const day = parts[2] || 1
  const targetDayOffset = endExclusive ? 1 : 0
  const utcGuess = new Date(Date.UTC(year, month - 1, day + targetDayOffset, 0, 0, 0))
  const offsetMs = getTimeZoneOffsetMs(utcGuess, timeZone)
  return new Date(utcGuess.getTime() - offsetMs).toISOString()
}

function getTimeZoneOffsetMs(date: Date, timeZone: string): number {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  const map: Record<string, number> = {}
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== 'literal') {
      map[part.type] = Number(part.value)
    }
  }
  const hour = map.hour === 24 ? 0 : (map.hour ?? 0)
  const asUtc = Date.UTC(map.year ?? 1970, (map.month ?? 1) - 1, map.day ?? 1, hour, map.minute ?? 0, map.second ?? 0)
  return asUtc - date.getTime()
}
