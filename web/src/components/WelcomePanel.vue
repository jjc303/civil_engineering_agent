<template>
  <section class="welcome-panel">
    <span class="welcome-icon"><el-icon><Service /></el-icon></span>
    <span class="section-kicker">你的施工安全助手</span>
    <h3>从现场风险，到安全教育</h3>
    <p>从一个问题开始，查看现场数据、报告与培训任务。<br />涉及执行的操作，会先请你确认。</p>
    <div class="starter-grid">
      <button
        v-for="starter in starters"
        :key="starter.question"
        :disabled="thinking"
        @click="$emit('selectPrompt', starter.question)"
      >
        <el-icon><component :is="starter.icon" /></el-icon>
        <strong>{{ starter.title }}</strong>
        <span>{{ starter.description }}</span>
        <b aria-hidden="true">↗</b>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Service, Picture, Document, Operation } from '@element-plus/icons-vue'

defineProps<{
  thinking: boolean
}>()

defineEmits<{
  selectPrompt: [question: string]
}>()

const starters = [
  { title: '现场状态', description: '查看摄像头运行情况', question: '查看所有摄像头状态', icon: Picture },
  { title: '安全报告', description: '查阅已有风险总结', question: '查看安全报告', icon: Document },
  { title: '培训任务', description: '跟进安全教育安排', question: '查看培训任务', icon: Operation },
]
</script>

<style scoped>
.welcome-panel { margin: auto 0; padding: 24px 8px 38px; text-align: center; flex-shrink: 0; }
.welcome-icon { display: grid; place-items: center; width: 62px; height: 62px; margin: 0 auto 22px; background: linear-gradient(140deg, #f1edfb, #faf8ff); border: 1px solid #e8e1f8; border-radius: 20px; color: #8972d0; font-size: 29px; }
.section-kicker { display: block; color: #9b8abc; font-size: 11px; letter-spacing: .5px; }
.welcome-panel h3 { font-size: 27px; margin: 12px 0; letter-spacing: -.6px; color: #3d4059; }
.welcome-panel p { font-size: 13px; line-height: 1.9; color: #8c94a4; margin: 0 0 26px; }
.starter-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; max-width: 670px; margin: 0 auto; }
.starter-grid button { position: relative; display: flex; flex-direction: column; gap: 8px; padding: 18px 15px; text-align: left; border: 1px solid #ebe6f4; background: #fdfcfe; border-radius: 14px; cursor: pointer; color: #5d526f; font: inherit; }
.starter-grid button > .el-icon { font-size: 20px; color: #9a86cc; margin-bottom: 6px; }
.starter-grid strong { font-size: 13px; font-weight: 600; }
.starter-grid span { font-size: 11px; color: #9b94a8; }
.starter-grid b { position: absolute; top: 17px; right: 16px; font-size: 13px; color: #b7a8cf; font-weight: 400; }
.starter-grid button:hover { border-color: #c9bbe9; background: #f6f2fd; }
@media (max-width: 760px) { .welcome-panel { padding: 10px 0 22px; } .welcome-panel h3 { font-size: 23px; } .welcome-panel p { font-size: 12px; } .starter-grid { gap: 7px; } .starter-grid button { padding: 13px 10px; } .starter-grid span { font-size: 10px; line-height: 1.6; } .starter-grid b { display: none; } }
@media (max-height: 800px) { .welcome-panel { padding-top: 2px; padding-bottom: 8px; } .welcome-icon { display: none; } .welcome-panel h3 { font-size: 22px; margin: 8px 0; } .welcome-panel p { margin-bottom: 16px; font-size: 12px; } .starter-grid button { padding: 13px; gap: 6px; } .starter-grid button > .el-icon { margin-bottom: 2px; } }
</style>