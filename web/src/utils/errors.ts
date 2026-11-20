export interface ApiErrorShape {
  response?: {
    data?: {
      detail?: string | Array<{ msg?: string }>
    }
    status?: number
  }
  code?: string
  message?: string
}

/**
 * Extract a human-readable error message from Axios/Fetch errors with safe fallback.
 */
export function extractApiError(err: unknown, fallback: string): string {
  const typed = err as ApiErrorShape | null | undefined
  const detail = typed?.response?.data?.detail
  if (Array.isArray(detail)) {
    const joined = detail.map((item) => item?.msg).filter(Boolean).join('; ')
    if (joined) return joined
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (typeof typed?.message === 'string' && typed.message.trim()) {
    return typed.message
  }
  return fallback
}
