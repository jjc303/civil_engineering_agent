<template>
  <div
    class="locale-toggle"
    :class="{ compact }"
    role="group"
    :aria-label="label"
  >
    <button
      v-for="option in options"
      :key="option.code"
      type="button"
      class="locale-option"
      :aria-pressed="modelValue === option.code"
      :title="option.label"
      @click="$emit('select', option.code)"
    >
      {{ option.shortLabel }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { LocaleStrategy, SupportedLocale } from '@/i18n/types'

defineProps<{
  modelValue: SupportedLocale
  options: ReadonlyArray<LocaleStrategy>
  label: string
  compact?: boolean
}>()

defineEmits<{
  select: [locale: SupportedLocale]
}>()
</script>

<style scoped>
.locale-toggle {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  border-radius: 20px;
  background: #f2f1f8;
  border: 1px solid #e9e6f3;
  flex-shrink: 0;
}

.locale-option {
  border: 0;
  background: transparent;
  color: #8a90a2;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  min-width: 28px;
  min-height: 26px;
  padding: 5px 10px;
  border-radius: 16px;
  transition: background 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
}

.locale-option:hover {
  color: #6559da;
}

.locale-option[aria-pressed='true'] {
  background: #ffffff;
  color: #6559da;
  font-weight: 600;
  box-shadow: 0 2px 7px #43386c15;
}

.locale-toggle.compact .locale-option {
  min-width: 25px;
  min-height: 24px;
  padding: 4px 8px;
  font-size: 11px;
}
</style>
