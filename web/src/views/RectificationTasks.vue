<template>
  <div class="tasks-page operations-workbench">
    <WorkspaceIntro eyebrow="RECTIFICATION TASKS" :title="t('tasks.title')" :description="t('tasks.description')">
      <el-button :icon="Refresh" :loading="loading" @click="load">{{ t('tasks.refreshTasks') }}</el-button><el-button type="primary" :icon="Plus" @click="openCreate">{{ t('tasks.createTask') }}</el-button>
    </WorkspaceIntro>
    <WorkspaceSummary :label="t('tasks.summaryLabel')" :items="summaryItems" />
    <el-alert v-if="loadError" class="workbench-error" :title="t('tasks.loadError')" type="warning" :closable="false" show-icon />

    <el-card shadow="never" class="filter-card">
      <div class="filter-heading"><strong>{{ t('tasks.filterTitle') }}</strong><span>{{ t('tasks.filterDesc') }}</span></div>
      <el-form :inline="true">
        <el-form-item :label="t('tasks.statusLabel')"><el-select v-model="filters.status" clearable :placeholder="t('tasks.allStatuses')" style="width: 150px"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item :label="t('tasks.ownerLabel')"><el-input v-model="filters.owner" clearable :placeholder="t('tasks.ownerPlaceholder')" /></el-form-item>
        <el-form-item><el-checkbox v-model="filters.overdue">{{ t('tasks.overdueOnly') }}</el-checkbox></el-form-item>
        <el-form-item><el-button type="primary" @click="search">{{ t('common.filter') }}</el-button><el-button @click="reset">{{ t('common.reset') }}</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-alert v-if="pendingAction" type="warning" :closable="false" class="pending-card">
      <template #title>{{ t('tasks.pendingPrefix', { summary: pendingAction.summary }) }}</template>
      <div class="pending-actions"><span>{{ t('tasks.expiresAt', { time: formatTime(pendingAction.expires_at_utc) }) }}</span><el-button size="small" type="primary" :loading="confirming" @click="confirmPending">{{ t('tasks.confirmExecute') }}</el-button><el-button size="small" :disabled="confirming" @click="cancelPending">{{ t('common.cancel') }}</el-button></div>
    </el-alert>

    <el-card shadow="never" class="table-card">
      <template #header><div class="section-card-heading"><strong>{{ t('tasks.tableTitle') }}</strong><span>{{ t('tasks.tableSubtitle', { total: dataLoaded ? total : '—' }) }}</span></div></template>
      <el-table v-loading="loading" :data="tasks" :empty-text="t('tasks.emptyText')">
        <el-table-column prop="title" :label="t('tasks.colTask')" min-width="170" show-overflow-tooltip />
        <el-table-column prop="owner" :label="t('tasks.colOwner')" width="120" />
        <el-table-column :label="t('tasks.colViolation')" min-width="170"><template #default="{ row }"><div>{{ violationLabel(row.violation_type) }}</div><small>{{ row.camera_id }}</small></template></el-table-column>
        <el-table-column :label="t('tasks.colDueAt')" width="175"><template #default="{ row }"><span :class="{ overdue: isOverdue(row) }">{{ formatTime(row.due_at_utc) }}</span></template></el-table-column>
        <el-table-column :label="t('tasks.colStatus')" width="120"><template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column :label="t('tasks.colActions')" width="265"><template #default="{ row }"><el-button size="small" link type="primary" @click="openDetail(row.task_id)">{{ t('tasks.actionDetail') }}</el-button><el-button v-if="canEdit(row)" size="small" link @click="openEdit(row)">{{ t('tasks.actionEdit') }}</el-button><el-button v-if="canEdit(row)" size="small" link type="success" @click="openStatus(row, 'COMPLETED')">{{ t('tasks.actionComplete') }}</el-button><el-button v-if="canEdit(row)" size="small" link type="danger" @click="openStatus(row, 'CANCELLED')">{{ t('tasks.actionCancel') }}</el-button></template></el-table-column>
      </el-table>
      <p class="table-scroll-hint">{{ t('tasks.scrollHint') }}</p>
      <div class="pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>

    <el-dialog v-model="createVisible" :title="t('tasks.createDialogTitle')" width="620px" destroy-on-close>
      <el-form label-position="top"><el-form-item :label="t('tasks.fieldViolation')" required><el-select v-model="createForm.eventUuid" filterable style="width:100%" :placeholder="t('tasks.selectViolationPlaceholder')"><el-option v-for="event in activeViolations" :key="event.event_uuid" :label="`${violationLabel(event.violation_type)} · ${event.camera_id} · ${formatTime(event.occurred_at_utc)}`" :value="event.event_uuid" /></el-select></el-form-item><el-form-item :label="t('tasks.fieldRequirement')" required><el-input v-model="createForm.title" /></el-form-item><el-form-item :label="t('tasks.ownerLabel')" required><el-input v-model="createForm.owner" /></el-form-item><el-form-item :label="t('tasks.fieldDueAt')" required><el-date-picker v-model="createForm.dueAt" type="datetime" style="width:100%" /></el-form-item><el-form-item :label="t('tasks.fieldDescription')"><el-input v-model="createForm.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="proposing" @click="proposeCreate">{{ t('tasks.proposeAction') }}</el-button></template>
    </el-dialog>

    <el-dialog v-model="editVisible" :title="editForm.status === 'COMPLETED' ? t('tasks.completeDialogTitle') : editForm.status === 'CANCELLED' ? t('tasks.cancelDialogTitle') : t('tasks.editDialogTitle')" width="560px" destroy-on-close>
      <el-form label-position="top"><el-form-item :label="t('tasks.ownerLabel')"><el-input v-model="editForm.owner" /></el-form-item><el-form-item :label="t('tasks.fieldDueAt')"><el-date-picker v-model="editForm.dueAt" type="datetime" style="width:100%" /></el-form-item><el-form-item :label="t('tasks.fieldTaskStatus')"><el-select v-model="editForm.status" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item :label="t('tasks.fieldNote')"><el-input v-model="editForm.note" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="editVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="proposing" @click="proposeEdit">{{ t('tasks.proposeAction') }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="t('tasks.detailDrawerTitle')" size="620px"><template v-if="detail"><el-descriptions :column="1" border><el-descriptions-item :label="t('tasks.detailTask')">{{ detail.task.title }}</el-descriptions-item><el-descriptions-item :label="t('tasks.ownerLabel')">{{ detail.task.owner }}</el-descriptions-item><el-descriptions-item :label="t('tasks.fieldDueAt')">{{ formatTime(detail.task.due_at_utc) }}</el-descriptions-item><el-descriptions-item :label="t('tasks.detailDescription')">{{ detail.task.description || '-' }}</el-descriptions-item><el-descriptions-item :label="t('tasks.detailViolation')">{{ violationLabel(detail.violation.violation_type) }} · {{ detail.violation.camera_id }}</el-descriptions-item></el-descriptions><div class="drawer-section"><h4>{{ t('tasks.detailEvidenceTitle') }}</h4><el-image v-if="detail.violation.snapshot_uri" :src="resolveMediaUrl(detail.violation.snapshot_uri)" :preview-src-list="[resolveMediaUrl(detail.violation.snapshot_uri)]" preview-teleported fit="cover" class="evidence-image" /><el-empty v-else :description="t('tasks.detailNoSnapshot')" /></div><div class="drawer-section"><h4>{{ t('tasks.detailAuditTitle') }}</h4><el-timeline><el-timeline-item v-for="audit in detail.audits" :key="audit.audit_id" :timestamp="formatTime(audit.created_at_utc)"><strong>{{ audit.action }}</strong> · {{ audit.actor }}<div v-if="Object.keys(audit.detail_safe_json).length" class="audit-detail">{{ JSON.stringify(audit.detail_safe_json) }}</div></el-timeline-item></el-timeline></div></template></el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { cancelPendingAction, confirmPendingAction, getAgentConversationId } from '@/api/chat'
import { createRectificationTask, fetchRectificationTask, fetchRectificationTasks, updateRectificationTask } from '@/api/rectificationTasks'
import { fetchViolations } from '@/api/violations'
import { resolveMediaUrl } from '@/api/client'
import WorkspaceIntro from '@/components/WorkspaceIntro.vue'
import WorkspaceSummary from '@/components/WorkspaceSummary.vue'
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import { useDictionariesStore } from '@/stores/dictionaries'
import type { PendingAction, RectificationTaskDetail, RectificationTaskRecord, RectificationTaskStatus, ViolationRecord, ViolationType } from '@/types/contract'

const { t, formatDateTime } = useAppI18n()
const dictionaries = useDictionariesStore()
dictionaries.ensureLoaded()

const tasks = ref<RectificationTaskRecord[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20); const loading = ref(false); const proposing = ref(false); const confirming = ref(false)
const route = useRoute()
const activeViolations = ref<ViolationRecord[]>([]); const pendingAction = ref<PendingAction | null>(null); const createVisible = ref(false); const editVisible = ref(false); const detailVisible = ref(false); const detail = ref<RectificationTaskDetail | null>(null); const editingTaskId = ref('')
const filters = reactive<{ status?: RectificationTaskStatus; owner: string; overdue: boolean }>({ status: undefined, owner: '', overdue: false })
const dataLoaded = ref(false), loadError = ref(false)
const summaryItems = computed(() => [
  { label: t('tasks.summaryTotal'), value: dataLoaded.value ? total.value : '—', hint: t('tasks.summaryTotalHint') },
  { label: t('tasks.summaryRunning'), value: dataLoaded.value ? tasks.value.filter(item => ['PENDING', 'IN_PROGRESS'].includes(item.status)).length : '—', hint: t('tasks.summaryRunningHint') },
  { label: t('tasks.summaryOverdue'), value: dataLoaded.value ? tasks.value.filter(isOverdue).length : '—', hint: t('tasks.summaryOverdueHint'), tone: 'warning' as const },
])
const createForm = reactive({ eventUuid: '', title: '', description: '', owner: '', dueAt: null as Date | null })
const editForm = reactive({ owner: '', dueAt: null as Date | null, status: 'PENDING' as RectificationTaskStatus, note: '' })
const TASK_STATUS_CODES: ReadonlyArray<RectificationTaskStatus> = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED']
const statusOptions = computed(() =>
  TASK_STATUS_CODES.map((code) => ({ value: code, label: t(`enums.taskStatus.${code}`) })),
)

const conversationId = getAgentConversationId
async function load() { loading.value = true; try { const data = await fetchRectificationTasks({ status: filters.status, owner: filters.owner || undefined, overdue: filters.overdue || undefined, limit: pageSize.value, offset: (page.value - 1) * pageSize.value }); tasks.value = data.items; total.value = data.total; dataLoaded.value = true; loadError.value = false } catch { loadError.value = true } finally { loading.value = false } }
function search() { page.value = 1; load() }
function reset() { filters.status = undefined; filters.owner = ''; filters.overdue = false; page.value = 1; load() }
async function openCreate() {
  try {
    const camera = typeof route.query.camera_id === 'string' ? route.query.camera_id : undefined
    const data = await fetchViolations({ status: 'ACTIVE', camera_id: camera, limit: 100 })
    const selectedId = typeof route.query.event_uuid === 'string' ? route.query.event_uuid : ''
    const selectedTime = typeof route.query.event_time === 'string' ? new Date(route.query.event_time).getTime() : NaN
    if (selectedId && !data.items.some(event => event.event_uuid === selectedId) && Number.isFinite(selectedTime)) {
      const historical = await fetchViolations({camera_id: camera, start_time_utc: new Date(selectedTime - 1000).toISOString(), end_time_utc: new Date(selectedTime + 1000).toISOString(), limit:500})
      const selected = historical.items.find(event => event.event_uuid === selectedId)
      if (selected) data.items.unshift(selected)
    }
    activeViolations.value = data.items
    createForm.eventUuid = data.items.some(event => event.event_uuid === selectedId) ? selectedId : ''
    createForm.title = ''; createForm.description = ''; createForm.owner = ''; createForm.dueAt = null
    createVisible.value = true
  } catch { ElMessage.error(t('tasks.violationsLoadFailed')) }
}
async function proposeCreate() {
  if (!createForm.eventUuid || !createForm.title.trim() || !createForm.owner.trim() || !createForm.dueAt) return ElMessage.warning(t('tasks.createValidation'))
  proposing.value = true
  try {
    await createRectificationTask({
      conversation_id: conversationId(),
      event_uuid: createForm.eventUuid,
      title: createForm.title.trim(),
      description: createForm.description.trim() || undefined,
      owner: createForm.owner.trim(),
      due_at_utc: createForm.dueAt.toISOString(),
    })
    createVisible.value = false
    ElMessage.success(t('tasks.createdMsg'))
    await load()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || t('tasks.createFailedMsg'))
  } finally {
    proposing.value = false
  }
}
function openEdit(task: RectificationTaskRecord) { editingTaskId.value = task.task_id; editForm.owner = task.owner; editForm.dueAt = new Date(task.due_at_utc); editForm.status = task.status; editForm.note = ''; editVisible.value = true }
function openStatus(task: RectificationTaskRecord, status: RectificationTaskStatus) { openEdit(task); editForm.status = status }
async function proposeEdit() {
  if (!editingTaskId.value || !editForm.owner.trim() || !editForm.dueAt) return ElMessage.warning(t('tasks.editValidation'))
  proposing.value = true
  try {
    await updateRectificationTask(editingTaskId.value, {
      conversation_id: conversationId(),
      owner: editForm.owner.trim(),
      due_at_utc: editForm.dueAt.toISOString(),
      status: editForm.status,
      note: editForm.note.trim() || undefined,
    })
    editVisible.value = false
    ElMessage.success(t('tasks.updatedMsg'))
    await load()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || t('tasks.updateFailedMsg'))
  } finally {
    proposing.value = false
  }
}
async function confirmPending() { if (!pendingAction.value) return; confirming.value = true; try { await confirmPendingAction(pendingAction.value.confirmation_id, conversationId()); pendingAction.value = null; ElMessage.success(t('tasks.executedMsg')); await load() } finally { confirming.value = false } }
async function cancelPending() { if (!pendingAction.value) return; await cancelPendingAction(pendingAction.value.confirmation_id, conversationId()); pendingAction.value = null; ElMessage.info(t('tasks.cancelledPendingMsg')) }
async function openDetail(taskId: string) { detail.value = await fetchRectificationTask(taskId); detailVisible.value = true }
function formatTime(value: string) { return formatDateTime(value) }
function canEdit(task: RectificationTaskRecord) { return !['COMPLETED', 'CANCELLED'].includes(task.status) }
function isOverdue(task: RectificationTaskRecord) { return ['PENDING', 'IN_PROGRESS'].includes(task.status) && new Date(task.due_at_utc).getTime() < Date.now() }
function statusLabel(status: RectificationTaskStatus) { return t(`enums.taskStatus.${status}`) }
function statusTag(status: RectificationTaskStatus): 'warning' | 'primary' | 'success' | 'info' { return ({ PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' } as const)[status] }
function violationLabel(type: ViolationType) { return dictionaries.violationLabel(type) }
useLocaleRefresh(() => {
  void load()
  if (detailVisible.value && detail.value?.task.task_id) {
    void openDetail(detail.value.task.task_id)
  }
})
onMounted(load)
</script>

<style scoped>
.pending-card{margin-bottom:22px;border-radius:14px;border:1px solid #efdfc0;padding:18px 22px}.pending-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:10px}.pending-actions>span{font-size:12px;color:#a48b67;margin-right:auto}.overdue{color:#bc7365;font-weight:600}.drawer-section{margin-top:24px}.evidence-image{width:100%;max-height:300px;background:#151b21;border-radius:12px}.audit-detail{color:#8791a3;font-size:12px;margin-top:4px;word-break:break-all}
</style>
