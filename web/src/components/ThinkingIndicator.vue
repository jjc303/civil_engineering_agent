<template>
  <div class="message-row assistant">
    <div class="avatar">
      <el-avatar :icon="Service" :size="36" />
    </div>
    <div class="message-content">
      <div class="sender-name">{{ assistantName }}</div>
      <div class="agent-bubble thinking-bubble">
        <el-icon class="is-loading"><Loading /></el-icon>
        <div>
          <strong>{{ waitSeconds >= 20 ? t('copilot.thinkingLongWait') : t('copilot.thinkingNormal') }}</strong>
          <small>
            {{ t('copilot.thinkingWaited', { seconds: waitSeconds }) }}{{ waitSeconds >= 20 ? t('copilot.thinkingLongHint') : t('copilot.thinkingShortHint') }}
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Service, Loading } from '@element-plus/icons-vue'
import { useAppI18n } from '@/i18n/useAppI18n'

const { t } = useAppI18n()

defineProps<{
  waitSeconds: number
  assistantName: string
}>()
</script>

<style scoped>
.message-row {
  display: flex;
  gap: 12px;
  max-width: 94%;
  min-width: 0;
  flex-shrink: 0;
  align-self: flex-start;
}
.message-content { min-width: 0; }
.avatar { flex-shrink: 0; padding-top: 2px; }
.avatar :deep(.el-avatar) { background: #eee8f9; color: #8b74bd; }
.sender-name { font-size: 12px; color: #9b9fad; margin-bottom: 8px; }
.agent-bubble {
  background: #f9f8fc;
  border: 1px solid #ede9f4;
  color: #4a5269;
  padding: 18px 20px;
  border-radius: 4px 16px 16px 16px;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.thinking-bubble {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #8873bb;
}
.thinking-bubble strong { font-size: 13px; font-weight: 500; }
.thinking-bubble small { display: block; font-size: 11px; color: #a29bad; }
</style>