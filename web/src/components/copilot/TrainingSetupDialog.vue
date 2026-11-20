<template>
  <el-dialog v-model="open" :title="t('copilot.createTrainingTitle')" width="520px" destroy-on-close>
    <el-form label-position="top">
      <el-form-item :label="t('copilot.sourceReport')">
        <el-input :model-value="target?.label || ''" disabled />
      </el-form-item>
      <el-form-item :label="t('copilot.trainingTopic')" required>
        <el-input v-model="form.title" maxlength="255" show-word-limit :placeholder="t('copilot.trainingTopicPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('copilot.targetCount')" required>
        <el-input-number v-model="form.targetCount" :min="1" :step="1" controls-position="right" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('copilot.questionCount')">
        <el-input-number v-model="form.questionCount" :min="1" :max="20" :step="1" controls-position="right" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('copilot.passScore')">
        <el-input-number v-model="form.passScore" :min="0" :max="100" :step="1" controls-position="right" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="busy" @click="submit">{{ t('tasks.proposeAction') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAgentConversationId, proposeTrainingAction } from '@/api/chat'
import { useAppI18n } from '@/i18n/useAppI18n'
import { extractApiError } from '@/utils/errors'
import type { GuidedSelectionOption, PendingAction } from '@/types/contract'

const props = defineProps<{
  modelValue: boolean
  target: GuidedSelectionOption | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  proposed: [pending: PendingAction]
}>()

const { t } = useAppI18n()
const busy = ref(false)
const form = reactive({
  title: '',
  targetCount: undefined as number | undefined,
  questionCount: 5,
  passScore: 80,
})

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

watch(
  () => [props.modelValue, props.target] as const,
  ([visible]) => {
    if (!visible) return
    form.title = t('copilot.defaultTrainingTopic')
    form.targetCount = undefined
    form.questionCount = 5
    form.passScore = 80
  },
)

async function submit(): Promise<void> {
  const report = props.target
  const title = form.title.trim()
  const targetCount = form.targetCount
  if (!report || !title || !targetCount || !Number.isInteger(targetCount) || targetCount < 1) {
    ElMessage.warning(t('copilot.trainingValidation'))
    return
  }
  busy.value = true
  try {
    const pending = await proposeTrainingAction(getAgentConversationId(), {
      report_id: report.option_id,
      title,
      document_ids: [],
      target_count: targetCount,
      question_count: form.questionCount,
      pass_score: form.passScore,
    })
    open.value = false
    emit('proposed', pending)
  } catch (err: unknown) {
    ElMessage.error(extractApiError(err, t('copilot.trainingProposeFailed')))
  } finally {
    busy.value = false
  }
}
</script>
