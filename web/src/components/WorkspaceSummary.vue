<template>
  <section class="workspace-summary" :aria-label="label">
    <article v-for="item in items" :key="item.label" class="summary-item" :class="item.tone"><span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.hint }}</small></article>
  </section>
</template>
<script setup lang="ts">
defineProps<{ label: string; items: ReadonlyArray<{ label: string; value: number | string; hint: string; tone?: 'warning' | 'success' }> }>()
</script>
<style scoped>
.workspace-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:24px}.summary-item{background:#fff;border:1px solid #ece9f4;border-radius:18px;padding:21px 24px;display:flex;flex-direction:column;position:relative;overflow:hidden}.summary-item:before{content:'';position:absolute;right:-22px;top:-29px;width:92px;height:92px;border:16px solid #f6f3fc;border-radius:50%;pointer-events:none}.summary-item>span{font-size:12px;color:#8390a1;position:relative}.summary-item strong{font-size:31px;font-weight:600;line-height:1.25;letter-spacing:-.8px;color:#625384;margin-top:13px;position:relative;font-variant-numeric:tabular-nums}.summary-item small{font-size:11px;color:#9a9fb0;margin-top:9px;position:relative}.summary-item.warning strong{color:#b57f65}.summary-item.success strong{color:#5e8c7b}@media(max-width:650px){.workspace-summary{gap:9px;margin-bottom:18px}.summary-item{padding:16px 12px;border-radius:14px}.summary-item strong{font-size:27px}.summary-item>span{font-size:11px}.summary-item small{font-size:10px;line-height:1.6}.summary-item:before{display:none}}
</style>
