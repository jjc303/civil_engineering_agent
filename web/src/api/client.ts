import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

export const isMockEnabled = import.meta.env.VITE_USE_MOCK === 'true'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 20000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg: string }> }>) => {
    if (error.response) {
      const status = error.response.status
      const detail = error.response.data?.detail
      let errorMsg = typeof detail === 'string' ? detail : error.message

      if (Array.isArray(detail)) {
        errorMsg = detail.map((d) => d.msg).join('; ')
      }

      if (status === 409) {
        ElMessage.error(`版本并发冲突: ${errorMsg}`)
      } else if (status === 404) {
        // 让业务方自主处理 404
      } else if (status >= 500) {
        ElMessage.error(`服务器错误 [${status}]: ${errorMsg}`)
      } else if (status === 422) {
        ElMessage.warning(`参数校验失败: ${errorMsg}`)
      }
    } else {
      ElMessage.error(`网络连接异常: ${error.message}`)
    }
    return Promise.reject(error)
  }
)

export function resolveMediaUrl(snapshotUri: string | null): string {
  if (!snapshotUri) return ''
  const cleanUri = snapshotUri.startsWith('/') ? snapshotUri.substring(1) : snapshotUri
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/media/${cleanUri}`
}
