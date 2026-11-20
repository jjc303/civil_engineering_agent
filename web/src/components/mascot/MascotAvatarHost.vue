<template>
  <component
    :is="activeComponent"
    :state="state"
    :gaze-offset="gazeOffset"
    :reduced-motion="reducedMotion"
    :has-pending-action="hasPendingAction"
    :unread-alerts="unreadAlerts"
    :speaking-active="speakingActive"
    :size="size"
  />
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import SvgSafetyMascot from '@/components/mascot/SvgSafetyMascot.vue'
import { DEFAULT_MASCOT_RENDERER, type MascotGazeOffset, type MascotRendererId } from '@/mascot/renderer'
import type { MascotState } from '@/mascot/stateMachine'

const RENDERER_COMPONENTS: Readonly<Record<MascotRendererId, Component>> = {
  svg: SvgSafetyMascot,
  // Future Rive adapter drops in here without modifying FloatingIpAgent or MascotChatDrawer.
  rive: SvgSafetyMascot,
}

const props = withDefaults(
  defineProps<{
    renderer?: MascotRendererId
    state: MascotState
    gazeOffset?: MascotGazeOffset
    reducedMotion?: boolean
    hasPendingAction?: boolean
    unreadAlerts?: number
    speakingActive?: boolean
    size?: number
  }>(),
  {
    renderer: DEFAULT_MASCOT_RENDERER,
    gazeOffset: () => ({ x: 0, y: 0 }),
    reducedMotion: false,
    hasPendingAction: false,
    unreadAlerts: 0,
    speakingActive: false,
    size: 86,
  },
)

const activeComponent = computed(() => RENDERER_COMPONENTS[props.renderer] || SvgSafetyMascot)
</script>
