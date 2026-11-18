<template>
  <aside class="side-column">
    <section class="surface task-section">
      <div class="section-head">
        <div>
          <span class="section-kicker">{{ t('learning.trainingExecutionKicker') }}</span>
          <h2>{{ t('learning.weeklyTasksTitle') }}</h2>
        </div>
        <el-button link @click="$emit('openTrainingComposer')">{{ t('learning.newTask') }}</el-button>
      </div>

      <div v-if="weeklyTraining.length" class="weekly-task-list">
        <button v-for="task in weeklyTraining" :key="task.task_id" class="weekly-task" @click="$emit('showTraining', task)">
          <span class="task-top">
            <b>{{ task.title }}</b>
            <span :class="task.status === 'PUBLISHED' ? 'status-running' : 'status-draft'">
              {{ task.status === 'PUBLISHED' ? t('enums.trainingStatus.RUNNING') : t('enums.trainingStatus.PENDING_PUBLISH') }}
            </span>
          </span>
          <span class="task-count">
            {{ t('learning.taskParticipants', { target: task.target_count, completed: task.weekly?.completed_count ?? 0 }) }}
          </span>
          <el-progress
            :percentage="task.target_count ? Math.min(100, Math.round(100 * (task.weekly?.completed_count ?? 0) / task.target_count)) : 0"
            :stroke-width="6"
            :show-text="false"
          />
          <span class="task-bottom">
            {{ t('learning.avgScore', { score: task.weekly?.average_score ?? 0 }) }}
            <i>{{ t('learning.viewDetailArrow') }}</i>
          </span>
        </button>
      </div>

      <div v-else class="empty-state compact">
        <strong>{{ t('learning.noWeeklyTasks') }}</strong>
        <p>{{ t('learning.noWeeklyTasksHint') }}</p>
        <el-button type="primary" plain @click="$emit('openTrainingComposer')">{{ t('learning.generateTraining') }}</el-button>
      </div>
    </section>

    <section class="advice-panel">
      <span class="advice-icon">✦</span>
      <span class="section-kicker">AGENT INSIGHT</span>
      <h2>{{ t('learning.aiAdviceTitle') }}</h2>
      <p v-if="insights?.advice">{{ insights.advice }}</p>
      <p v-else>{{ insightsLoading ? t('learning.aiAdviceLoading') : t('learning.aiAdviceEmpty') }}</p>
      <small v-if="insights" class="advice-updated">
        {{ t('learning.aiAdviceUpdated', { time: formatInsightTime(insights.generated_at_utc) }) }}
      </small>
      <el-button class="advice-action" @click="$emit('openTrainingComposer')">{{ t('learning.generateTrainingFromAdvice') }}</el-button>
      <el-button class="advice-refresh" link :loading="insightsLoading" @click="$emit('refreshInsights')">{{ t('learning.regenerateAdvice') }}</el-button>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { Training, WeeklyInsights, WeeklyOverview } from '@/api/learning'
import { useAppI18n } from '@/i18n/useAppI18n'

defineProps<{
  weeklyTraining: Array<Training & { weekly: WeeklyOverview['weekly_tasks'][number] }>
  insights: WeeklyInsights | null
  insightsLoading: boolean
  formatInsightTime: (value: string) => string
}>()

defineEmits<{
  openTrainingComposer: []
  showTraining: [task: Training]
  refreshInsights: []
}>()

const { t } = useAppI18n()
</script>

<style scoped>
.side-column { display: grid; gap: 20px; min-width: 0; }
.surface { border: 1px solid #eceef5; border-radius: 20px; background: #fff; box-shadow: 0 5px 20px #37406607; padding: 24px; }
.section-kicker { color: #7d6bd5; font-size: 10px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.section-head h2 { margin: 5px 0 0; font-size: 21px; letter-spacing: -.02em; }
.weekly-task-list { display: grid; gap: 11px; }
.weekly-task { border: 1px solid #ebeef4; border-radius: 13px; background: #fff; text-align: left; padding: 15px; width: 100%; cursor: pointer; display: grid; gap: 11px; }
.weekly-task:hover { background: #faf9ff; }
.task-top, .task-bottom { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.task-top b { font-size: 13px; color: #3c4658; line-height: 1.4; }
.status-running, .status-draft { font-size: 10px; white-space: nowrap; border-radius: 10px; padding: 4px 7px; }
.status-running { background: #e9f6ef; color: #449871; }
.status-draft { background: #fff3e4; color: #b58242; }
.task-count, .task-bottom { font-size: 11px; color: #8c96a5; }
.task-bottom i { float: right; font-style: normal; color: #7665cc; }
.empty-state.compact { padding: 30px 12px; text-align: center; color: #7f8a9d; background: #fafbfe; border-radius: 14px; }
.empty-state.compact strong { display: block; color: #697487; font-size: 14px; }
.empty-state.compact p { font-size: 12px; margin: 8px 0 0; line-height: 1.7; }
.empty-state.compact .el-button { margin-top: 16px; }
.advice-panel { border-radius: 20px; padding: 25px; color: #fff; background: linear-gradient(148deg, #6355be, #8c77d8); box-shadow: 0 16px 35px #6150bf22; }
.advice-panel .section-kicker { color: #d8d1ff; }
.advice-icon { display: block; font-size: 30px; margin-bottom: 9px; }
.advice-panel h2 { margin: 8px 0 14px; font-size: 20px; }
.advice-panel p { line-height: 1.85; font-size: 13px; white-space: pre-line; color: #f0edff; min-height: 84px; }
.advice-panel .el-button { margin-top: 12px; }
.advice-panel .advice-action { background: #fff; border-color: #fff; color: #5444ad; font-weight: 600; }
.advice-panel .advice-action:hover, .advice-panel .advice-action:focus-visible { background: #f0edff; border-color: #f0edff; color: #47369f; }
.advice-panel .advice-action:active { background: #e5dfff; border-color: #e5dfff; color: #3f308f; }
.advice-panel .advice-refresh { color: #f0ebff; }
.advice-panel .advice-refresh:hover { color: #fff; }
.advice-updated { display: block; margin: 0 0 8px; color: #e1dbff; font-size: 11px; }

@media (max-width: 1080px) { .side-column { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
  .side-column { grid-template-columns: 1fr; }
  .surface, .advice-panel { padding: 18px; border-radius: 16px; }
}
</style>
