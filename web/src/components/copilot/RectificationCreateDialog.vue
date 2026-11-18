<template>
  <el-dialog v-model="open" :title="t('copilot.createTaskTitle')" width="520px" destroy-on-close>
    <el-form label-position="top">
      <el-form-item :label="t('copilot.selectedViolation')">
        <el-input :model-value="target?.label || ''" disabled />
      </el-form-item>
      <el-form-item :label="t('tasks.fieldRequirement')" required>
        <el-input v-model="form.title" :placeholder="t('copilot.rectificationTitlePlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('tasks.ownerLabel')" required>
        <el-input v-model="form.owner" :placeholder="t('copilot.rectificationOwnerPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('tasks.fieldDueAt')" required>
        <el-date-picker v-model="form.dueAt" type="datetime" :placeholder="t('copilot.dueAtPlaceholder')" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('tasks.fieldDescription')">
        <el-input v-model="form.description" type="textarea" :rows="3" />
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
import { getAgentConversationId } from '@/api/chat'
import { proposeRectificationTaskCreate } from '@/api/rectificationTasks'
import { useAppI18n } from '@/i18n/useAppI18n'
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
  owner: '',
  dueAt: null as Date | null,
  description: '',
})

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

watch(
  () => [props.modelValue, props.target] as const,
  ([visible]) => {
    if (!visible) return
    form.title = ''
    form.owner = ''
    form.dueAt = null
    form.description = ''
  },
)

async function submit(): Promise<void> {
  const target = props.target
  if (!target || !form.title.trim() || !form.owner.trim() || !form.dueAt) {
    ElMessage.warning(t('copilot.rectificationValidation'))
    return
  }
  busy.value = true
  try {
    const pending = await proposeRectificationTaskCreate({
      conversation_id: getAgentConversationId(),
      event_uuid: target.option_id,
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      owner: form.owner.trim(),
      due_at_utc: form.dueAt.toISOString(),
    })
    open.value = false
    emit('proposed', pending)
  } catch (err: unknown) {
    const typed = err as { response?: { data?: { detail?: string } }; message?: string }
    ElMessage.error(typed?.response?.data?.detail || typed?.message || t('copilot.rectificationProposeFailed'))
  } finally {
    busy.value = false
  }
}
</script>
