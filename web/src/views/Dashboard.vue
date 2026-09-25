<template>
  <div class="dashboard-page">
    <div class="header-section">
      <div class="title-area">
        <h2>安全监控看板 (Dashboard)</h2>
        <p class="subtitle">全域施工态势感知、摄像头运行矩阵与实时违规统计</p>
      </div>
      <div class="actions">
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="refreshAll">
          刷新数据
        </el-button>
      </div>
    </div>

    <!-- KPI 概览卡片 -->
    <div class="kpi-grid">
      <el-card shadow="hover" class="kpi-card">
        <div class="kpi-title">今日违规总数</div>
        <div class="kpi-value text-blue">{{ stats?.total_violations ?? 0 }}</div>
        <div class="kpi-footer">覆盖全站所有在监控相机</div>
      </el-card>

      <el-card shadow="hover" class="kpi-card">
        <div class="kpi-title">严重告警 (CRITICAL)</div>
        <div class="kpi-value text-red">{{ stats?.by_severity?.CRITICAL ?? 0 }}</div>
        <div class="kpi-footer">需现场安全员紧急介入处置</div>
      </el-card>

      <el-card shadow="hover" class="kpi-card">
        <div class="kpi-title">平均停留/违规时长</div>
        <div class="kpi-value text-amber">
          {{ (stats?.average_duration_seconds ?? 0).toFixed(1) }} <span class="unit">秒</span>
        </div>
        <div class="kpi-footer">基于脚底进入判定至离场闭环</div>
      </el-card>

      <el-card shadow="hover" class="kpi-card">
        <div class="kpi-title">在线摄像头矩阵</div>
        <div class="kpi-value text-emerald">
          {{ onlineCamerasCount }} <span class="unit">/ {{ cameras.length }}</span>
        </div>
        <div class="kpi-footer">30s 内有心跳视为在线</div>
      </el-card>
    </div>

    <!-- ECharts 图表区 -->
    <div class="charts-grid">
      <el-card shadow="hover" class="chart-card">
        <template #header>
          <div class="card-header">
            <span>违规类型分布 (By Violation Type)</span>
          </div>
        </template>
        <div class="chart-wrapper">
          <v-chart :option="typePieOption" autoresize />
        </div>
      </el-card>

      <el-card shadow="hover" class="chart-card">
        <template #header>
          <div class="card-header">
            <span>违规严重度分级 (By Severity)</span>
          </div>
        </template>
        <div class="chart-wrapper">
          <v-chart :option="severityBarOption" autoresize />
        </div>
      </el-card>
    </div>

    <!-- 摄像头运行矩阵 -->
    <div class="camera-matrix-section">
      <div class="section-title">
        <h3>摄像头推流与推理矩阵</h3>
        <el-tag size="small" type="info">共 {{ cameras.length }} 路通道</el-tag>
      </div>

      <div class="camera-grid">
        <el-card
          v-for="cam in cameras"
          :key="cam.camera_id"
          shadow="hover"
          class="camera-card"
        >
          <div class="cam-header">
            <span class="cam-id">{{ cam.camera_id }}</span>
            <el-tag :type="cam.is_online ? 'success' : 'danger'" size="small" effect="dark">
              {{ cam.is_online ? '在线 推流中' : '离线' }}
            </el-tag>
          </div>

          <div class="cam-body">
            <div class="cam-stat">
              <span class="label">实时 FPS：</span>
              <span class="val font-mono">{{ cam.fps.toFixed(1) }}</span>
            </div>
            <div class="cam-stat">
              <span class="label">已处理帧：</span>
              <span class="val font-mono">{{ cam.processed_frame_id }}</span>
            </div>
            <div class="cam-stat">
              <span class="label">活跃 Worker：</span>
              <span class="val">{{ cam.active_workers_count }}</span>
            </div>
            <div class="cam-stat">
              <span class="label">部署模型：</span>
              <span class="val truncate">{{ cam.model_name || '默认' }}</span>
            </div>
            <div class="cam-stat">
              <span class="label">心跳时间：</span>
              <span class="val text-muted">{{ formatTime(cam.reported_at_utc) }}</span>
            </div>
          </div>

          <div class="cam-footer">
            <el-button
              size="small"
              text
              type="primary"
              @click="$router.push({ path: '/zones', query: { camera_id: cam.camera_id } })"
            >
              标定围栏
            </el-button>
            <el-button
              size="small"
              text
              type="primary"
              @click="$router.push({ path: '/violations', query: { camera_id: cam.camera_id } })"
            >
              查看违规
            </el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { fetchCameras } from '@/api/cameras'
import { fetchViolationStatistics } from '@/api/violations'
import type { CameraStatusResponse, ViolationStatistics } from '@/types/contract'

const loading = ref(false)
const cameras = ref<CameraStatusResponse[]>([])
const stats = ref<ViolationStatistics | null>(null)

const onlineCamerasCount = computed(() => cameras.value.filter((c) => c.is_online).length)

const typePieOption = computed(() => {
  const data = []
  if (stats.value?.by_type) {
    const map: Record<string, string> = {
      NO_HELMET: '未佩戴安全帽',
      DANGER_ZONE_INTRUSION: '危险区入侵',
      DWELL_TIMEOUT: '超时停留',
    }
    for (const [k, v] of Object.entries(stats.value.by_type)) {
      data.push({ name: map[k] || k, value: v })
    }
  }
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: '0' },
    color: ['#f59e0b', '#ef4444', '#8b5cf6', '#3b82f6'],
    series: [
      {
        name: '违规类型',
        type: 'pie',
        radius: ['45%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
        },
        data: data.length > 0 ? data : [{ name: '暂无数据', value: 0 }],
      },
    ],
  }
})

const severityBarOption = computed(() => {
  const categories = ['INFO (普通)', 'WARNING (告警)', 'CRITICAL (严重)']
  const bySev = stats.value?.by_severity || {}
  const data = [bySev.INFO || 0, bySev.WARNING || 0, bySev.CRITICAL || 0]

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: categories },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '事件数量',
        type: 'bar',
        barWidth: '35%',
        data: [
          { value: data[0], itemStyle: { color: '#3b82f6' } },
          { value: data[1], itemStyle: { color: '#f59e0b' } },
          { value: data[2], itemStyle: { color: '#ef4444' } },
        ],
      },
    ],
  }
})

async function refreshAll() {
  loading.value = true
  try {
    const [cRes, sRes] = await Promise.all([fetchCameras(), fetchViolationStatistics()])
    cameras.value = cRes
    stats.value = sRes
  } finally {
    loading.value = false
  }
}

function formatTime(utcStr: string): string {
  if (!utcStr) return '-'
  return new Date(utcStr).toLocaleTimeString()
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.dashboard-page {
  padding: 24px;
  overflow-y: auto;
  height: 100%;
}
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
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
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.kpi-card {
  border-radius: 8px;
}
.kpi-title {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}
.kpi-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
  margin-bottom: 8px;
}
.kpi-value .unit {
  font-size: 14px;
  font-weight: 400;
  color: #64748b;
}
.kpi-footer {
  font-size: 12px;
  color: #94a3b8;
}
.text-blue { color: #2563eb; }
.text-red { color: #ef4444; }
.text-amber { color: #d97706; }
.text-emerald { color: #059669; }

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.chart-card {
  border-radius: 8px;
}
.chart-wrapper {
  height: 260px;
  width: 100%;
}
.camera-matrix-section {
  margin-top: 16px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.section-title h3 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}
.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.camera-card {
  border-radius: 8px;
}
.cam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}
.cam-id {
  font-weight: 600;
  font-size: 15px;
  color: #1e293b;
}
.cam-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  margin-bottom: 12px;
}
.cam-stat {
  display: flex;
  justify-content: space-between;
}
.cam-stat .label {
  color: #64748b;
}
.cam-stat .val {
  color: #1e293b;
  font-weight: 500;
}
.font-mono {
  font-family: ui-monospace, monospace;
}
.truncate {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cam-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f8fafc;
  padding-top: 6px;
}
</style>
