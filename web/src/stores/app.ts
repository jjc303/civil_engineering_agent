import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CameraStatusResponse } from '@/types/contract'
import { fetchCameras } from '@/api/cameras'
import { APP_CONFIG } from '@/config/runtime'

export const useAppStore = defineStore('app', () => {
  const cameras = ref<CameraStatusResponse[]>([])
  const loadingCameras = ref(false)
  const isMock = ref(APP_CONFIG.useMock)

  async function loadCameras() {
    loadingCameras.value = true
    try {
      cameras.value = await fetchCameras()
    } finally {
      loadingCameras.value = false
    }
  }

  return {
    cameras,
    loadingCameras,
    isMock,
    loadCameras,
  }
})
