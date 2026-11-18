import axios, { AxiosError, type AxiosInstance } from 'axios'
import { APP_CONFIG } from '@/config/runtime'
import { resolveActiveClientLocale } from '@/i18n/localeDetect'
import { apiBaseUrl } from '@/utils/deployment'
import { getApiNotifier, translateApiMessage } from './ports'

export const CHAT_ENDPOINT = APP_CONFIG.chatEndpoint
export const API_TIMEOUT_MS = APP_CONFIG.apiTimeoutMs

type ErrorDetailPayload = { detail?: string | Array<{ msg: string }> }

function extractErrorMessage(error: AxiosError<ErrorDetailPayload>): string {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join('; ')
  }
  return typeof detail === 'string' ? detail : error.message
}

export function notifyHttpError(error: AxiosError<ErrorDetailPayload>): void {
  if (error.config?.url === CHAT_ENDPOINT) return
  const notifier = getApiNotifier()

  if (!error.response) {
    notifier.error(translateApiMessage('errors.networkError', { msg: error.message }))
    return
  }

  const status = error.response.status
  const errorMsg = extractErrorMessage(error)

  if (status === 409) {
    notifier.error(translateApiMessage('errors.versionConflict', { msg: errorMsg }))
  } else if (status === 404) {
    // Callers decide how to present missing resources.
  } else if (status >= 500) {
    notifier.error(translateApiMessage('errors.serverError', { status, msg: errorMsg }))
  } else if (status === 422) {
    notifier.warning(translateApiMessage('errors.validationError', { msg: errorMsg }))
  }
}

export function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: apiBaseUrl,
    timeout: API_TIMEOUT_MS,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  client.interceptors.request.use((config) => {
    config.headers = config.headers || {}
    config.headers['Accept-Language'] = resolveActiveClientLocale()
    return config
  })

  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ErrorDetailPayload>) => {
      notifyHttpError(error)
      return Promise.reject(error)
    },
  )

  return client
}

export const apiClient = createApiClient()

export function resolveMediaUrl(snapshotUri: string | null): string {
  if (!snapshotUri) return ''
  const cleanUri = snapshotUri.startsWith('/') ? snapshotUri.substring(1) : snapshotUri
  return `${apiBaseUrl}/media/${cleanUri}`
}
