import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { translateAppMessage } from '@/i18n'
import { LOCALE_STORAGE_KEY, detectInitialLocale, isSupportedLocale } from '@/i18n/strategies'
import { apiBaseUrl } from '@/utils/deployment'

export const isMockEnabled = import.meta.env.VITE_USE_MOCK === 'true'
export const CHAT_ENDPOINT = '/api/v1/agent/chat'
export const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 20000

function currentClientLocale(): string {
  if (typeof document !== 'undefined' && isSupportedLocale(document.documentElement.lang)) {
    return document.documentElement.lang
  }
  if (typeof window !== 'undefined') {
    try {
      const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY)
      if (isSupportedLocale(saved)) return saved
    } catch {
      // Ignore storage access errors
    }
  }
  return detectInitialLocale()
}

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  config.headers = config.headers || {}
  config.headers['Accept-Language'] = currentClientLocale()
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg: string }> }>) => {
    // The conversation displays a persistent, contextual error itself.
    if (error.config?.url === CHAT_ENDPOINT) return Promise.reject(error)
    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail
      let errorMsg = typeof detail === 'string' ? detail : error.message

      if (Array.isArray(detail)) {
        errorMsg = detail.map((d) => d.msg).join('; ')
      }

      if (status === 409) {
        ElMessage.error(translateAppMessage('errors.versionConflict', { msg: errorMsg }))
      } else if (status === 404) {
        // 让业务方自主处理 404
      } else if (status >= 500) {
        ElMessage.error(translateAppMessage('errors.serverError', { status, msg: errorMsg }))
      } else if (status === 422) {
        ElMessage.warning(translateAppMessage('errors.validationError', { msg: errorMsg }))
      }
    } else {
      ElMessage.error(translateAppMessage('errors.networkError', { msg: error.message }))
    }
    return Promise.reject(error)
  }
)

export function resolveMediaUrl(snapshotUri: string | null): string {
  if (!snapshotUri) return ''
  const cleanUri = snapshotUri.startsWith('/') ? snapshotUri.substring(1) : snapshotUri
  return `${apiBaseUrl}/media/${cleanUri}`
}
