import { onUnmounted, ref } from 'vue'

const DEFAULT_DOWNLOAD_REVOKE_MS = 60_000
const DEFAULT_PREVIEW_REVOKE_MS = 300_000

export function useObjectUrl() {
  const objectUrl = ref('')

  function clear(): void {
    if (objectUrl.value) {
      URL.revokeObjectURL(objectUrl.value)
      objectUrl.value = ''
    }
  }

  function setBlob(blob: Blob): string {
    clear()
    objectUrl.value = URL.createObjectURL(blob)
    return objectUrl.value
  }

  onUnmounted(clear)

  return {
    objectUrl,
    setBlob,
    clear,
  }
}

export function triggerBlobDownload(blob: Blob, filename: string, revokeDelayMs = DEFAULT_DOWNLOAD_REVOKE_MS): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), revokeDelayMs)
}

export function attachBlobToWindow(blob: Blob, targetTab: Window, revokeDelayMs = DEFAULT_PREVIEW_REVOKE_MS): void {
  const url = URL.createObjectURL(blob)
  targetTab.location.href = url
  window.setTimeout(() => URL.revokeObjectURL(url), revokeDelayMs)
}
