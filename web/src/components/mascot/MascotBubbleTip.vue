<template>
  <Transition name="mascot-bubble">
    <div
      v-if="bubble"
      :class="['mascot-bubble', `tone-${bubble.tone}`, `place-${placement}`]"
      role="status"
      aria-live="polite"
    >
      <div class="bubble-header">
        <span class="bubble-dot" />
        <strong>{{ personaName }}</strong>
        <button
          type="button"
          class="bubble-close"
          :aria-label="t('mascot.dismissBubbleAria')"
          @click.stop="$emit('dismiss')"
        >
          ×
        </button>
      </div>
      <p class="bubble-text">{{ bubble.text }}</p>
      <div v-if="bubble.actionLabel" class="bubble-actions">
        <button type="button" class="bubble-action-btn" @click.stop="$emit('action', bubble)">
          {{ bubble.actionLabel }} ↗
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { useAppI18n } from '@/i18n/useAppI18n'
import type { MascotBubble } from '@/stores/mascot'

defineProps<{
  bubble: MascotBubble | null
  personaName: string
  placement: 'left' | 'right'
}>()

defineEmits<{
  dismiss: []
  action: [bubble: MascotBubble]
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.mascot-bubble {
  position: absolute;
  bottom: calc(100% + 10px);
  width: 248px;
  max-width: calc(100vw - 36px);
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid #e5dff5;
  box-shadow: 0 12px 30px rgba(45, 36, 92, 0.16);
  color: #394056;
  font-size: 12px;
  line-height: 1.65;
  pointer-events: auto;
}

.place-left {
  right: 0;
}

.place-right {
  left: 0;
}

.tone-danger {
  border-color: #fecaca;
  background: rgba(255, 249, 249, 0.97);
}

.tone-warning {
  border-color: #fde68a;
  background: rgba(255, 253, 244, 0.97);
}

.tone-success {
  border-color: #a7f3d0;
}

.bubble-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
}

.bubble-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #7462d6;
}

.tone-danger .bubble-dot {
  background: #ef4444;
}

.tone-warning .bubble-dot {
  background: #f59e0b;
}

.tone-success .bubble-dot {
  background: #10b981;
}

.bubble-header strong {
  font-size: 12px;
  color: #343b51;
}

.bubble-close {
  margin-left: auto;
  border: 0;
  background: none;
  color: #9ca3af;
  font-size: 16px;
  line-height: 1;
  padding: 2px 4px;
}

.bubble-close:hover {
  color: #4b5563;
}

.bubble-text {
  margin: 0;
  color: #4b5563;
  overflow-wrap: anywhere;
}

.bubble-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}

.bubble-action-btn {
  border: 0;
  border-radius: 8px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 600;
  color: #6559da;
  background: #f0ecfc;
}

.bubble-action-btn:hover {
  background: #e4ddfa;
}

.mascot-bubble-enter-active,
.mascot-bubble-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.mascot-bubble-enter-from,
.mascot-bubble-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.97);
}
</style>
