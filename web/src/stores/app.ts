import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CameraStatusResponse } from '@/types/contract'
import { fetchCameras } from '@/api/cameras'

export const useAppStore = defineStore('app', () => {
  const cameras = ref<CameraStatusResponse[]>([])
  const loadingCameras = ref(false)
  const isMock = ref(import.meta.env.VITE_USE_MOCK === 'true')

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
