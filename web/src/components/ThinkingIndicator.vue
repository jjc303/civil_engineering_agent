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
          <strong>{{ waitSeconds >= 20 ? '回答仍在准备中，请稍候' : '正在查询并整理回答' }}</strong>
          <small>
            已等待 {{ waitSeconds }} 秒{{ waitSeconds >= 20 ? ' · 模型和工具查询可能需要一些时间，请勿重复提交。' : ' · 完成后会显示在这里。' }}
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Service, Loading } from '@element-plus/icons-vue'

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