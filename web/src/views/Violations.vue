<template>
  <div class="violations-page operations-workbench">
    <WorkspaceIntro eyebrow="SAFETY EVENTS" title="违规事件" description="找到需要关注的事件，查看现场证据，跟进后续整改。">
      <router-link to="/rectification-tasks" class="related-workspace">前往整改任务 ↗</router-link>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新事件</el-button>
    </WorkspaceIntro>
    <WorkspaceSummary label="当前事件查询概览" :items="summaryItems" />
    <el-alert v-if="loadError" class="workbench-error" title="事件查询未完成，请检查连接后重试；已有数据保留显示。" type="warning" :closable="false" show-icon />

    <!-- 筛选面板 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-heading"><strong>筛选事件</strong><span>按摄像头、类型与处理状态查找</span></div>
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="摄像头">
          <el-select v-model="filters.camera_id" placeholder="全部相机" clearable style="width: 160px">
            <el-option
              v-for="cam in cameraList"
              :key="cam.camera_id"
              :label="cam.camera_id"
              :value="cam.camera_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="违规类型">
          <el-select v-model="filters.violation_type" placeholder="全部类型" clearable style="width: 170px">
            <el-option label="未佩戴安全帽" value="NO_HELMET" />
            <el-option label="危险区域入侵" value="DANGER_ZONE_INTRUSION" />
            <el-option label="超时停留" value="DWELL_TIMEOUT" />
          </el-select>
        </el-form-item>

        <el-form-item label="严重级别">
          <el-select v-model="filters.severity" placeholder="全部级别" clearable style="width: 140px">
            <el-option label="严重" value="CRITICAL" />
            <el-option label="告警" value="WARNING" />
            <el-option label="提示" value="INFO" />
          </el-select>
        </el-form-item>

        <el-form-item label="事件状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option label="待关注" value="ACTIVE" />
            <el-option label="已解除" value="RESOLVED" />
            <el-option label="误报" value="FALSE_ALARM" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">检索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 事件数据表格 -->
    <el-card shadow="never" class="table-card">
      <template #header><div class="section-card-heading"><strong>事件记录</strong><span>当前条件匹配 {{ dataLoaded ? total : '—' }} 条 · 按发生时间查看</span></div></template>
      <el-table :data="tableData" v-loading="loading" style="width: 100%" empty-text="当前条件下暂无违规事件">
        <el-table-column label="现场证据" width="106"><template #default="{ row }"><button class="evidence-thumbnail" :aria-label="`查看 ${row.camera_id} 的事件证据`" @click="openEvidence(row)"><el-image v-if="row.snapshot_uri" :src="resolveMediaUrl(row.snapshot_uri)" fit="cover" loading="lazy" alt="事件快照"><template #error><span>暂无快照</span></template></el-image><span v-else>暂无快照</span></button></template></el-table-column>
        <el-table-column prop="camera_id" label="摄像头" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ row.camera_id }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="violation_type" label="违规类型" width="160">
          <template #default="{ row }">
            {{ formatType(row.violation_type) }}
            <small class="event-number">{{ row.event_uuid.substring(0, 8) }}…</small>
          </template>
        </el-table-column>

        <el-table-column prop="severity" label="严重级别" width="110">
          <template #default="{ row }">
            <el-tag :type="severityTag(row.severity)" size="small" effect="light">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'danger' : 'info'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="duration_seconds" label="持续时长" width="110">
          <template #default="{ row }">
            {{ row.duration_seconds.toFixed(1) }} s
          </template>
        </el-table-column>

        <el-table-column prop="occurred_at_utc" label="发生时间" min-width="170">
          <template #default="{ row }">
            {{ formatTime(row.occurred_at_utc) }}
          </template>
        </el-table-column>

        <el-table-column label="抓拍证据" width="120" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              link
              :icon="View"
              @click="openEvidence(row)"
            >
              审查证据
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="table-scroll-hint">左右滑动表格，查看完整事件信息与证据操作。</p>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 证据审查弹窗 -->
    <EvidenceModal v-model="modalVisible" :record="selectedRecord" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh, View } from '@element-plus/icons-vue'
import { fetchViolations } from '@/api/violations'
import { fetchCameras } from '@/api/cameras'
import type {
  CameraStatusResponse,
  EventStatus,
  ViolationRecord,
  ViolationSeverity,
  ViolationType,
} from '@/types/contract'
import EvidenceModal from '@/components/EvidenceModal.vue'
import WorkspaceIntro from '@/components/WorkspaceIntro.vue'
import WorkspaceSummary from '@/components/WorkspaceSummary.vue'
import { resolveMediaUrl } from '@/api/client'

const route = useRoute()

const loading = ref(false)
const dataLoaded = ref(false), loadError = ref(false)
const tableData = ref<ViolationRecord[]>([])
const cameraList = ref<CameraStatusResponse[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const summaryItems = computed(() => [
  { label: '匹配事件', value: dataLoaded.value ? total.value : '—', hint: '当前筛选条件 · 全部页' },
  { label: '本页待关注', value: dataLoaded.value ? tableData.value.filter(item => item.status === 'ACTIVE').length : '—', hint: '本页活动事件', tone: 'warning' as const },
  { label: '本页严重告警', value: dataLoaded.value ? tableData.value.filter(item => item.severity === 'CRITICAL').length : '—', hint: '本页严重级别事件', tone: 'warning' as const },
])

const modalVisible = ref(false)
const selectedRecord = ref<ViolationRecord | null>(null)

const filters = reactive<{
  camera_id: string
  violation_type: ViolationType | undefined
  severity: ViolationSeverity | undefined
  status: EventStatus | undefined
}>({
  camera_id: (route.query.camera_id as string) || '',
  violation_type: undefined,
  severity: undefined,
  status: undefined,
})

async function loadData() {
  loading.value = true
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    const res = await fetchViolations({
      camera_id: filters.camera_id || undefined,
      violation_type: filters.violation_type || undefined,
      severity: filters.severity || undefined,
      status: filters.status || undefined,
      limit: pageSize.value,
      offset,
    })
    tableData.value = res.items
    total.value = res.total
    dataLoaded.value = true
    loadError.value = false
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function loadCameras() {
  cameraList.value = await fetchCameras()
}

function handleSearch() {
  currentPage.value = 1
  loadData()
}

function handleReset() {
  filters.camera_id = ''
  filters.violation_type = undefined
  filters.severity = undefined
  filters.status = undefined
  currentPage.value = 1
  loadData()
}

function openEvidence(record: ViolationRecord) {
  selectedRecord.value = record
  modalVisible.value = true
}

function severityTag(s: ViolationSeverity): 'danger' | 'warning' | 'info' {
  if (s === 'CRITICAL') return 'danger'
  if (s === 'WARNING') return 'warning'
  return 'info'
}

function severityLabel(value: ViolationSeverity) { return ({ CRITICAL: '严重', WARNING: '告警', INFO: '提示' })[value] || value }
function statusLabel(value: EventStatus) { return ({ ACTIVE: '待关注', RESOLVED: '已解除', FALSE_ALARM: '误报' })[value] || value }

function formatType(t: ViolationType): string {
  const map: Record<ViolationType, string> = {
    NO_HELMET: '未佩戴安全帽',
    DANGER_ZONE_INTRUSION: '危险区入侵',
    DWELL_TIMEOUT: '超时停留',
  }
  return map[t] || t
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return new Date(utcStr).toLocaleString()
}

onMounted(() => {
  loadCameras()
  loadData()
})
</script>

<style scoped>
.uuid-text{color:#9193a6;background:#f5f2fa;padding:4px 6px;border-radius:5px;font-size:10px}.evidence-thumbnail{display:block;width:72px;height:48px;padding:0;border:1px solid #ece8f4;background:#f6f3fb;color:#a198ae;border-radius:8px;overflow:hidden;font-size:10px}.evidence-thumbnail .el-image{width:100%;height:100%}.evidence-thumbnail:hover{border-color:#a998d0}.evidence-thumbnail:focus-visible{outline:2px solid #9583e7;outline-offset:3px}
.event-number{display:block;margin-top:5px;font-family:ui-monospace,monospace;letter-spacing:.4px}
</style>
