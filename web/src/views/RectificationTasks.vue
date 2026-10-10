<template>
  <div class="tasks-page operations-workbench">
    <WorkspaceIntro eyebrow="RECTIFICATION TASKS" title="整改任务" description="明确整改要求与负责人，跟踪处理进度和截止时间。">
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新任务</el-button><el-button type="primary" :icon="Plus" @click="openCreate">新建整改任务</el-button>
    </WorkspaceIntro>
    <WorkspaceSummary label="当前整改任务查询概览" :items="summaryItems" />
    <el-alert v-if="loadError" class="workbench-error" title="任务查询未完成，请检查连接后重试；已有数据保留显示。" type="warning" :closable="false" show-icon />

    <el-card shadow="never" class="filter-card">
      <div class="filter-heading"><strong>查找整改任务</strong><span>按处理状态、负责人或逾期情况筛选</span></div>
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
      <template #header><div class="section-card-heading"><strong>任务清单</strong><span>当前条件匹配 {{ dataLoaded ? total : '—' }} 项 · 编辑和完成操作需确认</span></div></template>
      <el-table v-loading="loading" :data="tasks" empty-text="当前条件下暂无整改任务">
        <el-table-column prop="title" label="整改任务" min-width="170" show-overflow-tooltip />
        <el-table-column prop="owner" label="负责人" width="120" />
        <el-table-column label="关联违规" min-width="170"><template #default="{ row }"><div>{{ violationLabel(row.violation_type) }}</div><small>{{ row.camera_id }}</small></template></el-table-column>
        <el-table-column label="截止时间" width="175"><template #default="{ row }"><span :class="{ overdue: isOverdue(row) }">{{ formatTime(row.due_at_utc) }}</span></template></el-table-column>
        <el-table-column label="状态" width="120"><template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="265"><template #default="{ row }"><el-button size="small" link type="primary" @click="openDetail(row.task_id)">详情</el-button><el-button v-if="canEdit(row)" size="small" link @click="openEdit(row)">编辑</el-button><el-button v-if="canEdit(row)" size="small" link type="success" @click="openStatus(row, 'COMPLETED')">完成</el-button><el-button v-if="canEdit(row)" size="small" link type="danger" @click="openStatus(row, 'CANCELLED')">取消</el-button></template></el-table-column>
      </el-table>
      <p class="table-scroll-hint">左右滑动表格，查看任务详情与处理操作。</p>
      <div class="pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>

    <el-dialog v-model="createVisible" title="新建整改任务" width="620px" destroy-on-close>
      <el-form label-position="top"><el-form-item label="关联违规事件" required><el-select v-model="createForm.eventUuid" filterable style="width:100%" placeholder="选择违规"><el-option v-for="event in activeViolations" :key="event.event_uuid" :label="`${violationLabel(event.violation_type)} · ${event.camera_id} · ${formatTime(event.occurred_at_utc)}`" :value="event.event_uuid" /></el-select></el-form-item><el-form-item label="整改要求" required><el-input v-model="createForm.title" /></el-form-item><el-form-item label="负责人" required><el-input v-model="createForm.owner" /></el-form-item><el-form-item label="截止时间" required><el-date-picker v-model="createForm.dueAt" type="datetime" style="width:100%" /></el-form-item><el-form-item label="补充说明"><el-input v-model="createForm.description" type="textarea" :rows="3" /></el-form-item></el-form>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { cancelPendingAction, confirmPendingAction } from '@/api/chat'
import { fetchRectificationTask, fetchRectificationTasks, proposeRectificationTaskCreate, proposeRectificationTaskUpdate } from '@/api/rectificationTasks'
import { fetchViolations } from '@/api/violations'
import { resolveMediaUrl } from '@/api/client'
import WorkspaceIntro from '@/components/WorkspaceIntro.vue'
import WorkspaceSummary from '@/components/WorkspaceSummary.vue'
import type { PendingAction, RectificationTaskDetail, RectificationTaskRecord, RectificationTaskStatus, ViolationRecord, ViolationType } from '@/types/contract'

const tasks = ref<RectificationTaskRecord[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20); const loading = ref(false); const proposing = ref(false); const confirming = ref(false)
const route = useRoute()
const activeViolations = ref<ViolationRecord[]>([]); const pendingAction = ref<PendingAction | null>(null); const createVisible = ref(false); const editVisible = ref(false); const detailVisible = ref(false); const detail = ref<RectificationTaskDetail | null>(null); const editingTaskId = ref('')
const filters = reactive<{ status?: RectificationTaskStatus; owner: string; overdue: boolean }>({ status: undefined, owner: '', overdue: false })
const dataLoaded = ref(false), loadError = ref(false)
const summaryItems = computed(() => [
  { label: '匹配任务', value: dataLoaded.value ? total.value : '—', hint: '当前筛选条件 · 全部页' },
  { label: '本页进行中', value: dataLoaded.value ? tasks.value.filter(item => ['PENDING', 'IN_PROGRESS'].includes(item.status)).length : '—', hint: '待处理与处理中任务' },
  { label: '本页已逾期', value: dataLoaded.value ? tasks.value.filter(isOverdue).length : '—', hint: '截止时间已过且尚未完成', tone: 'warning' as const },
])
const createForm = reactive({ eventUuid: '', title: '', description: '', owner: '', dueAt: null as Date | null })
const editForm = reactive({ owner: '', dueAt: null as Date | null, status: 'PENDING' as RectificationTaskStatus, note: '' })
const statusOptions: Array<{ value: RectificationTaskStatus; label: string }> = [{ value: 'PENDING', label: '待处理' }, { value: 'IN_PROGRESS', label: '处理中' }, { value: 'COMPLETED', label: '已完成' }, { value: 'CANCELLED', label: '已取消' }]

function conversationId() { const key = 'agent_conversation_id'; const value = sessionStorage.getItem(key); if (value) return value; const created = crypto.randomUUID(); sessionStorage.setItem(key, created); return created }
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
  } catch { ElMessage.error('违规事件暂时无法加载，请稍后重试') }
}
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
.pending-card{margin-bottom:22px;border-radius:14px;border:1px solid #efdfc0;padding:18px 22px}.pending-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:10px}.pending-actions>span{font-size:12px;color:#a48b67;margin-right:auto}.overdue{color:#bc7365;font-weight:600}.drawer-section{margin-top:24px}.evidence-image{width:100%;max-height:300px;background:#151b21;border-radius:12px}.audit-detail{color:#8791a3;font-size:12px;margin-top:4px;word-break:break-all}
</style>
