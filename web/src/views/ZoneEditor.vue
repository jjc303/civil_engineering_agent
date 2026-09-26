<template>
  <div class="zone-editor-page">
    <div class="header-section">
      <div class="title-area">
        <h2>危险区域标定 (Zone Editor)</h2>
        <p class="subtitle">基于视频原始像素 (1080P) 的电子围栏几何标定与防抖策略配置</p>
      </div>

      <div class="camera-picker">
        <span class="label">选择目标摄像头：</span>
        <el-select v-model="selectedCameraId" style="width: 200px" @change="handleCameraChange">
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
            <span class="font-bold">监控帧标定画布 (原始帧: {{ sourceResolution.width }}×{{ sourceResolution.height }})</span>
            <div class="tool-btns">
              <el-tag size="small" :type="previewState === 'live' ? 'success' : previewState === 'paused' ? 'warning' : 'info'">{{ previewLabel }}</el-tag>
              <el-button size="small" :disabled="!selectedCameraId" @click="pausePreview">{{ previewState === 'paused' ? '刷新帧' : '暂停画面' }}</el-button>
              <el-button size="small" :disabled="!selectedCameraId || previewState === 'live'" @click="resumePreview">恢复实时</el-button>
              <el-button size="small" type="primary" :icon="Plus" @click="addPoint">添加顶点</el-button>
              <el-button size="small" :icon="RefreshRight" @click="resetToDefaultZone">重置默认形状</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="clearPoints">清空顶点</el-button>
            </div>
          </div>
        </template>

        <div class="canvas-container" ref="containerRef">
          <img v-if="previewImageSrc" class="preview-background" :src="previewImageSrc" alt="监控画面" @error="onPreviewError" />
          <canvas
            ref="canvasRef"
            class="interactive-canvas"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
          ></canvas>
        </div>

        <div class="canvas-hint">
          <span>💡 单击画布添加顶点，拖拽<strong>黄色圆点</strong>调整边界。坐标始终按原始视频帧反算；{{ previewState === 'unavailable' ? '当前没有可用预览，正在使用网格兜底。' : '可暂停为最新帧后精确标定。' }}</span>
        </div>
      </el-card>

      <!-- 参数配置面板 -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <span class="font-bold">防抖与报警参数 (Run Config)</span>
        </template>

        <div class="zones-panel">
          <div class="zones-toolbar"><span class="font-bold">危险区域 ({{ zones.length }})</span><div><el-button size="small" @click="duplicateZone">复制</el-button><el-button size="small" type="primary" @click="createZone">新增</el-button></div></div>
          <div class="zones-list">
            <button v-for="(zone, index) in displayZones" :key="zone.zone_id" class="zone-list-item" :class="{ active: index === selectedZoneIndex }" @click="selectZone(index)">
              <span>{{ zone.zone_name || zone.zone_id }}</span><el-tag size="small" :type="zone.enabled ? 'success' : 'info'">{{ zone.enabled ? '启用' : '停用' }}</el-tag>
            </button>
          </div>
        </div>
        <el-form label-position="top" :model="form" class="config-form">
          <el-form-item label="危险区域标识 (Zone ID)">
            <el-input v-model="zoneConfig.zone_id" placeholder="如 zone-crane-01" />
          </el-form-item>

          <el-form-item label="危险区域显示名 (Zone Name)">
            <el-input v-model="zoneConfig.zone_name" placeholder="如 塔吊回转作业区" />
          </el-form-item>

          <el-button size="small" type="danger" plain :disabled="zones.length <= 1" @click="deleteSelectedZone">删除当前区域</el-button>

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
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, RefreshRight, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchCameras } from '@/api/cameras'
import { fetchCameraZones, updateCameraZones } from '@/api/zones'
import { previewFrameUrl, previewUrl } from '@/api/cameraManagement'
import type { CameraStatusResponse, DangerZoneConfig } from '@/types/contract'

const route = useRoute()

const cameras = ref<CameraStatusResponse[]>([])
const selectedCameraId = ref<string>('')
const currentVersion = ref<number>(0)
const saving = ref(false)
const loadedCameraId = ref<string>('')
const dirty = ref(false)
const hydrating = ref(false)
const zones = ref<DangerZoneConfig[]>([])
const selectedZoneIndex = ref(0)
const previewState = ref<'live' | 'paused' | 'unavailable'>('unavailable')
const previewImageSrc = ref('')

const sourceResolution = ref({ width: 1920, height: 1080 })

// 画布相关
const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const canvasWidth = ref(840)
const canvasHeight = ref(472.5)

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

const displayZones = computed(() => zones.value.map((zone, index) => index === selectedZoneIndex.value
  ? { ...zoneConfig, polygon: polygonPoints.value }
  : zone))
const previewLabel = computed(() => ({ live: '实时预览', paused: '已暂停标帧', unavailable: '预览不可用' }[previewState.value]))

const form = reactive({
  enter_debounce_frames: 3,
  exit_debounce_frames: 5,
  helmet_debounce_frames: 5,
})

const scaleRatioText = computed(() => {
  const sx = (canvasWidth.value / sourceResolution.value.width).toFixed(2)
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

function defaultZone(index = 1): DangerZoneConfig {
  return {
    zone_id: `zone-${index}`,
    zone_name: `危险区域 ${index}`,
    polygon: [[400, 250], [900, 200], [950, 700], [500, 750]],
    enabled: true,
    alarm_dwell_threshold_seconds: 5.0,
  }
}

function syncSelectedZone() {
  if (!zones.value[selectedZoneIndex.value]) return
  zones.value[selectedZoneIndex.value] = {
    ...zoneConfig,
    polygon: polygonPoints.value.map((point) => [point[0], point[1]] as [number, number]),
  }
}

function hydrateSelectedZone(index = selectedZoneIndex.value) {
  const zone = zones.value[index] || defaultZone(index + 1)
  hydrating.value = true
  Object.assign(zoneConfig, { ...zone, polygon: [] })
  polygonPoints.value = zone.polygon.map((point) => [point[0], point[1]] as [number, number])
  nextTick(() => {
    hydrating.value = false
    drawCanvas()
  })
}

async function handleCameraChange(nextCameraId: string) {
  if (dirty.value && loadedCameraId.value && nextCameraId !== loadedCameraId.value) {
    try {
      await ElMessageBox.confirm('当前围栏修改尚未保存，切换摄像头会丢失这些修改。是否继续？', '未保存修改', { type: 'warning' })
    } catch {
      selectedCameraId.value = loadedCameraId.value
      return
    }
  }
  await loadCameraConfig()
}

async function loadCameraConfig() {
  if (!selectedCameraId.value) return
  try {
    const res = await fetchCameraZones(selectedCameraId.value)
    if (res) {
      currentVersion.value = res.config_version
      sourceResolution.value = { ...res.source_resolution }
      form.enter_debounce_frames = res.enter_debounce_frames
      form.exit_debounce_frames = res.exit_debounce_frames
      form.helmet_debounce_frames = res.helmet_debounce_frames
      zones.value = res.zones.length ? JSON.parse(JSON.stringify(res.zones)) : [defaultZone()]
    } else {
      currentVersion.value = 0
      sourceResolution.value = { width: 1920, height: 1080 }
      zones.value = [defaultZone()]
    }
    selectedZoneIndex.value = 0
    hydrateSelectedZone()
    loadedCameraId.value = selectedCameraId.value
    dirty.value = false
    resumePreview()
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
  polygonPoints.value = defaultZone().polygon
  dirty.value = true
  drawCanvas()
}

function clearPoints() {
  polygonPoints.value = []
  dirty.value = true
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
  dirty.value = true
  drawCanvas()
}

function removePoint(idx: number) {
  if (polygonPoints.value.length <= 3) {
    ElMessage.warning('多边形至少需要 3 个顶点')
    return
  }
  polygonPoints.value.splice(idx, 1)
  dirty.value = true
  drawCanvas()
}

function selectZone(index: number) {
  if (index === selectedZoneIndex.value) return
  syncSelectedZone()
  selectedZoneIndex.value = index
  hydrateSelectedZone(index)
}

function createZone() {
  syncSelectedZone()
  zones.value.push(defaultZone(zones.value.length + 1))
  selectedZoneIndex.value = zones.value.length - 1
  hydrateSelectedZone()
  dirty.value = true
}

function duplicateZone() {
  syncSelectedZone()
  const source = zones.value[selectedZoneIndex.value]
  const copy = JSON.parse(JSON.stringify(source)) as DangerZoneConfig
  copy.zone_id = `${source.zone_id}-copy-${zones.value.length + 1}`.slice(0, 128)
  copy.zone_name = `${source.zone_name}（副本）`
  zones.value.push(copy)
  selectedZoneIndex.value = zones.value.length - 1
  hydrateSelectedZone()
  dirty.value = true
}

async function deleteSelectedZone() {
  if (zones.value.length <= 1) return
  try {
    await ElMessageBox.confirm('删除当前危险区域？该操作在保存前可通过取消页面离开恢复。', '删除危险区域', { type: 'warning' })
  } catch { return }
  zones.value.splice(selectedZoneIndex.value, 1)
  selectedZoneIndex.value = Math.max(0, selectedZoneIndex.value - 1)
  hydrateSelectedZone()
  dirty.value = true
}

function resumePreview() {
  if (!selectedCameraId.value) return
  previewState.value = 'live'
  previewImageSrc.value = `${previewUrl(selectedCameraId.value)}?t=${Date.now()}`
}

function pausePreview() {
  if (!selectedCameraId.value) return
  previewState.value = 'paused'
  previewImageSrc.value = `${previewFrameUrl(selectedCameraId.value)}?t=${Date.now()}`
}

function onPreviewError() {
  previewImageSrc.value = ''
  previewState.value = 'unavailable'
}

function resizeCanvas() {
  const container = containerRef.value
  if (!container) return
  const w = container.clientWidth || 840
  canvasWidth.value = w
  canvasHeight.value = (w * sourceResolution.value.height) / sourceResolution.value.width
  const canvas = canvasRef.value
  if (canvas) {
    const ratio = window.devicePixelRatio || 1
    canvas.width = Math.round(canvasWidth.value * ratio)
    canvas.height = Math.round(canvasHeight.value * ratio)
    canvas.style.width = `${canvasWidth.value}px`
    canvas.style.height = `${canvasHeight.value}px`
  }
}

function drawCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const ratio = window.devicePixelRatio || 1
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.clearRect(0, 0, canvasWidth.value, canvasHeight.value)

  // 1. 视频可用时 Canvas 必须透明，作为围栏叠加层；仅无预览时
  // 使用深色网格兜底，避免遮住底层 MJPEG/JPEG 画面。
  if (previewState.value === 'unavailable') {
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, canvasWidth.value, canvasHeight.value)
  }

  ctx.strokeStyle = previewState.value === 'unavailable' ? '#1e293b' : 'rgba(226, 232, 240, 0.22)'
  ctx.lineWidth = 1
  const step = 40
  for (let x = 0; x < canvasWidth.value; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvasHeight.value; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }

  // 2. 先绘制未选中区域，再高亮当前区域。
  const scaleX = canvasWidth.value / sourceResolution.value.width
  const scaleY = canvasHeight.value / sourceResolution.value.height
  for (let index = 0; index < displayZones.value.length; index++) {
    if (index === selectedZoneIndex.value) continue
    const zone = displayZones.value[index]
    if (zone.polygon.length < 2) continue
    ctx.beginPath()
    ctx.moveTo(zone.polygon[0][0] * scaleX, zone.polygon[0][1] * scaleY)
    zone.polygon.slice(1).forEach((point) => ctx.lineTo(point[0] * scaleX, point[1] * scaleY))
    ctx.closePath()
    ctx.strokeStyle = zone.enabled ? '#fb7185' : '#94a3b8'
    ctx.lineWidth = 2
    ctx.setLineDash([7, 5])
    ctx.stroke()
    ctx.setLineDash([])
  }

  // 3. 绘制当前多边形
  const pts = polygonPoints.value
  if (pts.length < 2) return

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

  // 4. 绘制当前区域锚点
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

  const scaleX = canvasWidth.value / sourceResolution.value.width
  const scaleY = canvasHeight.value / sourceResolution.value.height

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
  const px = Math.round(Math.max(0, Math.min(mouseX / scaleX, sourceResolution.value.width)))
  const py = Math.round(Math.max(0, Math.min(mouseY / scaleY, sourceResolution.value.height)))
  polygonPoints.value.push([px, py])
  dirty.value = true
  drawCanvas()
}

function onMouseMove(e: MouseEvent) {
  if (draggingIndex.value === null) return
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mouseX = Math.max(0, Math.min(e.clientX - rect.left, canvasWidth.value))
  const mouseY = Math.max(0, Math.min(e.clientY - rect.top, canvasHeight.value))

  const scaleX = canvasWidth.value / sourceResolution.value.width
  const scaleY = canvasHeight.value / sourceResolution.value.height

  // 逆向反算物理像素
  const px = Math.round(mouseX / scaleX)
  const py = Math.round(mouseY / scaleY)

  polygonPoints.value[draggingIndex.value] = [
    Math.min(px, sourceResolution.value.width), Math.min(py, sourceResolution.value.height),
  ]
  dirty.value = true
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
  syncSelectedZone()
  const invalidZone = zones.value.find((zone) => !zone.zone_id.trim() || !zone.zone_name.trim() || zone.polygon.length < 3)
  if (invalidZone) {
    ElMessage.error('每个危险区域都必须填写 ID、名称并至少包含 3 个顶点')
    return
  }
  if (new Set(zones.value.map((zone) => zone.zone_id)).size !== zones.value.length) {
    ElMessage.error('危险区域标识不能重复')
    return
  }

  saving.value = true
  try {
    const res = await updateCameraZones(selectedCameraId.value, {
      expected_version: currentVersion.value > 0 ? currentVersion.value : null,
      source_resolution: sourceResolution.value,
      enter_debounce_frames: form.enter_debounce_frames,
      exit_debounce_frames: form.exit_debounce_frames,
      helmet_debounce_frames: form.helmet_debounce_frames,
      alarm_dwell_threshold_seconds: zoneConfig.alarm_dwell_threshold_seconds,
      zones: zones.value,
    })

    currentVersion.value = res.config_version
    zones.value = JSON.parse(JSON.stringify(res.zones))
    selectedZoneIndex.value = Math.min(selectedZoneIndex.value, zones.value.length - 1)
    hydrateSelectedZone()
    dirty.value = false
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

watch(zoneConfig, () => { if (!hydrating.value) dirty.value = true }, { deep: true })

const beforeUnload = (event: BeforeUnloadEvent) => {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

let resizeObserver: ResizeObserver | undefined

onMounted(() => {
  init()
  resizeObserver = new ResizeObserver(() => {
    resizeCanvas()
    drawCanvas()
  })
  if (containerRef.value) resizeObserver.observe(containerRef.value)
  window.addEventListener('beforeunload', beforeUnload)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('beforeunload', beforeUnload)
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
  position: relative;
  background: #0f172a;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  justify-content: center;
}
.interactive-canvas {
  cursor: crosshair;
  display: block;
  position: relative;
  z-index: 1;
}
.preview-background {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: fill;
  z-index: 0;
}
.canvas-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
.settings-card {
  border-radius: 8px;
}
.zones-panel { margin-bottom: 16px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; }
.zones-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.zones-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow: auto; }
.zone-list-item { display: flex; align-items: center; justify-content: space-between; width: 100%; border: 1px solid #e2e8f0; border-radius: 4px; background: white; padding: 8px; text-align: left; cursor: pointer; }
.zone-list-item.active { border-color: #409eff; background: #ecf5ff; color: #1d4ed8; }
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
