<template>
  <div class="violations-page">
    <div class="header-section">
      <div class="title-area">
        <h2>违规事件中心 (Violations Center)</h2>
        <p class="subtitle">施工安全违规事件结构化归档、筛选审计与证据排查</p>
      </div>
      <el-button type="primary" :icon="Refresh" @click="loadData">刷新</el-button>
    </div>

    <!-- 筛选面板 -->
    <el-card shadow="never" class="filter-card">
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
            <el-option label="CRITICAL (严重)" value="CRITICAL" />
            <el-option label="WARNING (告警)" value="WARNING" />
            <el-option label="INFO (提示)" value="INFO" />
          </el-select>
        </el-form-item>

        <el-form-item label="事件状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px">
            <el-option label="ACTIVE (活跃)" value="ACTIVE" />
            <el-option label="RESOLVED (已解除)" value="RESOLVED" />
            <el-option label="FALSE_ALARM (误报)" value="FALSE_ALARM" />
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
      <el-table :data="tableData" v-loading="loading" style="width: 100%" stripe border>
        <el-table-column prop="event_uuid" label="事件 UUID" width="180">
          <template #default="{ row }">
            <code class="uuid-text">{{ row.event_uuid.substring(0, 13) }}...</code>
          </template>
        </el-table-column>

        <el-table-column prop="camera_id" label="摄像头" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ row.camera_id }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="violation_type" label="违规类型" width="160">
          <template #default="{ row }">
            {{ formatType(row.violation_type) }}
          </template>
        </el-table-column>

        <el-table-column prop="severity" label="严重级别" width="110">
          <template #default="{ row }">
            <el-tag :type="severityTag(row.severity)" size="small" effect="dark">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'danger' : 'info'" size="small">
              {{ row.status }}
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
import { ref, reactive, onMounted } from 'vue'
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

const route = useRoute()

const loading = ref(false)
const tableData = ref<ViolationRecord[]>([])
const cameraList = ref<CameraStatusResponse[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

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
.violations-page {
  padding: 24px;
  overflow-y: auto;
  height: 100%;
}
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.title-area h2 {
  margin: 0;
  font-size: 22px;
  color: #0f172a;
}
.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}
.filter-card {
  margin-bottom: 16px;
  border-radius: 8px;
}
.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.table-card {
  border-radius: 8px;
}
.uuid-text {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
