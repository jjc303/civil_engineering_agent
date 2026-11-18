import { STORAGE_KEYS } from '@/config/runtime'
import type { DangerZoneConfig, SourceResolution } from '@/types/contract'
import { readJsonStorage, removeStorage, writeJsonStorage } from '@/utils/storage'

export interface ZoneDraftRules {
  enter_debounce_frames: number
  exit_debounce_frames: number
  helmet_debounce_frames: number
}

export interface ZoneDraftPayload {
  version: number
  zones: DangerZoneConfig[]
  index: number
  resolution: SourceResolution
  rules: ZoneDraftRules
}

export function useZoneDraft() {
  function saveDraft(cameraId: string, payload: ZoneDraftPayload): void {
    if (!cameraId) return
    writeJsonStorage(STORAGE_KEYS.zoneDraft(cameraId), payload, 'session')
  }

  function loadDraft(cameraId: string, expectedVersion: number): ZoneDraftPayload | null {
    if (!cameraId) return null
    const draft = readJsonStorage<ZoneDraftPayload>(STORAGE_KEYS.zoneDraft(cameraId), 'session')
    if (!draft || draft.version !== expectedVersion || !Array.isArray(draft.zones) || !draft.zones.length) {
      return null
    }
    return draft
  }

  function clearDraft(cameraId: string): void {
    if (!cameraId) return
    removeStorage(STORAGE_KEYS.zoneDraft(cameraId), 'session')
  }

  return {
    saveDraft,
    loadDraft,
    clearDraft,
  }
}
