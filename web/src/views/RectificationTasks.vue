<template>
  <div class="tasks-page">
    <div class="header-section">
      <div><h2>整改任务中心</h2><p>跟踪违规整改、负责人、截止时间与处理审计。</p></div>
      <div class="header-actions"><el-button :icon="Refresh" @click="load">刷新</el-button><el-button type="primary" :icon="Plus" @click="openCreate">新建整改任务</el-button></div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 150px"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="负责人"><el-input v-model="filters.owner" clearable placeholder="姓名或班组" /></el-form-item>
        <el-form-item><el-checkbox v-model="filters.overdue">仅看逾期</el-checkbox></el-form-item>
        <el-form-item><el-button type="primary" @click="search">筛选</el-button><el-button @click="reset">重置</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-alert v-if="pendingAction" type="warning" :closable="false" class="pending-card">
      <template #title>待确认操作：{{ pendingAction.summary }}</template>
      <div class="pending-actions"><span>有效期至 {{ formatTime(pendingAction.expires_at_utc) }}</span><el-button size="small" type="primary" :loading="confirming" @click="confirmPending">确认执行</el-button><el-button size="small" :disabled="confirming" @click="cancelPending">取消</el-button></div>
    </el-alert>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tasks" stripe border empty-text="暂无整改任务">
        <el-table-column prop="title" label="整改任务" min-width="170" show-overflow-tooltip />
        <el-table-column prop="owner" label="负责人" width="120" />
        <el-table-column label="关联违规" min-width="170"><template #default="{ row }"><div>{{ violationLabel(row.violation_type) }}</div><small>{{ row.camera_id }}</small></template></el-table-column>
        <el-table-column label="截止时间" width="175"><template #default="{ row }"><span :class="{ overdue: isOverdue(row) }">{{ formatTime(row.due_at_utc) }}</span></template></el-table-column>
        <el-table-column label="状态" width="120"><template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="265" fixed="right"><template #default="{ row }"><el-button size="small" link type="primary" @click="openDetail(row.task_id)">详情</el-button><el-button v-if="canEdit(row)" size="small" link @click="openEdit(row)">编辑</el-button><el-button v-if="canEdit(row)" size="small" link type="success" @click="openStatus(row, 'COMPLETED')">完成</el-button><el-button v-if="canEdit(row)" size="small" link type="danger" @click="openStatus(row, 'CANCELLED')">取消</el-button></template></el-table-column>
      </el-table>
      <div class="pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>

    <el-dialog v-model="createVisible" title="新建整改任务" width="620px" destroy-on-close>
      <el-form label-position="top"><el-form-item label="关联活动违规" required><el-select v-model="createForm.eventUuid" filterable style="width:100%" placeholder="选择违规"><el-option v-for="event in activeViolations" :key="event.event_uuid" :label="`${violationLabel(event.violation_type)} · ${event.camera_id} · ${formatTime(event.occurred_at_utc)}`" :value="event.event_uuid" /></el-select></el-form-item><el-form-item label="整改要求" required><el-input v-model="createForm.title" /></el-form-item><el-form-item label="负责人" required><el-input v-model="createForm.owner" /></el-form-item><el-form-item label="截止时间" required><el-date-picker v-model="createForm.dueAt" type="datetime" style="width:100%" /></el-form-item><el-form-item label="补充说明"><el-input v-model="createForm.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="proposing" @click="proposeCreate">生成待确认操作</el-button></template>
    </el-dialog>

    <el-dialog v-model="editVisible" :title="editForm.status === 'COMPLETED' ? '完成整改任务' : editForm.status === 'CANCELLED' ? '取消整改任务' : '编辑整改任务'" width="560px" destroy-on-close>
      <el-form label-position="top"><el-form-item label="负责人"><el-input v-model="editForm.owner" /></el-form-item><el-form-item label="截止时间"><el-date-picker v-model="editForm.dueAt" type="datetime" style="width:100%" /></el-form-item><el-form-item label="任务状态"><el-select v-model="editForm.status" style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item label="处理备注"><el-input v-model="editForm.note" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="editVisible = false">取消</el-button><el-button type="primary" :loading="proposing" @click="proposeEdit">生成待确认操作</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="整改任务详情" size="620px"><template v-if="detail"><el-descriptions :column="1" border><el-descriptions-item label="任务">{{ detail.task.title }}</el-descriptions-item><el-descriptions-item label="负责人">{{ detail.task.owner }}</el-descriptions-item><el-descriptions-item label="截止时间">{{ formatTime(detail.task.due_at_utc) }}</el-descriptions-item><el-descriptions-item label="说明">{{ detail.task.description || '-' }}</el-descriptions-item><el-descriptions-item label="关联违规">{{ violationLabel(detail.violation.violation_type) }} · {{ detail.violation.camera_id }}</el-descriptions-item></el-descriptions><div class="drawer-section"><h4>违规证据</h4><el-image v-if="detail.violation.snapshot_uri" :src="resolveMediaUrl(detail.violation.snapshot_uri)" :preview-src-list="[resolveMediaUrl(detail.violation.snapshot_uri)]" preview-teleported fit="cover" class="evidence-image" /><el-empty v-else description="该违规没有快照" /></div><div class="drawer-section"><h4>操作审计</h4><el-timeline><el-timeline-item v-for="audit in detail.audits" :key="audit.audit_id" :timestamp="formatTime(audit.created_at_utc)"><strong>{{ audit.action }}</strong> · {{ audit.actor }}<div v-if="Object.keys(audit.detail_safe_json).length" class="audit-detail">{{ JSON.stringify(audit.detail_safe_json) }}</div></el-timeline-item></el-timeline></div></template></el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { cancelPendingAction, confirmPendingAction } from '@/api/chat'
import { fetchRectificationTask, fetchRectificationTasks, proposeRectificationTaskCreate, proposeRectificationTaskUpdate } from '@/api/rectificationTasks'
import { fetchViolations } from '@/api/violations'
import { resolveMediaUrl } from '@/api/client'
import type { PendingAction, RectificationTaskDetail, RectificationTaskRecord, RectificationTaskStatus, ViolationRecord, ViolationType } from '@/types/contract'

const tasks = ref<RectificationTaskRecord[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20); const loading = ref(false); const proposing = ref(false); const confirming = ref(false)
const activeViolations = ref<ViolationRecord[]>([]); const pendingAction = ref<PendingAction | null>(null); const createVisible = ref(false); const editVisible = ref(false); const detailVisible = ref(false); const detail = ref<RectificationTaskDetail | null>(null); const editingTaskId = ref('')
const filters = reactive<{ status?: RectificationTaskStatus; owner: string; overdue: boolean }>({ status: undefined, owner: '', overdue: false })
const createForm = reactive({ eventUuid: '', title: '', description: '', owner: '', dueAt: null as Date | null })
const editForm = reactive({ owner: '', dueAt: null as Date | null, status: 'PENDING' as RectificationTaskStatus, note: '' })
const statusOptions: Array<{ value: RectificationTaskStatus; label: string }> = [{ value: 'PENDING', label: '待处理' }, { value: 'IN_PROGRESS', label: '处理中' }, { value: 'COMPLETED', label: '已完成' }, { value: 'CANCELLED', label: '已取消' }]

function conversationId() { const key = 'agent_conversation_id'; const value = sessionStorage.getItem(key); if (value) return value; const created = crypto.randomUUID(); sessionStorage.setItem(key, created); return created }
async function load() { loading.value = true; try { const data = await fetchRectificationTasks({ status: filters.status, owner: filters.owner || undefined, overdue: filters.overdue || undefined, limit: pageSize.value, offset: (page.value - 1) * pageSize.value }); tasks.value = data.items; total.value = data.total } finally { loading.value = false } }
function search() { page.value = 1; load() }
function reset() { filters.status = undefined; filters.owner = ''; filters.overdue = false; page.value = 1; load() }
async function openCreate() { const data = await fetchViolations({ status: 'ACTIVE', limit: 100 }); activeViolations.value = data.items; createForm.eventUuid = ''; createForm.title = ''; createForm.description = ''; createForm.owner = ''; createForm.dueAt = null; createVisible.value = true }
async function proposeCreate() { if (!createForm.eventUuid || !createForm.title.trim() || !createForm.owner.trim() || !createForm.dueAt) return ElMessage.warning('请填写关联违规、整改要求、负责人和截止时间'); proposing.value = true; try { pendingAction.value = await proposeRectificationTaskCreate({ conversation_id: conversationId(), event_uuid: createForm.eventUuid, title: createForm.title.trim(), description: createForm.description.trim() || undefined, owner: createForm.owner.trim(), due_at_utc: createForm.dueAt.toISOString() }); createVisible.value = false } finally { proposing.value = false } }
function openEdit(task: RectificationTaskRecord) { editingTaskId.value = task.task_id; editForm.owner = task.owner; editForm.dueAt = new Date(task.due_at_utc); editForm.status = task.status; editForm.note = ''; editVisible.value = true }
function openStatus(task: RectificationTaskRecord, status: RectificationTaskStatus) { openEdit(task); editForm.status = status }
async function proposeEdit() { if (!editingTaskId.value || !editForm.owner.trim() || !editForm.dueAt) return ElMessage.warning('请填写负责人和截止时间'); proposing.value = true; try { pendingAction.value = await proposeRectificationTaskUpdate(editingTaskId.value, { conversation_id: conversationId(), owner: editForm.owner.trim(), due_at_utc: editForm.dueAt.toISOString(), status: editForm.status, note: editForm.note.trim() || undefined }); editVisible.value = false } finally { proposing.value = false } }
async function confirmPending() { if (!pendingAction.value) return; confirming.value = true; try { await confirmPendingAction(pendingAction.value.confirmation_id, conversationId()); pendingAction.value = null; ElMessage.success('操作已执行'); await load() } finally { confirming.value = false } }
async function cancelPending() { if (!pendingAction.value) return; await cancelPendingAction(pendingAction.value.confirmation_id, conversationId()); pendingAction.value = null; ElMessage.info('已取消待确认操作') }
async function openDetail(taskId: string) { detail.value = await fetchRectificationTask(taskId); detailVisible.value = true }
function formatTime(value: string) { return value ? new Date(value).toLocaleString() : '-' }
function canEdit(task: RectificationTaskRecord) { return !['COMPLETED', 'CANCELLED'].includes(task.status) }
function isOverdue(task: RectificationTaskRecord) { return ['PENDING', 'IN_PROGRESS'].includes(task.status) && new Date(task.due_at_utc).getTime() < Date.now() }
function statusLabel(status: RectificationTaskStatus) { return ({ PENDING: '待处理', IN_PROGRESS: '处理中', COMPLETED: '已完成', CANCELLED: '已取消' })[status] }
function statusTag(status: RectificationTaskStatus): 'warning' | 'primary' | 'success' | 'info' { return ({ PENDING: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' } as const)[status] }
function violationLabel(type: ViolationType) { return ({ NO_HELMET: '未佩戴安全帽', DANGER_ZONE_INTRUSION: '危险区域入侵', DWELL_TIMEOUT: '危险区停留超时' })[type] || type }
onMounted(load)
</script>

<style scoped>
.tasks-page { padding: 24px; height: 100%; overflow-y: auto; box-sizing: border-box; }
.header-section, .header-actions, .pending-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.header-section { margin-bottom: 16px; }.header-section h2 { margin: 0; font-size: 22px; color: #0f172a; }.header-section p { margin: 4px 0 0; color: #64748b; font-size: 13px; }
.filter-card, .table-card, .pending-card { margin-bottom: 16px; }.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }.overdue { color: #dc2626; font-weight: 600; }.drawer-section { margin-top: 24px; }.evidence-image { width: 100%; max-height: 300px; background: #0f172a; }.audit-detail { color: #64748b; font-size: 12px; margin-top: 4px; word-break: break-all; }
</style>
