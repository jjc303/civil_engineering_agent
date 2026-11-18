<template>
  <el-dialog v-model="open" :title="t('learning.trainingDialogTitle')" width="920px" destroy-on-close @closed="clearQr">
    <template v-if="training">
      <div class="dialog-meta">
        <strong>{{ training.title }}</strong>
        <el-tag :type="training.status === 'PUBLISHED' ? 'success' : 'warning'">
          {{ training.status === 'PUBLISHED' ? t('enums.trainingStatus.PUBLISHED') : t('enums.trainingStatus.DRAFT') }}
        </el-tag>
      </div>

      <div class="source-list">
        <span>{{ t('learning.referencedDocs') }}</span>
        <p v-if="!training.selected_documents.length" class="hint">{{ t('learning.noReferencedDocs') }}</p>
        <p v-for="source in training.selected_documents" :key="source.document_id" class="citation">
          {{ source.title }} · {{ source.document_type === 'STANDARD' ? t('enums.documentType.STANDARD_SHORT') : t('enums.documentType.ACCIDENT_REPORT') }}
        </p>
      </div>

      <el-form label-position="top">
        <el-form-item :label="t('learning.taskName')">
          <el-input v-model="training.title" :disabled="training.status !== 'DRAFT'" />
        </el-form-item>
        <div class="form-row">
          <el-form-item :label="t('copilot.targetCount')">
            <el-input-number v-model="training.target_count" :min="1" :disabled="training.status !== 'DRAFT'" />
          </el-form-item>
          <el-form-item :label="t('copilot.passScore')">
            <el-input-number v-model="training.pass_score" :min="0" :max="100" :disabled="training.status !== 'DRAFT'" />
          </el-form-item>
        </div>
        <el-form-item :label="t('copilot.studyMaterial')">
          <el-input v-model="training.material" type="textarea" :rows="7" :disabled="training.status !== 'DRAFT'" />
        </el-form-item>

        <div v-for="(question, index) in training.questions" :key="index" class="question-editor">
          <strong>{{ t('learning.questionIndex', { index: index + 1 }) }}</strong>
          <el-input v-model="question.stem" :disabled="training.status !== 'DRAFT'" />
          <div v-for="(_, optionIndex) in question.options" :key="optionIndex" class="option-row">
            <span>{{ String.fromCharCode(65 + optionIndex) }}</span>
            <el-input v-model="question.options[optionIndex]" :disabled="training.status !== 'DRAFT'" />
          </div>
          <el-radio-group v-model="question.answer" :disabled="training.status !== 'DRAFT'">
            <el-radio v-for="(_, optionIndex) in question.options" :key="optionIndex" :value="optionIndex">
              {{ t('learning.optionCorrect', { letter: String.fromCharCode(65 + optionIndex) }) }}
            </el-radio>
          </el-radio-group>
          <p v-if="question.evidence" class="hint">{{ t('copilot.questionEvidence', { evidence: question.evidence }) }}</p>
        </div>
      </el-form>

      <div v-if="training.status === 'PUBLISHED'">
        <p>
          {{ t('learning.studyUrlLabel') }}
          <a :href="learningPath(training.public_url || '') || '#'" target="_blank" rel="noopener">{{ training.public_url }}</a>
        </p>
        <img v-if="qrUrl" class="qr" :src="qrUrl" :alt="t('copilot.qrAlt')" />
        <div v-if="stats" class="stats">
          <span>{{ t('learning.trainingStatsCompletion', { completed: stats.completed_count, target: stats.target_count, rate: Math.min(100, stats.completion_rate) }) }}</span>
          <span v-if="stats.excess_completed_count">{{ t('learning.excessCompleted', { count: stats.excess_completed_count }) }}</span>
          <span>{{ t('learning.trainingStatsAvg', { score: stats.average_score }) }}</span>
          <span>{{ t('learning.trainingStatsPassRate', { rate: stats.pass_rate }) }}</span>
          <el-table :data="stats.submissions" size="small">
            <el-table-column prop="worker_id" :label="t('learning.colWorkerId')" />
            <el-table-column prop="worker_name" :label="t('learning.colWorkerName')" />
            <el-table-column prop="score" :label="t('learning.colScore')" />
            <el-table-column :label="t('learning.colPassed')">
              <template #default="scope">{{ scope.row.passed ? t('common.yes') : t('common.no') }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="dialog-actions">
        <template v-if="training.status === 'DRAFT'">
          <el-button :loading="busy" @click="$emit('save', training)">{{ t('learning.saveDraft') }}</el-button>
          <el-button type="primary" :loading="busy" @click="$emit('publish', training)">{{ t('learning.confirmPublish') }}</el-button>
        </template>
        <el-button type="danger" plain :disabled="busy" @click="$emit('delete', training, stats?.completed_count)">
          {{ t('learning.deleteItem', { kind: training.status === 'DRAFT' ? t('learning.trainingDraftKind') : t('learning.trainingTaskKind') }) }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/learning'
import { useObjectUrl } from '@/composables/useObjectUrl'
import { useAppI18n } from '@/i18n/useAppI18n'
import { learningPath } from '@/utils/deployment'

const props = defineProps<{
  modelValue: boolean
  training: api.Training | null
  busy: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  save: [training: api.Training]
  publish: [training: api.Training]
  delete: [training: api.Training, completedCount?: number]
}>()

const { t } = useAppI18n()
const { objectUrl: qrUrl, setBlob: setQrBlob, clear: clearQr } = useObjectUrl()
const stats = ref<api.TrainingStatistics | null>(null)

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

watch(
  () => [props.modelValue, props.training?.task_id, props.training?.status] as const,
  async ([visible, taskId, status]) => {
    clearQr()
    stats.value = null
    if (!visible || !taskId || status !== 'PUBLISHED') return
    try {
      const [statsData, qrBlob] = await Promise.all([api.getTrainingStats(taskId), api.getTrainingQr(taskId)])
      if (!props.modelValue || props.training?.task_id !== taskId) return
      stats.value = statsData
      setQrBlob(qrBlob)
    } catch {
      ElMessage.warning(t('learning.trainingPartialLoadWarn'))
    }
  },
)
</script>

<style scoped>
.hint { color: #919aab; font-size: 12px; }
.dialog-meta, .dialog-actions, .form-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.dialog-meta { justify-content: space-between; margin-bottom: 16px; }
.dialog-actions { justify-content: flex-end; margin-top: 20px; }
.source-list { margin: 16px 0; }
.citation { padding-left: 10px; border-left: 2px solid #aa9fe6; color: #788398; font-size: 12px; }
.question-editor { border: 1px solid #e8ecf4; border-radius: 12px; padding: 14px; margin: 14px 0; display: grid; gap: 9px; }
.option-row { display: flex; align-items: center; gap: 8px; }
.qr { width: 180px; height: 180px; margin: 14px 0; }
.stats { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stats > span { padding: 7px 12px; border-radius: 9px; background: #eef0ff; color: #6258ac; font-size: 12px; }
.stats .el-table { width: 100%; }
</style>
