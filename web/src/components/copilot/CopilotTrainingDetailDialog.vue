<template>
  <el-dialog v-model="open" :title="t('copilot.trainingDetailTitle')" width="800px" destroy-on-close @closed="clearQr">
    <div v-loading="loading">
      <template v-if="training">
        <div class="report-detail-head">
          <strong>{{ training.title }}</strong>
          <el-tag :type="training.status === 'PUBLISHED' ? 'success' : 'warning'">
            {{ training.status === 'PUBLISHED' ? t('enums.trainingStatus.PUBLISHED') : t('enums.trainingStatus.DRAFT') }}
          </el-tag>
        </div>
        <p>{{ t('copilot.trainingMeta', { target: training.target_count, questions: training.question_count, passScore: training.pass_score }) }}</p>
        <div v-if="trainingStats" class="training-detail-stats">
          {{ t('copilot.trainingStatsSummary', { completed: trainingStats.completed_count, target: trainingStats.target_count, rate: trainingStats.completion_rate, avg: trainingStats.average_score }) }}
        </div>
        <h4>{{ t('copilot.studyMaterial') }}</h4>
        <p class="report-detail-text">{{ training.material }}</p>
        <h4>{{ t('copilot.multipleChoice') }}</h4>
        <div v-for="(question, index) in training.questions" :key="index" class="training-question">
          <strong>{{ index + 1 }}. {{ question.stem }}</strong>
          <p v-for="(option, optionIndex) in question.options" :key="optionIndex" :class="{ 'correct-option': optionIndex === question.answer }">
            {{ String.fromCharCode(65 + optionIndex) }}. {{ option }}
          </p>
          <small v-if="question.evidence">{{ t('copilot.questionEvidence', { evidence: question.evidence }) }}</small>
        </div>
        <div v-if="training.public_url" class="training-access">
          <img v-if="qrUrl" :src="qrUrl" :alt="t('copilot.qrAlt')" />
          <a v-if="learningPath(training.public_url)" :href="learningPath(training.public_url)" target="_blank" rel="noopener">
            {{ t('copilot.openWorkerPage') }}
          </a>
        </div>
      </template>
    </div>
    <template #footer>
      <el-button @click="open = false">{{ t('common.close') }}</el-button>
      <router-link to="/learning" class="training-link" @click="open = false">{{ t('copilot.manageInLearning') }}</router-link>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getTraining, getTrainingQr, getTrainingStats, type Training, type TrainingStatistics } from '@/api/learning'
import { useObjectUrl } from '@/composables/useObjectUrl'
import { useAppI18n } from '@/i18n/useAppI18n'
import { learningPath } from '@/utils/deployment'

const props = defineProps<{
  modelValue: boolean
  trainingId: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const { t } = useAppI18n()
const { objectUrl: qrUrl, setBlob: setQrBlob, clear: clearQr } = useObjectUrl()
const loading = ref(false)
const training = ref<Training | null>(null)
const trainingStats = ref<TrainingStatistics | null>(null)

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

watch(
  () => [props.modelValue, props.trainingId] as const,
  async ([visible, trainingId]) => {
    if (!visible || !trainingId) return
    clearQr()
    training.value = null
    trainingStats.value = null
    loading.value = true
    try {
      const task = await getTraining(trainingId)
      if (!props.modelValue || props.trainingId !== trainingId) return
      training.value = task
      if (task.status === 'PUBLISHED') {
        const [statsRes, qrRes] = await Promise.allSettled([getTrainingStats(trainingId), getTrainingQr(trainingId)])
        if (!props.modelValue || training.value?.task_id !== trainingId) return
        if (statsRes.status === 'fulfilled') trainingStats.value = statsRes.value
        if (qrRes.status === 'fulfilled') setQrBlob(qrRes.value)
      }
    } catch {
      ElMessage.error(t('copilot.trainingDetailLoadFailed'))
    } finally {
      loading.value = false
    }
  },
)
</script>

<style scoped>
.report-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-detail-head strong { font-size: 14px; color: #303b51; }
.report-detail-text { line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.training-link { color: #5b55bb; font-size: 12px; font-weight: 600; text-decoration: none; margin-left: 12px; }
.training-link:hover { text-decoration: underline; }
.training-detail-stats { padding: 10px 12px; background: #f0f3ff; border-radius: 9px; color: #555cac; font-size: 13px; }
.training-question { padding: 14px 0; border-top: 1px solid #e7eaf0; }
.training-question strong { display: block; margin-bottom: 8px; }
.training-question p { margin: 4px 0 4px 16px; }
.training-question .correct-option { color: #278263; font-weight: 600; }
.training-question small { display: block; color: #7a8596; margin-top: 8px; }
.training-access { display: flex; align-items: center; gap: 20px; margin-top: 18px; }
.training-access img { width: 150px; height: 150px; object-fit: contain; }
</style>
