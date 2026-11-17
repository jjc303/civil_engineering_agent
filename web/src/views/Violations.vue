<template>
  <div class="violations-page operations-workbench">
    <WorkspaceIntro eyebrow="SAFETY EVENTS" :title="t('violations.title')" :description="t('violations.description')">
      <router-link to="/rectification-tasks" class="related-workspace">{{ t('violations.goTasks') }}</router-link>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">{{ t('violations.refreshEvents') }}</el-button>
    </WorkspaceIntro>
    <WorkspaceSummary :label="t('violations.summaryLabel')" :items="summaryItems" />
    <el-alert v-if="loadError" class="workbench-error" :title="t('violations.loadError')" type="warning" :closable="false" show-icon />

    <!-- 筛选面板 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-heading"><strong>{{ t('violations.filterTitle') }}</strong><span>{{ t('violations.filterDesc') }}</span></div>
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item :label="t('violations.cameraLabel')">
          <el-select v-model="filters.camera_id" :placeholder="t('violations.allCameras')" clearable style="width: 160px">
            <el-option
              v-for="cam in cameraList"
              :key="cam.camera_id"
              :label="cam.camera_id"
              :value="cam.camera_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('violations.typeLabel')">
          <el-select v-model="filters.violation_type" :placeholder="t('violations.allTypes')" clearable style="width: 170px">
            <el-option
              v-for="opt in dictionaries.violationOptions"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('violations.severityLabel')">
          <el-select v-model="filters.severity" :placeholder="t('violations.allSeverities')" clearable style="width: 140px">
            <el-option
              v-for="opt in dictionaries.severityOptions"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('violations.statusLabel')">
          <el-select v-model="filters.status" :placeholder="t('violations.allStatuses')" clearable style="width: 140px">
            <el-option
              v-for="opt in dictionaries.statusOptions"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">{{ t('common.search') }}</el-button>
          <el-button @click="handleReset">{{ t('common.reset') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 事件数据表格 -->
    <el-card shadow="never" class="table-card">
      <template #header><div class="section-card-heading"><strong>{{ t('violations.tableTitle') }}</strong><span>{{ t('violations.tableSubtitle', { total: dataLoaded ? total : '—' }) }}</span></div></template>
      <el-table :data="tableData" v-loading="loading" style="width: 100%" :empty-text="t('violations.emptyText')">
        <el-table-column :label="t('violations.colEvidence')" width="106"><template #default="{ row }"><button class="evidence-thumbnail" :aria-label="t('violations.viewEvidenceAria', { camera: row.camera_id })" @click="openEvidence(row)"><el-image v-if="row.snapshot_uri" :src="resolveMediaUrl(row.snapshot_uri)" fit="cover" loading="lazy" :alt="t('violations.snapshotAlt')"><template #error><span>{{ t('violations.noSnapshot') }}</span></template></el-image><span v-else>{{ t('violations.noSnapshot') }}</span></button></template></el-table-column>
        <el-table-column prop="camera_id" :label="t('violations.colCamera')" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ row.camera_id }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="violation_type" :label="t('violations.colType')" width="160">
          <template #default="{ row }">
            {{ formatType(row.violation_type) }}
            <small class="event-number">{{ row.event_uuid.substring(0, 8) }}…</small>
          </template>
        </el-table-column>

        <el-table-column prop="severity" :label="t('violations.colSeverity')" width="110">
          <template #default="{ row }">
            <el-tag :type="severityTag(row.severity)" size="small" effect="light">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" :label="t('violations.colStatus')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'danger' : 'info'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="duration_seconds" :label="t('violations.colDuration')" width="110">
          <template #default="{ row }">
            {{ row.duration_seconds.toFixed(1) }} s
          </template>
        </el-table-column>

        <el-table-column prop="occurred_at_utc" :label="t('violations.colTime')" min-width="170">
          <template #default="{ row }">
            {{ formatTime(row.occurred_at_utc) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('violations.colAction')" width="120" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              link
              :icon="View"
              @click="openEvidence(row)"
            >
              {{ t('violations.inspectEvidence') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="table-scroll-hint">{{ t('violations.scrollHint') }}</p>

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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh, View } from '@element-plus/icons-vue'
import { fetchViolations } from '@/api/violations'
import { fetchCameras } from '@/api/cameras'
import { createSafetyEventStream, type SafetyEventStreamHandle } from '@/api/realtime'
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
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import { useDictionariesStore } from '@/stores/dictionaries'

const route = useRoute()
const { t, formatDateTime } = useAppI18n()
const dictionaries = useDictionariesStore()
dictionaries.ensureLoaded()

const loading = ref(false)
const dataLoaded = ref(false), loadError = ref(false)
const tableData = ref<ViolationRecord[]>([])
const cameraList = ref<CameraStatusResponse[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const summaryItems = computed(() => [
  { label: t('violations.summaryTotal'), value: dataLoaded.value ? total.value : '—', hint: t('violations.summaryTotalHint') },
  { label: t('violations.summaryActive'), value: dataLoaded.value ? tableData.value.filter(item => item.status === 'ACTIVE').length : '—', hint: t('violations.summaryActiveHint'), tone: 'warning' as const },
  { label: t('violations.summaryCritical'), value: dataLoaded.value ? tableData.value.filter(item => item.severity === 'CRITICAL').length : '—', hint: t('violations.summaryCriticalHint'), tone: 'warning' as const },
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

function severityLabel(value: ViolationSeverity) { return dictionaries.severityLabel(value) }
function statusLabel(value: EventStatus) { return dictionaries.statusLabel(value) }

function formatType(t: ViolationType): string {
  return dictionaries.violationLabel(t)
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return formatDateTime(utcStr)
}

useLocaleRefresh(() => {
  void loadData()
})

let streamHandle: SafetyEventStreamHandle | undefined
let refreshDebounceTimer: ReturnType<typeof setTimeout> | undefined

onMounted(() => {
  loadCameras()
  loadData()
  streamHandle = createSafetyEventStream({
    onViolationEvent() {
      if (currentPage.value !== 1) return
      if (refreshDebounceTimer) clearTimeout(refreshDebounceTimer)
      refreshDebounceTimer = setTimeout(() => {
        void loadData()
      }, 500)
    },
  })
})

onUnmounted(() => {
  streamHandle?.close()
  if (refreshDebounceTimer) clearTimeout(refreshDebounceTimer)
})
</script>

<style scoped>
.uuid-text{color:#9193a6;background:#f5f2fa;padding:4px 6px;border-radius:5px;font-size:10px}.evidence-thumbnail{display:block;width:72px;height:48px;padding:0;border:1px solid #ece8f4;background:#f6f3fb;color:#a198ae;border-radius:8px;overflow:hidden;font-size:10px}.evidence-thumbnail .el-image{width:100%;height:100%}.evidence-thumbnail:hover{border-color:#a998d0}.evidence-thumbnail:focus-visible{outline:2px solid #9583e7;outline-offset:3px}
.event-number{display:block;margin-top:5px;font-family:ui-monospace,monospace;letter-spacing:.4px}
</style>
