<template>
  <header class="workspace-intro">
    <div class="intro-copy"><span class="intro-eyebrow">{{ eyebrow }}</span><h1>{{ title }}</h1><p>{{ description }}</p></div>
    <div v-if="$slots.default" class="intro-actions"><slot /></div>
  </header>
</template>
<script setup lang="ts">
defineProps<{ eyebrow: string; title: string; description: string }>()
</script>
<style scoped>
.workspace-intro{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:26px}.intro-copy{min-width:0}.intro-eyebrow{display:block;color:#9584c7;font-size:10px;letter-spacing:1.8px;font-weight:600;margin-bottom:10px}.intro-copy h1{margin:0;font-size:27px;font-weight:650;letter-spacing:-.5px;color:#343b51;line-height:1.4}.intro-copy p{margin:10px 0 0;font-size:13px;line-height:1.8;color:#8791a2}.intro-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0}.intro-actions :deep(.el-button){margin-left:0;border-radius:11px;font-size:12px;min-height:37px}
@media(max-width:900px){.workspace-intro{align-items:flex-start;gap:18px;flex-wrap:wrap}.intro-actions{flex-shrink:1}}@media(max-width:600px){.workspace-intro{margin-bottom:20px}.intro-copy h1{font-size:24px}.intro-copy p{font-size:12px}.intro-actions{gap:8px}}
</style>
