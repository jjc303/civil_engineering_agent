<template>
  <div v-if="hasError" class="error-boundary-fallback">
    <div class="error-boundary-content">
      <el-icon :size="32"><WarningFilled /></el-icon>
      <h3>页面组件异常</h3>
      <p>安全助手界面遇到临时问题，请刷新页面重试。</p>
      <el-button type="primary" @click="reset">刷新组件</el-button>
    </div>
  </div>
  <div v-else class="error-boundary-wrapper">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

const hasError = ref(false)

onErrorCaptured((err: Error, instance, info) => {
  console.error('[ErrorBoundary]', err.message, info)
  hasError.value = true
  return false // prevent propagation
})

function reset() {
  hasError.value = false
}
</script>

<style scoped>
.error-boundary-wrapper {
  display: contents;
}
.error-boundary-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 40px 20px;
  background: #faf9fc;
  border: 1px solid #ede9f4;
  border-radius: 16px;
}
.error-boundary-content {
  text-align: center;
  color: #5d526f;
}
.error-boundary-content .el-icon {
  color: #f59e0b;
  margin-bottom: 16px;
}
.error-boundary-content h3 {
  font-size: 18px;
  margin: 0 0 10px;
  color: #3d4059;
}
.error-boundary-content p {
  font-size: 13px;
  color: #8c94a4;
  margin: 0 0 20px;
}
</style>