import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { translateApiMessage } from '@/api/ports'
import { STORAGE_KEYS } from '@/config/runtime'
import { resolveActiveClientLocale } from '@/i18n/localeDetect'
import { MASCOT_DEFAULTS } from '@/mascot/config'
import { resolvePageContextPolicy, type MascotContextKey } from '@/mascot/pageContextRegistry'
import type { MascotGazeOffset } from '@/mascot/renderer'
import { getSpeechPort } from '@/mascot/speech'
import {
  getMascotStateSpec,
  resolveMascotTransition,
  type MascotState,
} from '@/mascot/stateMachine'
import { useCopilotStore } from '@/stores/copilot'
import { useRealtimeStore } from '@/stores/realtime'
import type { ViolationRecord } from '@/types/contract'
import { readJsonStorage, readStorage, writeJsonStorage, writeStorage } from '@/utils/storage'

export interface MascotBubble {
  id: number
  text: string
  tone: 'info' | 'warning' | 'danger' | 'success'
  actionLabel?: string
  violation?: ViolationRecord
}

export interface MascotPosition {
  x: number
  y: number
}

export const useMascotStore = defineStore('mascot', () => {
  const copilotStore = useCopilotStore()
  const realtimeStore = useRealtimeStore()

  const state = ref<MascotState>('idle')
  const drawerOpen = ref(false)
  const minimized = ref(readStorage(STORAGE_KEYS.mascotCollapsed, 'local') === 'true')
  const voiceSupported = computed(() => getSpeechPort().isSupported())
  const storedVoicePref = readStorage(STORAGE_KEYS.mascotVoiceEnabled, 'local')
  const voiceEnabled = ref(storedVoicePref === 'true')
  const speakingActive = ref(false)
  const unreadAlerts = ref(0)
  const latestAlert = ref<ViolationRecord | null>(null)
  const bubble = ref<MascotBubble | null>(null)
  const gazeOffset = ref<MascotGazeOffset>({ x: 0, y: 0 })
  const contextKey = ref<MascotContextKey>('default')
  const position = ref<MascotPosition | null>(
    readJsonStorage<MascotPosition>(STORAGE_KEYS.mascotPosition, 'local'),
  )

  let initialized = false
  let bubbleSeq = 0
  let revertTimer: ReturnType<typeof setTimeout> | undefined
  let bubbleTimer: ReturnType<typeof setTimeout> | undefined
  let stopRealtimeSubscription: (() => void) | undefined

  const profile = computed(() => copilotStore.uiConfig?.mascot_profile)
  const isEnabled = computed(() => profile.value?.enabled !== false)
  const personaName = computed(
    () => profile.value?.persona_name || translateApiMessage('mascot.defaultPersonaName'),
  )
  const pagePolicy = computed(() => resolvePageContextPolicy(contextKey.value))
  const stateSpec = computed(() => getMascotStateSpec(state.value))

  function clearRevertTimer(): void {
    if (revertTimer) {
      clearTimeout(revertTimer)
      revertTimer = undefined
    }
  }

  function clearBubbleTimer(): void {
    if (bubbleTimer) {
      clearTimeout(bubbleTimer)
      bubbleTimer = undefined
    }
  }

  function showBubble(
    text: string,
    tone: MascotBubble['tone'] = 'info',
    options?: { durationMs?: number; actionLabel?: string; violation?: ViolationRecord },
  ): void {
    const clipped =
      text.length > MASCOT_DEFAULTS.maxBubbleChars
        ? `${text.slice(0, MASCOT_DEFAULTS.maxBubbleChars - 1)}…`
        : text
    bubbleSeq += 1
    bubble.value = {
      id: bubbleSeq,
      text: clipped,
      tone,
      actionLabel: options?.actionLabel,
      violation: options?.violation,
    }
    clearBubbleTimer()
    const duration = options?.durationMs ?? MASCOT_DEFAULTS.autoRevertMs.alert
    if (duration > 0) {
      bubbleTimer = setTimeout(() => {
        bubble.value = null
      }, duration)
    }
  }

  function dismissBubble(): void {
    clearBubbleTimer()
    bubble.value = null
  }

  function resolveBaselineState(): MascotState {
    if (copilotStore.thinking) {
      return copilotStore.thinkingStage === 'executing_tool' ? 'tool_busy' : 'thinking'
    }
    if (copilotStore.hasPendingAction) {
      return 'confirm_pending'
    }
    return 'idle'
  }

  function transitionTo(target: MascotState, force = false): boolean {
    const decision = resolveMascotTransition(state.value, target, force)
    if (!decision.accepted) return false
    state.value = decision.nextState
    clearRevertTimer()
    const revertMs = decision.spec.autoRevertMs
    if (revertMs !== null) {
      revertTimer = setTimeout(() => {
        transitionTo(resolveBaselineState(), true)
      }, revertMs)
    }
    return true
  }

  function speakText(text: string): void {
    const speech = getSpeechPort()
    if (!voiceEnabled.value || !speech.isSupported()) return
    const started = speech.speak(text, resolveActiveClientLocale(), () => {
      speakingActive.value = false
    })
    speakingActive.value = started
  }

  function stopSpeaking(): void {
    getSpeechPort().stop()
    speakingActive.value = false
  }

  function toggleVoice(): void {
    voiceEnabled.value = !voiceEnabled.value
    writeStorage(STORAGE_KEYS.mascotVoiceEnabled, String(voiceEnabled.value), 'local')
    if (!voiceEnabled.value) {
      stopSpeaking()
    } else {
      showBubble(translateApiMessage('mascot.voiceOnTip'), 'info', { durationMs: 2600 })
    }
  }

  function setHover(hovering: boolean): void {
    if (hovering) {
      transitionTo('hover')
    } else if (state.value === 'hover') {
      transitionTo(resolveBaselineState(), true)
    }
  }

  function setListening(active: boolean): void {
    if (active) {
      transitionTo('listening')
    } else if (state.value === 'listening') {
      transitionTo(resolveBaselineState(), true)
    }
  }

  function openDrawer(): void {
    drawerOpen.value = true
    minimized.value = false
    writeStorage(STORAGE_KEYS.mascotCollapsed, 'false', 'local')
    unreadAlerts.value = 0
    dismissBubble()
  }

  function closeDrawer(): void {
    drawerOpen.value = false
    stopSpeaking()
    if (state.value === 'listening') {
      transitionTo(resolveBaselineState(), true)
    }
  }

  function toggleMinimized(): void {
    minimized.value = !minimized.value
    writeStorage(STORAGE_KEYS.mascotCollapsed, String(minimized.value), 'local')
    if (minimized.value) {
      drawerOpen.value = false
      dismissBubble()
      stopSpeaking()
    }
  }

  function savePosition(pos: MascotPosition): void {
    position.value = pos
    writeJsonStorage(STORAGE_KEYS.mascotPosition, pos, 'local')
  }

  function setContextKey(nextKey: MascotContextKey): void {
    contextKey.value = nextKey
    if (pagePolicy.value.mode === 'hidden') {
      drawerOpen.value = false
      dismissBubble()
    }
  }

  function setGazeOffset(offset: MascotGazeOffset): void {
    gazeOffset.value = offset
  }

  function handleViolationAlert(record: ViolationRecord): void {
    if (!isEnabled.value || profile.value?.alert_reaction_enabled === false) return
    if (record.status !== 'ACTIVE') return

    latestAlert.value = record
    if (!drawerOpen.value) {
      unreadAlerts.value += 1
    }

    const typeLabel = translateApiMessage(`enums.violation.${record.violation_type}`)
    const message = translateApiMessage('mascot.alertBubble', {
      camera: record.camera_id,
      type: typeLabel,
    })

    transitionTo('alert')
    showBubble(message, record.severity === 'CRITICAL' ? 'danger' : 'warning', {
      durationMs: MASCOT_DEFAULTS.autoRevertMs.alert,
      actionLabel: translateApiMessage('mascot.viewEvidenceAction'),
      violation: record,
    })
    speakText(message)
  }

  function init(): void {
    if (initialized) return
    initialized = true
    copilotStore.init()

    if (storedVoicePref === null && profile.value?.voice_enabled_by_default) {
      voiceEnabled.value = true
    }

    stopRealtimeSubscription = realtimeStore.subscribe({
      onViolationEvent(payload) {
        if (payload.operation === 'CREATED' || payload.record.status === 'ACTIVE') {
          handleViolationAlert(payload.record)
        }
      },
    })

    watch(
      () => [copilotStore.thinking, copilotStore.thinkingStage] as const,
      ([isThinking, stage]) => {
        if (isThinking) {
          transitionTo(stage === 'executing_tool' ? 'tool_busy' : 'thinking', true)
          return
        }
        if (copilotStore.lastOutcome === 'error') {
          transitionTo('error', true)
        } else if (copilotStore.hasPendingAction) {
          transitionTo('confirm_pending', true)
        } else if (copilotStore.lastOutcome === 'success') {
          transitionTo('speaking', true)
        } else {
          transitionTo('idle', true)
        }
      },
    )

    watch(
      () => copilotStore.messageVersion,
      () => {
        const latest = copilotStore.lastAssistantMessage
        if (!latest || copilotStore.thinking) return
        if (voiceEnabled.value && latest.text) {
          speakText(latest.text)
        }
        if (!drawerOpen.value && pagePolicy.value.mode === 'float') {
          showBubble(latest.text, latest.degraded ? 'warning' : 'info', {
            durationMs: MASCOT_DEFAULTS.autoRevertMs.speaking,
          })
        }
      },
    )

    watch(
      () => copilotStore.hasPendingAction,
      (pending) => {
        if (pending && !copilotStore.thinking) {
          transitionTo('confirm_pending', true)
        } else if (!pending && state.value === 'confirm_pending') {
          transitionTo(
            copilotStore.lastOutcome === 'success' ? 'success' : resolveBaselineState(),
            true,
          )
        }
      },
    )

    watch(
      () => copilotStore.uiConfig,
      (cfg) => {
        if (storedVoicePref === null && cfg?.mascot_profile) {
          voiceEnabled.value = cfg.mascot_profile.voice_enabled_by_default
        }
      },
    )
  }

  function dispose(): void {
    clearRevertTimer()
    clearBubbleTimer()
    stopRealtimeSubscription?.()
    stopRealtimeSubscription = undefined
    stopSpeaking()
    initialized = false
  }

  return {
    state,
    stateSpec,
    drawerOpen,
    minimized,
    voiceEnabled,
    voiceSupported,
    speakingActive,
    unreadAlerts,
    latestAlert,
    bubble,
    gazeOffset,
    contextKey,
    pagePolicy,
    position,
    isEnabled,
    personaName,
    init,
    dispose,
    transitionTo,
    showBubble,
    dismissBubble,
    speakText,
    stopSpeaking,
    toggleVoice,
    setHover,
    setListening,
    openDrawer,
    closeDrawer,
    toggleMinimized,
    savePosition,
    setContextKey,
    setGazeOffset,
    handleViolationAlert,
  }
})
