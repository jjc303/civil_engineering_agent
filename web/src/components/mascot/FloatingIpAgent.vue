<template>
  <div
    v-if="visible"
    ref="anchorRef"
    class="floating-mascot-root"
    :style="rootStyle"
  >
    <MascotBubbleTip
      v-if="!drawerOpen && !minimized"
      :bubble="bubble"
      :persona-name="personaName"
      :placement="horizontalPlacement"
      @dismiss="mascotStore.dismissBubble()"
      @action="handleBubbleAction"
    />

    <MascotChatDrawer
      :open="drawerOpen"
      :mascot-state="state"
      :state-label="stateLabel"
      :persona-name="personaName"
      :route-title="routeTitle"
      :page-policy="pagePolicy"
      :reduced-motion="reducedMotion"
      :speaking-active="speakingActive"
      :voice-enabled="voiceEnabled"
      :voice-supported="voiceSupported"
      :placement="horizontalPlacement"
      :vertical-placement="verticalPlacement"
      :max-height-px="drawerMaxHeightPx"
      @close="mascotStore.closeDrawer()"
      @toggle-voice="mascotStore.toggleVoice()"
      @listening="mascotStore.setListening($event)"
    />

    <!-- Compact dock mode on /copilot or when minimized -->
    <div v-if="isDockMode || minimized" class="dock-pill">
      <button
        type="button"
        class="dock-trigger"
        :aria-label="t('mascot.expandAria', { name: personaName })"
        @click="handleDockClick"
      >
        <MascotAvatarHost
          :state="state"
          :gaze-offset="gazeOffset"
          :reduced-motion="reducedMotion"
          :speaking-active="speakingActive"
          :size="MASCOT_DEFAULTS.dockSizePx"
        />
        <span class="dock-label">{{ personaName }}</span>
        <span v-if="unreadAlerts > 0" class="unread-badge">{{ unreadBadgeText }}</span>
      </button>
    </div>

    <!-- Full floating IP mascot -->
    <div
      v-else
      ref="handleRef"
      class="mascot-stage"
      :class="{ dragging: isDragging }"
      @mouseenter="mascotStore.setHover(true)"
      @mouseleave="mascotStore.setHover(false)"
    >
      <div class="stage-quick-actions" role="toolbar" :aria-label="t('mascot.toolbarAria')">
        <button
          v-if="voiceSupported"
          type="button"
          class="mini-tool-btn"
          :class="{ active: voiceEnabled }"
          :title="voiceEnabled ? t('mascot.muteVoice') : t('mascot.enableVoice')"
          :aria-label="voiceEnabled ? t('mascot.muteVoice') : t('mascot.enableVoice')"
          @click.stop="mascotStore.toggleVoice()"
        >
          <el-icon><Microphone /></el-icon>
        </button>
        <button
          type="button"
          class="mini-tool-btn"
          :title="t('mascot.minimizeAria')"
          :aria-label="t('mascot.minimizeAria')"
          @click.stop="mascotStore.toggleMinimized()"
        >
          <el-icon><Minus /></el-icon>
        </button>
      </div>

      <button
        type="button"
        class="mascot-avatar-btn"
        :aria-expanded="drawerOpen"
        :aria-label="t('mascot.toggleDrawerAria', { name: personaName, state: stateLabel })"
        @pointerdown="onPointerDown"
        @click="onAvatarClick"
      >
        <MascotAvatarHost
          :state="state"
          :gaze-offset="gazeOffset"
          :reduced-motion="reducedMotion"
          :has-pending-action="hasPendingAction"
          :unread-alerts="unreadAlerts"
          :speaking-active="speakingActive"
          :size="MASCOT_DEFAULTS.sizePx"
        />
        <span v-if="unreadAlerts > 0" class="unread-badge">{{ unreadBadgeText }}</span>
        <span v-else-if="hasPendingAction" class="pending-badge">!</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useDraggable, useMouse, usePreferredReducedMotion, useWindowSize } from '@vueuse/core'
import { Microphone, Minus } from '@element-plus/icons-vue'
import MascotAvatarHost from '@/components/mascot/MascotAvatarHost.vue'
import MascotBubbleTip from '@/components/mascot/MascotBubbleTip.vue'
import MascotChatDrawer from '@/components/mascot/MascotChatDrawer.vue'
import { useCopilotModals } from '@/composables/useCopilotModals'
import { useAppI18n } from '@/i18n/useAppI18n'
import { MASCOT_DEFAULTS } from '@/mascot/config'
import type { MascotContextKey } from '@/mascot/pageContextRegistry'
import { resolveRouteTitle } from '@/router'
import { useCopilotStore } from '@/stores/copilot'
import { useMascotStore, type MascotBubble } from '@/stores/mascot'

const { t } = useAppI18n()
const route = useRoute()
const mascotStore = useMascotStore()
const copilotStore = useCopilotStore()
const { openViolationRecord } = useCopilotModals()

const {
  state,
  stateSpec,
  drawerOpen,
  minimized,
  voiceEnabled,
  voiceSupported,
  speakingActive,
  unreadAlerts,
  bubble,
  gazeOffset,
  pagePolicy,
  position,
  isEnabled,
  personaName,
} = storeToRefs(mascotStore)
const { hasPendingAction } = storeToRefs(copilotStore)

const anchorRef = ref<HTMLElement | null>(null)
const handleRef = ref<HTMLElement | null>(null)

const { width: winWidth, height: winHeight } = useWindowSize()
const { x: mouseX, y: mouseY } = useMouse({ type: 'client' })
const preferredMotion = usePreferredReducedMotion()
const reducedMotion = computed(() => preferredMotion.value === 'reduce')

const isDockMode = computed(() => pagePolicy.value.mode === 'dock')
const visible = computed(() => isEnabled.value && pagePolicy.value.mode !== 'hidden')
const stateLabel = computed(() => t(stateSpec.value.statusLabelKey))
const routeTitle = computed(() => resolveRouteTitle(route))
const unreadBadgeText = computed(() =>
  unreadAlerts.value > MASCOT_DEFAULTS.maxUnreadBadgeCount
    ? `${MASCOT_DEFAULTS.maxUnreadBadgeCount}+`
    : String(unreadAlerts.value),
)

const currentWidgetSize = computed(() =>
  isDockMode.value || minimized.value ? MASCOT_DEFAULTS.dockSizePx : MASCOT_DEFAULTS.sizePx,
)

function clampPosition(rawX: number, rawY: number): { x: number; y: number } {
  const margin = MASCOT_DEFAULTS.viewportMarginPx
  const size = currentWidgetSize.value
  const maxX = Math.max(margin, winWidth.value - size - margin)
  const maxY = Math.max(margin, winHeight.value - size - margin)
  return {
    x: Math.min(Math.max(margin, rawX), maxX),
    y: Math.min(Math.max(margin, rawY), maxY),
  }
}

const initialPos = computed(() => {
  if (position.value) {
    return clampPosition(position.value.x, position.value.y)
  }
  return clampPosition(
    winWidth.value - MASCOT_DEFAULTS.sizePx - MASCOT_DEFAULTS.defaultRightOffsetPx,
    winHeight.value - MASCOT_DEFAULTS.sizePx - MASCOT_DEFAULTS.defaultBottomOffsetPx,
  )
})

let dragStartPointer: { x: number; y: number } | null = null
let movedBeyondThreshold = false

const { x, y, isDragging } = useDraggable(handleRef, {
  initialValue: initialPos.value,
  onStart(_pos, event) {
    dragStartPointer = { x: event.clientX, y: event.clientY }
    movedBeyondThreshold = false
  },
  onMove(pos, event) {
    const clamped = clampPosition(pos.x, pos.y)
    x.value = clamped.x
    y.value = clamped.y
    if (dragStartPointer) {
      const dist = Math.hypot(event.clientX - dragStartPointer.x, event.clientY - dragStartPointer.y)
      if (dist > MASCOT_DEFAULTS.dragThresholdPx) {
        movedBeyondThreshold = true
      }
    }
  },
  onEnd(pos) {
    const clamped = clampPosition(pos.x, pos.y)
    const margin = MASCOT_DEFAULTS.viewportMarginPx
    const rightLimit = winWidth.value - currentWidgetSize.value - margin
    let snappedX = clamped.x
    if (Math.abs(clamped.x - margin) <= MASCOT_DEFAULTS.edgeSnapThresholdPx) {
      snappedX = margin
    } else if (Math.abs(clamped.x - rightLimit) <= MASCOT_DEFAULTS.edgeSnapThresholdPx) {
      snappedX = rightLimit
    }
    x.value = snappedX
    y.value = clamped.y
    mascotStore.savePosition({ x: snappedX, y: clamped.y })
    dragStartPointer = null
  },
})

const effectivePos = computed(() => {
  if (isDockMode.value || minimized.value) {
    return clampPosition(
      winWidth.value - currentWidgetSize.value - MASCOT_DEFAULTS.defaultRightOffsetPx,
      winHeight.value - currentWidgetSize.value - MASCOT_DEFAULTS.defaultBottomOffsetPx,
    )
  }
  return clampPosition(x.value, y.value)
})

const horizontalPlacement = computed<'left' | 'right'>(() =>
  effectivePos.value.x > winWidth.value / 2 ? 'left' : 'right',
)

const verticalSpace = computed(() => {
  const spaceAbove = effectivePos.value.y - MASCOT_DEFAULTS.viewportMarginPx
  const spaceBelow =
    winHeight.value - (effectivePos.value.y + currentWidgetSize.value) - MASCOT_DEFAULTS.viewportMarginPx
  return { spaceAbove, spaceBelow }
})

const verticalPlacement = computed<'above' | 'below'>(() =>
  verticalSpace.value.spaceAbove >= verticalSpace.value.spaceBelow ? 'above' : 'below',
)

const drawerMaxHeightPx = computed(() => {
  const available =
    verticalPlacement.value === 'above'
      ? verticalSpace.value.spaceAbove
      : verticalSpace.value.spaceBelow
  const ratioCap = Math.round((winHeight.value * MASCOT_DEFAULTS.drawerMaxHeightVh) / 100)
  return Math.max(
    MASCOT_DEFAULTS.minDrawerHeightPx,
    Math.min(MASCOT_DEFAULTS.drawerMaxHeightPx, ratioCap, available),
  )
})

const rootStyle = computed(() => ({
  left: `${effectivePos.value.x}px`,
  top: `${effectivePos.value.y}px`,
  zIndex: String(MASCOT_DEFAULTS.zIndexFloat),
}))

watch([winWidth, winHeight], () => {
  const clamped = clampPosition(x.value, y.value)
  x.value = clamped.x
  y.value = clamped.y
})

watch([mouseX, mouseY, effectivePos, reducedMotion], ([mx, my, pos, isReduced]) => {
  if (isReduced || drawerOpen.value || isDockMode.value || minimized.value) {
    mascotStore.setGazeOffset({ x: 0, y: 0 })
    return
  }
  const cx = pos.x + currentWidgetSize.value / 2
  const cy = pos.y + currentWidgetSize.value / 2
  const dx = mx - cx
  const dy = my - cy
  const dist = Math.hypot(dx, dy) || 1
  const maxOffset = MASCOT_DEFAULTS.maxGazeOffsetPx
  const scale = Math.min(1, dist / MASCOT_DEFAULTS.gazeFalloffPx) * maxOffset
  mascotStore.setGazeOffset({
    x: Number(((dx / dist) * scale).toFixed(2)),
    y: Number(((dy / dist) * scale).toFixed(2)),
  })
})

watch(
  () => [route.path, route.meta?.ipContextKey, route.query?.camera_id, route.query?.event_uuid] as const,
  ([_path, contextKeyMeta, camId, evtUuid]) => {
    const key = (typeof contextKeyMeta === 'string' ? contextKeyMeta : 'default') as MascotContextKey
    mascotStore.setContextKey(key)
    copilotStore.setPageContext({
      route_key: key,
      route_title: resolveRouteTitle(route) || undefined,
      camera_id: typeof camId === 'string' ? camId : undefined,
      event_uuid: typeof evtUuid === 'string' ? evtUuid : undefined,
    })
  },
  { immediate: true },
)

function onPointerDown(event: PointerEvent): void {
  dragStartPointer = { x: event.clientX, y: event.clientY }
  movedBeyondThreshold = false
}

function onAvatarClick(): void {
  if (movedBeyondThreshold) {
    movedBeyondThreshold = false
    return
  }
  if (drawerOpen.value) {
    mascotStore.closeDrawer()
  } else {
    mascotStore.openDrawer()
  }
}

function handleDockClick(): void {
  if (isDockMode.value) {
    mascotStore.showBubble(t(pagePolicy.value.greetingKey), 'info', {
      durationMs: MASCOT_DEFAULTS.autoRevertMs.speaking,
    })
    return
  }
  mascotStore.toggleMinimized()
}

function handleBubbleAction(activeBubble: MascotBubble): void {
  mascotStore.dismissBubble()
  if (activeBubble.violation) {
    openViolationRecord(activeBubble.violation)
    return
  }
  mascotStore.openDrawer()
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && drawerOpen.value) {
    mascotStore.closeDrawer()
  }
}

onMounted(() => {
  mascotStore.init()
  const initPos = initialPos.value
  x.value = initPos.x
  y.value = initPos.y
  document.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
  mascotStore.dispose()
})
</script>

<style scoped>
.floating-mascot-root {
  position: fixed;
  touch-action: none;
}

.mascot-stage {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
}

.mascot-stage.dragging {
  cursor: grabbing;
}

.mascot-avatar-btn {
  position: relative;
  border: 0;
  padding: 0;
  background: transparent;
  border-radius: 50%;
  cursor: inherit;
  transition: transform 0.18s ease;
}

.mascot-avatar-btn:hover {
  transform: translateY(-2px);
}

.stage-quick-actions {
  position: absolute;
  top: -8px;
  right: -6px;
  display: flex;
  gap: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.18s ease;
  z-index: 2;
}

.mascot-stage:hover .stage-quick-actions,
.mascot-stage:focus-within .stage-quick-actions {
  opacity: 1;
  pointer-events: auto;
}

.mini-tool-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #e2dcf5;
  background: #ffffff;
  color: #6b7280;
  display: grid;
  place-items: center;
  font-size: 11px;
  box-shadow: 0 3px 8px rgba(45, 36, 92, 0.12);
}

.mini-tool-btn:hover,
.mini-tool-btn.active {
  color: #6559da;
  border-color: #c4b5fd;
  background: #f5f3ff;
}

.unread-badge,
.pending-badge {
  position: absolute;
  top: 2px;
  left: 2px;
  min-width: 19px;
  height: 19px;
  padding: 0 5px;
  border-radius: 999px;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  display: grid;
  place-items: center;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.22);
}

.unread-badge {
  background: #ef4444;
}

.pending-badge {
  background: #f59e0b;
}

.dock-pill {
  position: relative;
}

.dock-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px 4px 6px;
  border-radius: 999px;
  border: 1px solid #e5dff5;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(8px);
  box-shadow: 0 8px 22px rgba(45, 36, 92, 0.14);
  color: #463d70;
  font-size: 12px;
  font-weight: 600;
}

.dock-trigger:hover {
  border-color: #c4b5fd;
  background: #f8f6fe;
}

.dock-label {
  white-space: nowrap;
}
</style>
