<template>
  <aside class="copilot-aside" :aria-label="t('copilot.asideAria')">
    <section class="education-guide">
      <span class="guide-icon"><el-icon><Document /></el-icon></span>
      <span class="section-kicker">{{ t('copilot.asideConnect') }}</span>
      <h3>{{ t('copilot.asideHeadline1') }}<br />{{ t('copilot.asideHeadline2') }}</h3>
      <p>{{ t('copilot.asideDesc') }}</p>
      <router-link to="/learning">{{ t('copilot.openLearningWorkbench') }} <span>↗</span></router-link>
    </section>
    <section class="workflow-card">
      <span class="section-kicker">{{ t('copilot.workflowKicker') }}</span>
      <h3>{{ t('copilot.workflowTitle') }}</h3>
      <ol>
        <li><b>01</b><div><strong>{{ t('copilot.workflowStep1Title') }}</strong><span>{{ t('copilot.workflowStep1Desc') }}</span></div></li>
        <li><b>02</b><div><strong>{{ t('copilot.workflowStep2Title') }}</strong><span>{{ t('copilot.workflowStep2Desc') }}</span></div></li>
        <li><b>03</b><div><strong>{{ t('copilot.workflowStep3Title') }}</strong><span>{{ t('copilot.workflowStep3Desc') }}</span></div></li>
      </ol>
      <router-link to="/violations">{{ t('copilot.viewViolationsLink') }}</router-link>
    </section>
    <p class="aside-note">{{ t('copilot.asideNote') }}</p>
  </aside>
</template>

<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import { useAppI18n } from '@/i18n/useAppI18n'

const { t } = useAppI18n()
</script>

<style scoped>
.copilot-aside { display: flex; flex-direction: column; gap: 18px; overflow: auto; scrollbar-width: thin; }
.section-kicker { display: block; color: #9b8abc; font-size: 11px; letter-spacing: .5px; }
.education-guide { padding: 26px 23px 24px; color: #fff; background: linear-gradient(148deg, #6355be, #8c77d8); border-radius: 20px; position: relative; overflow: hidden; flex-shrink: 0; }
.education-guide:after { content: ''; position: absolute; width: 170px; height: 170px; border: 1px solid #ffffff18; border-radius: 50%; top: -74px; right: -61px; pointer-events: none; }
.guide-icon { display: grid; place-items: center; width: 38px; height: 38px; background: #ffffff1a; border: 1px solid #ffffff26; border-radius: 12px; margin-bottom: 22px; font-size: 20px; }
.education-guide .section-kicker { color: #e0d9f5; }
.education-guide h3 { font-size: 22px; line-height: 1.5; letter-spacing: -.3px; margin: 12px 0; font-weight: 600; }
.education-guide p { font-size: 12px; line-height: 1.9; color: #e3def3; margin: 0 0 24px; }
.education-guide a { display: flex; justify-content: space-between; background: #ffffff18; color: #fff; text-decoration: none; font-size: 12px; padding: 12px 13px; border-radius: 10px; border: 1px solid #ffffff22; }
.education-guide a:hover { background: #ffffff28; }
.workflow-card { padding: 24px 22px; background: #fff; border: 1px solid #eeebf5; border-radius: 20px; flex-shrink: 0; }
.workflow-card h3 { font-size: 16px; font-weight: 600; margin: 10px 0 22px; }
.workflow-card ol { margin: 0; padding: 0; list-style: none; display: grid; gap: 22px; }
.workflow-card li { display: flex; gap: 12px; }
.workflow-card li > b { font-size: 11px; color: #a694c9; font-weight: 500; background: #f6f2fc; border-radius: 8px; padding: 7px; align-self: flex-start; }
.workflow-card strong { font-size: 12px; font-weight: 500; }
.workflow-card li span { display: block; margin-top: 5px; font-size: 11px; line-height: 1.6; color: #9a9fac; }
.workflow-card > a { display: block; margin-top: 24px; padding-top: 18px; border-top: 1px solid #f0edf6; font-size: 12px; color: #9380bd; text-decoration: none; }
.aside-note { margin: 0; padding: 0 10px 14px; font-size: 11px; line-height: 1.9; color: #aaa5b4; flex-shrink: 0; }

@media (max-width: 1180px) { .education-guide, .workflow-card { padding: 22px 18px; } }
@media (max-width: 1000px) { .copilot-aside { display: none; } }
</style>
