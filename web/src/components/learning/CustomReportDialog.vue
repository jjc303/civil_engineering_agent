<template>
  <el-dialog v-model="open" :title="t('learning.customReportTitle')" width="600px">
    <el-date-picker
      v-model="range"
      type="daterange"
      value-format="YYYY-MM-DD"
      :range-separator="t('common.rangeSeparator')"
      :start-placeholder="t('common.startDate')"
      :end-placeholder="t('common.endDate')"
    />
    <p class="hint">{{ t('learning.customReportHint') }}</p>
    <template #footer>
      <el-button @click="open = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="busy" @click="submit">{{ t('learning.generateReportDraft') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppI18n } from '@/i18n/useAppI18n'

const props = defineProps<{
  modelValue: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  submit: [range: [string, string]]
}>()

const { t } = useAppI18n()
const range = ref<string[]>([])

const open = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

function submit() {
  if (range.value?.length !== 2) {
    ElMessage.warning(t('learning.selectRangeWarning'))
    return
  }
  emit('submit', [range.value[0]!, range.value[1]!])
}
</script>

<style scoped>
.hint { color: #919aab; font-size: 12px; }
</style>
