<template>
  <div class="zone-editor-page">
    <div class="header-section">
      <div class="title-area">
        <h2>危险区域标定 (Zone Editor)</h2>
        <p class="subtitle">基于视频原始像素 (1080P) 的电子围栏几何标定与防抖策略配置</p>
      </div>

      <div class="camera-picker">
        <span class="label">选择目标摄像头：</span>
        <el-select v-model="selectedCameraId" style="width: 200px" @change="loadCameraConfig">
          <el-option
            v-for="cam in cameras"
            :key="cam.camera_id"
            :label="cam.camera_id"
            :value="cam.camera_id"
          />
        </el-select>
        <el-tag :type="currentVersion > 0 ? 'success' : 'info'" effect="dark">
          {{ currentVersion > 0 ? `当前配置: v${currentVersion}` : '未标定 (首次创建)' }}
        </el-tag>
      </div>
    </div>

    <div class="workspace-grid">
      <!-- 画布标定操作区 -->
      <el-card shadow="never" class="canvas-card">
        <template #header>
          <div class="canvas-toolbar">
            <span class="font-bold">监控帧标定画布 (视口缩放反算: {{ scaleRatioText }})</span>
            <div class="tool-btns">
              <el-button size="small" type="primary" :icon="Plus" @click="addPoint">添加顶点</el-button>
              <el-button size="small" :icon="RefreshRight" @click="resetToDefaultZone">重置默认形状</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="clearPoints">清空顶点</el-button>
            </div>
          </div>
        </template>

        <div class="canvas-container" ref="containerRef">
          <canvas
            ref="canvasRef"
            class="interactive-canvas"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
          ></canvas>
        </div>

        <div class="canvas-hint">
          <span>💡 提示：在画布中按住<strong>黄色圆点</strong>拖拽可调整多边形边界；顶点均自动反算为 1920×1080 原始视频帧物理坐标。</span>
        </div>
      </el-card>

      <!-- 参数配置面板 -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <span class="font-bold">防抖与报警参数 (Run Config)</span>
        </template>

        <el-form label-position="top" :model="form" class="config-form">
          <el-form-item label="危险区域标识 (Zone ID)">
            <el-input v-model="zoneConfig.zone_id" placeholder="如 zone-crane-01" />
          </el-form-item>

          <el-form-item label="危险区域显示名 (Zone Name)">
            <el-input v-model="zoneConfig.zone_name" placeholder="如 塔吊回转作业区" />
          </el-form-item>

          <el-form-item label="滞留报警阈值 (秒)">
            <el-input-number
              v-model="zoneConfig.alarm_dwell_threshold_seconds"
              :min="0.5"
              :max="300"
              :step="0.5"
            />
          </el-form-item>

          <el-divider />

          <el-form-item label="进入防抖判定帧数 (enter_debounce_frames)">
            <el-slider v-model="form.enter_debounce_frames" :min="1" :max="30" show-input />
          </el-form-item>

          <el-form-item label="离开防抖判定帧数 (exit_debounce_frames)">
            <el-slider v-model="form.exit_debounce_frames" :min="1" :max="30" show-input />
          </el-form-item>

          <el-form-item label="安全帽状态平滑帧数 (helmet_debounce_frames)">
            <el-slider v-model="form.helmet_debounce_frames" :min="1" :max="30" show-input />
          </el-form-item>

          <el-form-item label="启用围栏布防">
            <el-switch v-model="zoneConfig.enabled" active-text="启用实时布控" />
          </el-form-item>

          <div class="polygon-points-preview">
            <div class="preview-title">当前顶点 (物理绝对坐标, 数量: {{ polygonPoints.length }}):</div>
            <div class="points-chips">
              <el-tag
                v-for="(p, idx) in polygonPoints"
                :key="idx"
                size="small"
                closable
                @close="removePoint(idx)"
              >
                P{{ idx + 1 }}: [{{ p[0] }}, {{ p[1] }}]
              </el-tag>
            </div>
          </div>

          <div class="submit-section">
            <el-button
              type="primary"
              size="large"
              :loading="saving"
              style="width: 100%"
              @click="saveConfiguration"
            >
              保存并下发新版本配置
            </el-button>
          </div>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, RefreshRight, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchCameras } from '@/api/cameras'
import { fetchCameraZones, updateCameraZones } from '@/api/zones'
import type { CameraStatusResponse, DangerZoneConfig } from '@/types/contract'

const route = useRoute()

const cameras = ref<CameraStatusResponse[]>([])
const selectedCameraId = ref<string>('')
const currentVersion = ref<number>(0)
const saving = ref(false)

const SOURCE_WIDTH = 1920
const SOURCE_HEIGHT = 1080

// 画布相关
const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const canvasWidth = ref(840)
const canvasHeight = ref(472.5) // 16:9

// 顶点数组 (以原始视频 1920x1080 像素坐标保存)
const polygonPoints = ref<[number, number][]>([
  [350, 200],
  [850, 180],
  [1000, 650],
  [600, 800],
  [280, 550],
])

const draggingIndex = ref<number | null>(null)

const zoneConfig = reactive<DangerZoneConfig>({
  zone_id: 'zone-crane-01',
  zone_name: '塔吊禁行危险区',
  polygon: [],
  enabled: true,
  alarm_dwell_threshold_seconds: 5.0,
})

const form = reactive({
  enter_debounce_frames: 3,
  exit_debounce_frames: 5,
  helmet_debounce_frames: 5,
})

const scaleRatioText = computed(() => {
  const sx = (canvasWidth.value / SOURCE_WIDTH).toFixed(2)
  return `${canvasWidth.value}x${canvasHeight.value} (比例: ${sx})`
})

async function init() {
  try {
    const cList = await fetchCameras()
    cameras.value = cList
    const queryCam = route.query.camera_id as string
    if (queryCam && cList.some((c) => c.camera_id === queryCam)) {
      selectedCameraId.value = queryCam
    } else if (cList.length > 0) {
      selectedCameraId.value = cList[0].camera_id
    }
    if (selectedCameraId.value) {
      await loadCameraConfig()
    } else {
      ElMessage.info('暂无可用摄像头，请先启动 CV 会话或选择 Mock 模式。')
    }
  } catch {
    cameras.value = []
    ElMessage.error('无法获取 Agent 摄像头列表；实时联调模式不会回退到 Mock 数据。')
  }
}

async function loadCameraConfig() {
  if (!selectedCameraId.value) return
  try {
    const res = await fetchCameraZones(selectedCameraId.value)
    if (res) {
      currentVersion.value = res.config_version
      form.enter_debounce_frames = res.enter_debounce_frames
      form.exit_debounce_frames = res.exit_debounce_frames
      form.helmet_debounce_frames = res.helmet_debounce_frames

      if (res.zones && res.zones.length > 0) {
        const z = res.zones[0]
        zoneConfig.zone_id = z.zone_id
        zoneConfig.zone_name = z.zone_name
        zoneConfig.enabled = z.enabled
        zoneConfig.alarm_dwell_threshold_seconds = z.alarm_dwell_threshold_seconds
        polygonPoints.value = JSON.parse(JSON.stringify(z.polygon))
      }
    } else {
      // 404 说明未配置，首次创建
      currentVersion.value = 0
      resetToDefaultZone()
    }
  } catch {
    ElMessage.error('无法读取围栏配置，请检查 Agent 服务连接后重试。')
    return
  }
  nextTick(() => {
    resizeCanvas()
    drawCanvas()
  })
}

function resetToDefaultZone() {
  polygonPoints.value = [
    [400, 250],
    [900, 200],
    [950, 700],
    [500, 750],
  ]
  drawCanvas()
}

function clearPoints() {
  polygonPoints.value = []
  drawCanvas()
}

function addPoint() {
  const pts = polygonPoints.value
  if (pts.length === 0) {
    polygonPoints.value = [[500, 500]]
  } else {
    const last = pts[pts.length - 1]
    polygonPoints.value.push([Math.min(last[0] + 80, 1800), Math.min(last[1] + 80, 1000)])
  }
  drawCanvas()
}

function removePoint(idx: number) {
  if (polygonPoints.value.length <= 3) {
    ElMessage.warning('多边形至少需要 3 个顶点')
    return
  }
  polygonPoints.value.splice(idx, 1)
  drawCanvas()
}

function resizeCanvas() {
  const container = containerRef.value
  if (!container) return
  const w = container.clientWidth || 840
  canvasWidth.value = w
  canvasHeight.value = (w * 9) / 16
  const canvas = canvasRef.value
  if (canvas) {
    canvas.width = canvasWidth.value
    canvas.height = canvasHeight.value
  }
}

function drawCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 1. 绘制工业网格背景与标尺
  ctx.fillStyle = '#0f172a'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  const step = 40
  for (let x = 0; x < canvas.width; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvas.height; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }

  // 2. 绘制多边形
  const pts = polygonPoints.value
  if (pts.length < 2) return

  const scaleX = canvasWidth.value / SOURCE_WIDTH
  const scaleY = canvasHeight.value / SOURCE_HEIGHT

  ctx.beginPath()
  ctx.moveTo(pts[0][0] * scaleX, pts[0][1] * scaleY)
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(pts[i][0] * scaleX, pts[i][1] * scaleY)
  }
  ctx.closePath()

  ctx.fillStyle = 'rgba(239, 68, 68, 0.25)'
  ctx.fill()

  ctx.strokeStyle = '#ef4444'
  ctx.lineWidth = 3
  ctx.stroke()

  // 3. 绘制锚点 Anchor
  for (let i = 0; i < pts.length; i++) {
    const cx = pts[i][0] * scaleX
    const cy = pts[i][1] * scaleY

    ctx.beginPath()
    ctx.arc(cx, cy, 7, 0, 2 * Math.PI)
    ctx.fillStyle = '#facc15'
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = '#000000'
    ctx.stroke()

    // 绘制标签 P1, P2...
    ctx.fillStyle = '#ffffff'
    ctx.font = '11px sans-serif'
    ctx.fillText(`P${i + 1}`, cx + 9, cy - 5)
  }
}

function onMouseDown(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  const scaleX = canvasWidth.value / SOURCE_WIDTH
  const scaleY = canvasHeight.value / SOURCE_HEIGHT

  // 检查是否点中了某个顶点锚点
  const pts = polygonPoints.value
  for (let i = 0; i < pts.length; i++) {
    const cx = pts[i][0] * scaleX
    const cy = pts[i][1] * scaleY
    const dist = Math.hypot(mouseX - cx, mouseY - cy)
    if (dist <= 12) {
      draggingIndex.value = i
      return
    }
  }
}

function onMouseMove(e: MouseEvent) {
  if (draggingIndex.value === null) return
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mouseX = Math.max(0, Math.min(e.clientX - rect.left, canvasWidth.value))
  const mouseY = Math.max(0, Math.min(e.clientY - rect.top, canvasHeight.value))

  const scaleX = canvasWidth.value / SOURCE_WIDTH
  const scaleY = canvasHeight.value / SOURCE_HEIGHT

  // 逆向反算物理像素
  const px = Math.round(mouseX / scaleX)
  const py = Math.round(mouseY / scaleY)

  polygonPoints.value[draggingIndex.value] = [px, py]
  drawCanvas()
}

function onMouseUp() {
  draggingIndex.value = null
}

async function saveConfiguration() {
  if (!selectedCameraId.value) {
    ElMessage.warning('请先选择一个真实摄像头。')
    return
  }
  if (polygonPoints.value.length < 3) {
    ElMessage.error('围栏多边形至少需要 3 个有效顶点')
    return
  }

  saving.value = true
  try {
    const res = await updateCameraZones(selectedCameraId.value, {
      expected_version: currentVersion.value > 0 ? currentVersion.value : null,
      source_resolution: { width: SOURCE_WIDTH, height: SOURCE_HEIGHT },
      enter_debounce_frames: form.enter_debounce_frames,
      exit_debounce_frames: form.exit_debounce_frames,
      helmet_debounce_frames: form.helmet_debounce_frames,
      alarm_dwell_threshold_seconds: zoneConfig.alarm_dwell_threshold_seconds,
      zones: [
        {
          zone_id: zoneConfig.zone_id,
          zone_name: zoneConfig.zone_name,
          polygon: polygonPoints.value,
          enabled: zoneConfig.enabled,
          alarm_dwell_threshold_seconds: zoneConfig.alarm_dwell_threshold_seconds,
        },
      ],
    })

    currentVersion.value = res.config_version
    ElMessage.success(`围栏配置成功保存并下发！当前配置版本升级至 v${res.config_version}`)
  } catch (err: any) {
    if (err.response?.status === 409) {
      ElMessageBox.confirm(
        '该摄像头配置已被其他客户端更新，当前版本已失效，是否立即重新拉取最新版本？',
        '乐观并发冲突提示 (409)',
        { confirmButtonText: '重新拉取', cancelButtonText: '取消', type: 'warning' }
      ).then(() => {
        loadCameraConfig()
      })
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  init()
  window.addEventListener('resize', () => {
    resizeCanvas()
    drawCanvas()
  })
})
</script>

<style scoped>
.zone-editor-page {
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
.camera-picker {
  display: flex;
  align-items: center;
  gap: 12px;
}
.camera-picker .label {
  font-size: 14px;
  color: #475569;
}
.workspace-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 20px;
}
.canvas-card {
  border-radius: 8px;
}
.canvas-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.canvas-container {
  width: 100%;
  background: #0f172a;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  justify-content: center;
}
.interactive-canvas {
  cursor: crosshair;
  display: block;
}
.canvas-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
.settings-card {
  border-radius: 8px;
}
.polygon-points-preview {
  margin: 16px 0;
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
}
.preview-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}
.points-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.submit-section {
  margin-top: 24px;
}
</style>
